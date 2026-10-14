from flask import Blueprint, render_template, redirect, url_for, session
from .auth import login_required

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    """
    Renders the main Traffic Optimization Control Dashboard.
    Requires authenticated operator or administrator session.
    """
    return render_template('dashboard.html', current_user=session.get('username'), user_role=session.get('role'))

@dashboard_bp.route('/login')
def login():
    """
    Renders or redirects to the unified authentication login portal.
    """
    return redirect(url_for('auth.login'))

@dashboard_bp.route('/reports')
@login_required
def reports():
    """
    Renders historical reports and analytics dashboards.
    """
    return render_template('reports.html', current_user=session.get('username'), user_role=session.get('role'))

@dashboard_bp.route('/settings')
@login_required
def settings():
    """
    Renders system settings (threshold configurations, database config, user access control).
    """
    return render_template('settings.html', current_user=session.get('username'), user_role=session.get('role'))

