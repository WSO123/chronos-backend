import unittest
from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.db import get_db
from app.core.security import create_access_token
from main import app
from tests.db import TestingSessionLocal, override_get_db, reset_database
from tests.factories import create_user


class AuthDependencyTests(unittest.TestCase):
    def setUp(self):
        reset_database()
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.db = TestingSessionLocal()
        self.user = create_user(self.db, name="Alice")
        self.original_auth_mode = settings.AUTH_MODE
        self.original_environment = settings.ENVIRONMENT
        self.original_allow_dev_auth_header = settings.ALLOW_DEV_AUTH_HEADER
        self.original_secret_key = settings.SECRET_KEY
        settings.AUTH_MODE = "dev_header"
        settings.ENVIRONMENT = "development"
        settings.ALLOW_DEV_AUTH_HEADER = True
        settings.SECRET_KEY = "test-secret-key"

    def tearDown(self):
        settings.AUTH_MODE = self.original_auth_mode
        settings.ENVIRONMENT = self.original_environment
        settings.ALLOW_DEV_AUTH_HEADER = self.original_allow_dev_auth_header
        settings.SECRET_KEY = self.original_secret_key
        self.db.close()
        app.dependency_overrides.clear()

    def test_dev_header_mode_accepts_x_user_id_in_development(self):
        response = self.client.get("/api/v1/me/overview", headers={"X-User-Id": str(self.user.id)})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["profile"]["user_id"], str(self.user.id))

    def test_dev_header_mode_fails_closed_in_production(self):
        settings.ENVIRONMENT = "production"

        response = self.client.get("/api/v1/me/overview", headers={"X-User-Id": str(self.user.id)})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "INSECURE_AUTH_CONFIGURATION")

    def test_inactive_user_is_forbidden(self):
        self.user.is_active = False
        self.db.commit()

        response = self.client.get("/api/v1/me/overview", headers={"X-User-Id": str(self.user.id)})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "USER_INACTIVE")

    def test_jwt_mode_accepts_bearer_token_without_dev_header(self):
        settings.AUTH_MODE = "jwt"
        token = create_access_token(self.user.id)

        response = self.client.get("/api/v1/me/overview", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["profile"]["user_id"], str(self.user.id))

    def test_jwt_mode_does_not_accept_x_user_id_as_auth(self):
        settings.AUTH_MODE = "jwt"

        response = self.client.get("/api/v1/me/overview", headers={"X-User-Id": str(self.user.id)})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "AUTH_REQUIRED")

    def test_jwt_mode_rejects_invalid_token(self):
        settings.AUTH_MODE = "jwt"

        response = self.client.get("/api/v1/me/overview", headers={"Authorization": "Bearer invalid-token"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "INVALID_ACCESS_TOKEN")

    def test_jwt_mode_rejects_expired_token(self):
        settings.AUTH_MODE = "jwt"
        token = create_access_token(self.user.id, expires_delta=timedelta(seconds=-1))

        response = self.client.get("/api/v1/me/overview", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "ACCESS_TOKEN_EXPIRED")

    def test_jwt_mode_rejects_non_access_token(self):
        settings.AUTH_MODE = "jwt"
        token = create_access_token(self.user.id, extra_claims={"type": "refresh"})

        response = self.client.get("/api/v1/me/overview", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "INVALID_ACCESS_TOKEN")

    def test_jwt_mode_fails_closed_with_default_secret_in_production(self):
        settings.AUTH_MODE = "jwt"
        settings.ENVIRONMENT = "production"
        settings.SECRET_KEY = "change-me-in-production"
        token = create_access_token(self.user.id)

        response = self.client.get("/api/v1/me/overview", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "INSECURE_AUTH_CONFIGURATION")


if __name__ == "__main__":
    unittest.main()
