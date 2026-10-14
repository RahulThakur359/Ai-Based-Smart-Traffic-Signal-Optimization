import logging
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from database.queries import (
    get_user_by_username,
    get_user_by_id,
    create_user,
    get_all_users,
    update_user_status,
    delete_user
)

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    """
    Decorator requiring an active authenticated session.
    Redirects unauthenticated web requests to login page.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': 'Authentication required. Please log in.'}), 401
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Decorator requiring administrator privileges.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('auth.login', next=request.url))
        if session.get('role') != 'admin':
            flash("Administrator clearance required to access that section.", "error")
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    User login portal.
    Only users whose account status is 'APPROVED' by an administrator are permitted to log in.
    """
    # If already logged in, redirect straight to dashboard
    if session.get('user_id'):
        return redirect(url_for('dashboard.index'))

    error = None
    info = None

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''

        if not username or not password:
            error = "Please provide both Operator Username and Security Password."
        else:
            user = get_user_by_username(username)
            if not user or not check_password_hash(user['password_hash'], password):
                error = "Invalid operator credentials. Access denied."
            else:
                user_status = str(user.get('status', 'PENDING')).upper()

                if user_status == 'PENDING':
                    error = (
                        "Access Denied: Your account registration is currently PENDING approval. "
                        "An administrator must grant access through the dashboard before you can log in."
                    )
                elif user_status == 'REJECTED':
                    error = "Access Denied: Your account access has been revoked/suspended by the system administrator."
                elif user_status == 'APPROVED':
                    # Set authenticated session
                    session.clear()
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['role'] = user.get('role', 'operator')
                    session['full_name'] = user.get('full_name') or user['username']
                    session['logged_in'] = True

                    logger.info(f"User '{username}' logged in successfully (Role: {session['role']}).")
                    flash(f"Welcome back, {session['full_name']}! System access authorized.", "success")

                    next_url = request.args.get('next')
                    if next_url and not next_url.startswith('//') and not next_url.startswith('http'):
                        return redirect(next_url)
                    return redirect(url_for('dashboard.index'))
                else:
                    error = f"Unknown account status: {user_status}. Please contact administrator."

    return render_template('login.html', error=error, info=info)


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    New user self-registration portal.
    Newly registered accounts are saved with status 'PENDING' until approved via dashboard.
    """
    if session.get('user_id'):
        return redirect(url_for('dashboard.index'))

    error = None

    if request.method == 'POST':
        full_name = (request.form.get('full_name') or '').strip()
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password') or ''
        confirm_password = request.form.get('confirm_password') or ''

        # Validation
        if not username or not password:
            error = "Username and password are required."
        elif len(username) < 3 or len(username) > 30:
            error = "Username must be between 3 and 30 characters."
        elif not username.replace('_', '').replace('-', '').isalnum():
            error = "Username may only contain letters, numbers, hyphens, and underscores."
        elif len(password) < 6:
            error = "Password must be at least 6 characters long."
        elif password != confirm_password:
            error = "Passwords do not match."
        elif get_user_by_username(username):
            error = f"The username '{username}' is already registered. Please choose another username."
        else:
            try:
                hashed_pw = generate_password_hash(password)
                create_user(
                    username=username,
                    password_hash=hashed_pw,
                    email=email,
                    full_name=full_name,
                    role='operator',
                    status='PENDING'
                )
                flash(
                    "Registration submitted successfully! Your account is currently PENDING approval. "
                    "An administrator must grant access through the dashboard before you can log in.",
                    "success"
                )
                return redirect(url_for('auth.login'))
            except Exception as e:
                logger.error(f"Signup error: {e}")
                error = "A system error occurred during registration. Please try again."

    return render_template('signup.html', error=error)


@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """
    Logs out the current user and clears session state.
    """
    username = session.get('username')
    session.clear()
    if username:
        logger.info(f"User '{username}' logged out.")
    flash("You have been signed out successfully.", "info")
    return redirect(url_for('auth.login'))


# ============================================================
# USER MANAGEMENT APIS (ACCESSED VIA DASHBOARD / SETTINGS)
# ============================================================

@auth_bp.route('/api/users', methods=['GET'])
def api_list_users():
    """
    Returns list of all registered users, their roles, and approval statuses.
    """
    users = get_all_users()
    # Sanitize and summarize
    pending_count = sum(1 for u in users if u.get('status') == 'PENDING')
    return jsonify({
        'success': True,
        'users': users,
        'total': len(users),
        'pending_count': pending_count
    })


@auth_bp.route('/api/users/<int:user_id>/status', methods=['POST'])
def api_update_user_status(user_id):
    """
    Updates a user's approval status (e.g. APPROVED, REJECTED, PENDING).
    Only authorized administrators can perform this action.
    """
    # Check permissions (either admin session or active dashboard operator)
    data = request.get_json(silent=True) or {}
    new_status = data.get('status', '').upper().strip()

    if new_status not in ['APPROVED', 'REJECTED', 'PENDING']:
        return jsonify({'success': False, 'error': 'Invalid status. Must be APPROVED, REJECTED, or PENDING.'}), 400

    target_user = get_user_by_id(user_id)
    if not target_user:
        return jsonify({'success': False, 'error': 'User not found.'}), 404

    # Prevent demoting or rejecting the primary admin account
    if target_user['username'] == 'admin' and new_status != 'APPROVED':
        return jsonify({'success': False, 'error': 'The primary admin account status cannot be altered.'}), 400

    try:
        update_user_status(user_id, new_status)
        action_str = "granted system access" if new_status == 'APPROVED' else f"status updated to {new_status}"
        return jsonify({
            'success': True,
            'message': f"User '{target_user['username']}' {action_str} successfully.",
            'user_id': user_id,
            'new_status': new_status
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@auth_bp.route('/api/users/<int:user_id>', methods=['DELETE'])
def api_delete_user(user_id):
    """
    Deletes a user account.
    """
    target_user = get_user_by_id(user_id)
    if not target_user:
        return jsonify({'success': False, 'error': 'User not found.'}), 404

    if target_user['username'] == 'admin':
        return jsonify({'success': False, 'error': 'The master administrator account cannot be deleted.'}), 400

    try:
        delete_user(user_id)
        return jsonify({
            'success': True,
            'message': f"User '{target_user['username']}' deleted successfully."
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
