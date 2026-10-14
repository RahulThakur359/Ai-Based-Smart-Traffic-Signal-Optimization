import unittest
from app import create_app
from database.queries import get_user_by_username


class TestAuthAndApproval(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self._cleanup()

    def tearDown(self):
        self._cleanup()

    def _cleanup(self):
        from database.queries import get_user_by_username, delete_user
        u = get_user_by_username('test_operator_1')
        if u:
            try:
                delete_user(u['id'])
            except Exception:
                pass

    def test_unauthenticated_redirected_to_login(self):
        """Unauthenticated requests to protected dashboard routes should redirect to /login."""
        res = self.client.get('/', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login', res.headers.get('Location', ''))

    def test_default_admin_login_success(self):
        """Default admin account (admin / admin123) should be pre-approved and successfully log in."""
        res = self.client.post('/login', data={
            'username': 'admin',
            'password': 'admin123'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Control Center', res.data)

    def test_signup_creates_pending_user_who_cannot_login(self):
        """
        A newly registered user must receive status PENDING and be barred from logging in
        until an administrator explicitly approves their access.
        """
        # 1. Sign up new operator 'test_driver'
        res_signup = self.client.post('/signup', data={
            'full_name': 'Test Operator',
            'username': 'test_operator_1',
            'email': 'test@traffic.gov',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(res_signup.status_code, 200)

        # Verify DB status is PENDING
        user = get_user_by_username('test_operator_1')
        self.assertIsNotNone(user)
        self.assertEqual(user['status'], 'PENDING')

        # 2. Try to log in as 'test_operator_1' -> MUST BE REJECTED
        res_login_pending = self.client.post('/login', data={
            'username': 'test_operator_1',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(res_login_pending.status_code, 200)
        self.assertIn(b'PENDING', res_login_pending.data)
        self.assertIn(b'Access Denied', res_login_pending.data)

        # 3. Administrator grants access via dashboard API
        res_approve = self.client.post(f'/api/users/{user["id"]}/status', json={'status': 'APPROVED'})
        self.assertEqual(res_approve.status_code, 200)
        self.assertTrue(res_approve.get_json()['success'])

        # Verify DB status changed to APPROVED
        user_approved = get_user_by_username('test_operator_1')
        self.assertEqual(user_approved['status'], 'APPROVED')

        # 4. Now attempt login -> MUST SUCCEED
        res_login_approved = self.client.post('/login', data={
            'username': 'test_operator_1',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(res_login_approved.status_code, 200)
        self.assertIn(b'Control Center', res_login_approved.data)

        # 5. Revoke access -> MUST BE REJECTED AGAIN
        res_revoke = self.client.post(f'/api/users/{user["id"]}/status', json={'status': 'REJECTED'})
        self.assertEqual(res_revoke.status_code, 200)

        # Clear session to re-test login
        with self.client.session_transaction() as sess:
            sess.clear()

        res_login_revoked = self.client.post('/login', data={
            'username': 'test_operator_1',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertIn(b'Access Denied', res_login_revoked.data)


if __name__ == '__main__':
    unittest.main()
