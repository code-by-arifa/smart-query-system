import os
os.environ.setdefault("JWT_SECRET", "unit-test-secret-that-is-at-least-32-characters-long")
import unittest
from app.security import issue_session, current_user


class SecurityTests(unittest.TestCase):
    def test_session_contains_user_id(self):
        token = issue_session("user-123")
        # Unit-level decode verifies the token contract without a database.
        import jwt
        from app.security import SECRET
        self.assertEqual(jwt.decode(token, SECRET, algorithms=["HS256"])["sub"], "user-123")


if __name__ == "__main__":
    unittest.main()
