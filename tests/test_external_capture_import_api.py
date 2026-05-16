import unittest

from fastapi.testclient import TestClient

from app.core.db import get_db
from main import app
from tests.db import TestingSessionLocal, override_get_db, reset_database
from tests.factories import create_user


class ExternalCaptureImportAPITests(unittest.TestCase):
    def setUp(self):
        reset_database()
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.db = TestingSessionLocal()
        self.user = create_user(self.db)
        self.headers = {"X-User-Id": str(self.user.id)}

    def tearDown(self):
        self.db.close()
        app.dependency_overrides.clear()

    def test_external_calendar_import_enters_capture_inbox_path(self):
        connection_response = self.client.put(
            "/api/v1/data-sources/calendar/google_calendar",
            json={},
            headers=self.headers,
        )
        connection_id = connection_response.json()["id"]

        import_response = self.client.post(
            "/api/v1/captures/external-imports",
            json={
                "data_source_connection_id": connection_id,
                "external_item_id": "calendar-event-api-1",
                "external_item_type": "calendar_event",
                "title": "完成 API 联调",
                "body": "从日历导入",
            },
            headers=self.headers,
        )
        body = import_response.json()
        confirm_response = self.client.post(
            f"/api/v1/inbox/{body['inbox_item']['id']}/confirm",
            headers=self.headers,
        )
        task_response = self.client.get(
            f"/api/v1/tasks/{confirm_response.json()['result_entity_id']}",
            headers=self.headers,
        )

        self.assertEqual(import_response.status_code, 200)
        self.assertTrue(body["created"])
        self.assertEqual(body["capture"]["input_type"], "external")
        self.assertEqual(body["capture"]["source"], "calendar")
        self.assertEqual(body["inbox_item"]["title"], "完成 API 联调")
        self.assertEqual(confirm_response.status_code, 200)
        self.assertEqual(task_response.json()["source"], "calendar")
        source_context = task_response.json()["source_context"]
        self.assertEqual(source_context["source"], "calendar")
        self.assertEqual(source_context["capture_source"], "calendar")
        self.assertEqual(source_context["provider"], "google_calendar")
        self.assertEqual(source_context["external_item_id"], "calendar-event-api-1")
        self.assertEqual(source_context["external_item_type"], "calendar_event")
        self.assertEqual(source_context["external_title"], "完成 API 联调")
        self.assertEqual(source_context["external_body_preview"], "从日历导入")
        self.assertNotIn("external_payload", source_context)
        self.assertNotIn("normalized_text", source_context)

    def test_duplicate_external_import_reuses_existing_capture(self):
        connection_response = self.client.put(
            "/api/v1/data-sources/email/gmail",
            json={},
            headers=self.headers,
        )
        payload = {
            "data_source_connection_id": connection_response.json()["id"],
            "external_item_id": "email-api-1",
            "external_item_type": "email_message",
            "title": "完成邮件回复",
        }

        first_response = self.client.post("/api/v1/captures/external-imports", json=payload, headers=self.headers)
        second_response = self.client.post("/api/v1/captures/external-imports", json=payload, headers=self.headers)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertTrue(first_response.json()["created"])
        self.assertFalse(second_response.json()["created"])
        self.assertEqual(
            first_response.json()["import_record"]["id"],
            second_response.json()["import_record"]["id"],
        )
        self.assertEqual(
            first_response.json()["capture"]["id"],
            second_response.json()["capture"]["id"],
        )

    def test_health_connection_cannot_import_capture(self):
        connection_response = self.client.put(
            "/api/v1/data-sources/health/apple_health",
            json={},
            headers=self.headers,
        )

        response = self.client.post(
            "/api/v1/captures/external-imports",
            json={
                "data_source_connection_id": connection_response.json()["id"],
                "external_item_id": "sleep-api-1",
                "external_item_type": "sleep_sample",
                "title": "Sleep sample",
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")


if __name__ == "__main__":
    unittest.main()
