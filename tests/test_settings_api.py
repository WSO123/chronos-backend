import unittest

from fastapi.testclient import TestClient

from app.core.db import get_db
from app.models.user import UserSettings
from main import app
from tests.db import TestingSessionLocal, override_get_db, reset_database
from tests.factories import create_user


class SettingsAPITests(unittest.TestCase):
    def setUp(self):
        reset_database()
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.db = TestingSessionLocal()
        self.user = create_user(self.db, name="Alice")
        self.headers = {"X-User-Id": str(self.user.id)}

    def tearDown(self):
        self.db.close()
        app.dependency_overrides.clear()

    def test_get_settings_creates_default_settings(self):
        response = self.client.get("/api/v1/me/settings", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["notification_enabled"], True)
        self.assertEqual(body["reminder_execution_enabled"], True)
        self.assertEqual(body["reminder_deadline_enabled"], True)
        self.assertEqual(body["reminder_channel_in_app_enabled"], True)
        self.assertEqual(body["execution_reminder_limit"], 3)
        self.assertEqual(self.db.query(UserSettings).filter(UserSettings.user_id == self.user.id).count(), 1)

    def test_patch_settings_updates_reminder_preferences_and_me_overview(self):
        response = self.client.patch(
            "/api/v1/me/settings",
            json={
                "notification_enabled": False,
                "reminder_execution_enabled": False,
                "reminder_deadline_enabled": True,
                "execution_reminder_limit": 2,
                "execution_reminder_start_hour": 10,
                "execution_reminder_spacing_minutes": 60,
                "deadline_reminder_hour": 8,
            },
            headers=self.headers,
        )
        overview_response = self.client.get("/api/v1/me/overview", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["notification_enabled"], False)
        self.assertEqual(body["reminder_execution_enabled"], False)
        self.assertEqual(body["execution_reminder_limit"], 2)
        self.assertEqual(body["execution_reminder_start_hour"], 10)
        self.assertEqual(body["execution_reminder_spacing_minutes"], 60)
        self.assertEqual(body["deadline_reminder_hour"], 8)
        self.assertEqual(overview_response.status_code, 200)
        self.assertEqual(overview_response.json()["settings"]["notification_enabled"], False)
        self.assertEqual(overview_response.json()["settings"]["reminder_execution_enabled"], False)

    def test_patch_settings_rejects_disabling_all_channels(self):
        response = self.client.patch(
            "/api/v1/me/settings",
            json={
                "reminder_channel_in_app_enabled": False,
                "reminder_channel_push_enabled": False,
                "reminder_channel_email_enabled": False,
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")


if __name__ == "__main__":
    unittest.main()
