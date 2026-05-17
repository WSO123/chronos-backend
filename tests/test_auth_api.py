import unittest

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.db import get_db
from app.models.user import AuthRefreshToken, User
from main import app
from tests.db import TestingSessionLocal, override_get_db, reset_database
from tests.factories import create_user


class AuthAPITests(unittest.TestCase):
    def setUp(self):
        reset_database()
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.db = TestingSessionLocal()
        self.original_auth_mode = settings.AUTH_MODE
        self.original_environment = settings.ENVIRONMENT
        self.original_secret_key = settings.SECRET_KEY
        settings.AUTH_MODE = "jwt"
        settings.ENVIRONMENT = "development"
        settings.SECRET_KEY = "test-secret-key"

    def tearDown(self):
        settings.AUTH_MODE = self.original_auth_mode
        settings.ENVIRONMENT = self.original_environment
        settings.SECRET_KEY = self.original_secret_key
        self.db.close()
        app.dependency_overrides.clear()

    def test_register_returns_token_pair_and_stores_password_hash(self):
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": " Alice@Example.COM ",
                "password": "safe-password",
                "name": "Alice",
                "timezone": "Asia/Shanghai",
            },
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["token_type"], "bearer")
        self.assertTrue(body["access_token"])
        self.assertTrue(body["refresh_token"])
        self.assertEqual(body["expires_in"], 1800)
        self.assertEqual(body["refresh_expires_in"], 30 * 24 * 60 * 60)
        self.assertEqual(body["user"]["email"], "alice@example.com")
        user = self.db.scalars(select(User).where(User.email == "alice@example.com")).one()
        self.assertIsNotNone(user.password_hash)
        self.assertNotEqual(user.password_hash, "safe-password")
        self.assertEqual(self.db.query(AuthRefreshToken).filter(AuthRefreshToken.user_id == user.id).count(), 1)

    def test_register_rejects_duplicate_email_case_insensitive(self):
        payload = {
            "email": "alice@example.com",
            "password": "safe-password",
            "name": "Alice",
        }
        first = self.client.post("/api/v1/auth/register", json=payload)
        second = self.client.post(
            "/api/v1/auth/register",
            json={**payload, "email": "ALICE@example.com"},
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.json()["error"]["code"], "CONFLICT")

    def test_register_rejects_blank_name_after_trimming(self):
        response = self.client.post(
            "/api/v1/auth/register",
            json={"email": "alice@example.com", "password": "safe-password", "name": "   "},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "REQUEST_VALIDATION_ERROR")

    def test_login_returns_token_pair_and_bearer_token_can_read_auth_me(self):
        self.client.post(
            "/api/v1/auth/register",
            json={"email": "alice@example.com", "password": "safe-password", "name": "Alice"},
        )

        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "alice@example.com", "password": "safe-password"},
        )
        body = response.json()
        me_response = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {body['access_token']}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["email"], "alice@example.com")

    def test_login_rejects_invalid_password(self):
        self.client.post(
            "/api/v1/auth/register",
            json={"email": "alice@example.com", "password": "safe-password", "name": "Alice"},
        )

        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "alice@example.com", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "AUTHENTICATION_FAILED")

    def test_login_rejects_inactive_user(self):
        create_user(
            self.db,
            name="Inactive",
            email="inactive@example.com",
            password="safe-password",
            is_active=False,
        )

        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "inactive@example.com", "password": "safe-password"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "FORBIDDEN")

    def test_login_fails_closed_with_default_secret_in_production(self):
        self.client.post(
            "/api/v1/auth/register",
            json={"email": "alice@example.com", "password": "safe-password", "name": "Alice"},
        )
        settings.ENVIRONMENT = "production"
        settings.SECRET_KEY = "change-me-in-production"

        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "alice@example.com", "password": "safe-password"},
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "INSECURE_AUTH_CONFIGURATION")

    def test_refresh_rotates_refresh_token_and_rejects_reuse(self):
        register_response = self.client.post(
            "/api/v1/auth/register",
            json={"email": "alice@example.com", "password": "safe-password", "name": "Alice"},
        )
        original_refresh = register_response.json()["refresh_token"]

        refresh_response = self.client.post("/api/v1/auth/refresh", json={"refresh_token": original_refresh})
        reuse_response = self.client.post("/api/v1/auth/refresh", json={"refresh_token": original_refresh})
        new_refresh = refresh_response.json()["refresh_token"]
        second_refresh_response = self.client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})

        self.assertEqual(refresh_response.status_code, 200)
        self.assertNotEqual(new_refresh, original_refresh)
        self.assertEqual(reuse_response.status_code, 401)
        self.assertEqual(reuse_response.json()["error"]["code"], "AUTHENTICATION_FAILED")
        self.assertEqual(second_refresh_response.status_code, 200)

    def test_logout_revokes_refresh_token(self):
        register_response = self.client.post(
            "/api/v1/auth/register",
            json={"email": "alice@example.com", "password": "safe-password", "name": "Alice"},
        )
        refresh_token = register_response.json()["refresh_token"]

        logout_response = self.client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
        refresh_response = self.client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        second_logout_response = self.client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})

        self.assertEqual(logout_response.status_code, 200)
        self.assertEqual(logout_response.json()["revoked"], True)
        self.assertIsNotNone(logout_response.json()["revoked_at"])
        self.assertEqual(refresh_response.status_code, 401)
        self.assertEqual(second_logout_response.status_code, 200)
        self.assertEqual(second_logout_response.json()["revoked"], True)


if __name__ == "__main__":
    unittest.main()
