import unittest
import uuid

from fastapi.testclient import TestClient

from app.core.db import get_db
from main import app
from app.services.data_source_sync_service import data_source_sync_service
from tests.db import TestingSessionLocal, override_get_db, reset_database
from tests.factories import create_user


class DataSourceAPITests(unittest.TestCase):
    def setUp(self):
        reset_database()
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.db = TestingSessionLocal()
        self.user = create_user(self.db)
        self.other_user = create_user(self.db)
        self.headers = {"X-User-Id": str(self.user.id)}
        self.other_headers = {"X-User-Id": str(self.other_user.id)}

    def tearDown(self):
        self.db.close()
        app.dependency_overrides.clear()

    def test_list_data_sources_returns_catalog(self):
        response = self.client.get("/api/v1/data-sources", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["connected_count"], 0)
        self.assertEqual(
            {source["source_type"] for source in body["sources"]},
            {"calendar", "email", "health"},
        )
        self.assertTrue(all(source["status"] == "disconnected" for source in body["sources"]))

    def test_connect_update_and_disconnect_data_source(self):
        connect_response = self.client.put(
            "/api/v1/data-sources/calendar/google_calendar",
            json={
                "external_account_label": "alice@example.com",
                "sync_enabled": True,
                "connection_metadata": {"origin": "settings"},
            },
            headers=self.headers,
        )
        connection_id = connect_response.json()["id"]
        update_response = self.client.patch(
            f"/api/v1/data-sources/{connection_id}",
            json={"status": "paused", "sync_enabled": False},
            headers=self.headers,
        )
        disconnect_response = self.client.post(
            f"/api/v1/data-sources/{connection_id}/disconnect",
            headers=self.headers,
        )

        self.assertEqual(connect_response.status_code, 200)
        self.assertEqual(connect_response.json()["status"], "connected")
        self.assertEqual(connect_response.json()["scopes"], ["calendar.read"])
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["status"], "paused")
        self.assertFalse(update_response.json()["sync_enabled"])
        self.assertEqual(disconnect_response.status_code, 200)
        self.assertEqual(disconnect_response.json()["status"], "disconnected")
        self.assertFalse(disconnect_response.json()["sync_enabled"])

    def test_unsupported_provider_returns_validation_error(self):
        response = self.client.put(
            "/api/v1/data-sources/email/google_calendar",
            json={},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")

    def test_connection_isolated_by_user(self):
        connect_response = self.client.put(
            "/api/v1/data-sources/email/gmail",
            json={},
            headers=self.headers,
        )
        connection_id = connect_response.json()["id"]

        response = self.client.post(
            f"/api/v1/data-sources/{connection_id}/disconnect",
            headers=self.other_headers,
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")

    def test_list_data_source_sync_runs_returns_recent_runs(self):
        connect_response = self.client.put(
            "/api/v1/data-sources/email/gmail",
            json={
                "connection_metadata": {
                    "fake_items": [
                        {
                            "external_item_id": "api-sync-run-email-1",
                            "title": "同步运行记录验证",
                        }
                    ],
                    "fake_next_cursor": "api-sync-cursor-2",
                }
            },
            headers=self.headers,
        )
        connection_id = connect_response.json()["id"]
        data_source_sync_service.sync_connection(self.db, connection_id=uuid.UUID(connection_id))

        response = self.client.get(
            f"/api/v1/data-sources/{connection_id}/sync-runs",
            headers=self.headers,
        )
        other_response = self.client.get(
            f"/api/v1/data-sources/{connection_id}/sync-runs",
            headers=self.other_headers,
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["status"], "succeeded")
        self.assertEqual(body[0]["provider"], "gmail")
        self.assertEqual(body[0]["imported_count"], 1)
        self.assertEqual(body[0]["provider_mode"], "fake")
        self.assertEqual(body[0]["sync_cursor_after"], "api-sync-cursor-2")
        self.assertFalse(body[0]["retryable"])
        self.assertEqual(other_response.status_code, 404)
        self.assertEqual(other_response.json()["error"]["code"], "NOT_FOUND")

    def test_get_data_source_sync_summary(self):
        connect_response = self.client.put(
            "/api/v1/data-sources/email/gmail",
            json={
                "connection_metadata": {
                    "fake_items": [
                        {
                            "external_item_id": "api-sync-summary-email-1",
                            "title": "同步摘要 API 验证",
                        }
                    ]
                }
            },
            headers=self.headers,
        )
        connection_id = connect_response.json()["id"]
        data_source_sync_service.sync_connection(self.db, connection_id=uuid.UUID(connection_id))

        response = self.client.get("/api/v1/data-sources/sync-summary", headers=self.headers)
        other_response = self.client.get("/api/v1/data-sources/sync-summary", headers=self.other_headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["connected_count"], 1)
        self.assertEqual(body["sync_enabled_count"], 1)
        self.assertEqual(body["attention_count"], 0)
        self.assertIsNotNone(body["latest_success_at"])
        self.assertEqual(len(body["items"]), 1)
        self.assertEqual(body["items"][0]["connection_id"], connection_id)
        self.assertEqual(body["items"][0]["latest_run_status"], "succeeded")
        self.assertEqual(body["items"][0]["imported_count"], 1)
        self.assertEqual(other_response.status_code, 200)
        self.assertEqual(other_response.json()["items"], [])

    def test_manual_sync_connection_imports_items(self):
        connect_response = self.client.put(
            "/api/v1/data-sources/calendar/google_calendar",
            json={
                "connection_metadata": {
                    "fake_items": [
                        {
                            "external_item_id": "api-manual-sync-calendar-1",
                            "title": "手动同步 API 验证",
                        }
                    ]
                }
            },
            headers=self.headers,
        )
        connection_id = connect_response.json()["id"]

        response = self.client.post(f"/api/v1/data-sources/{connection_id}/sync", headers=self.headers)
        other_response = self.client.post(f"/api/v1/data-sources/{connection_id}/sync", headers=self.other_headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "synced")
        self.assertEqual(body["connection_id"], connection_id)
        self.assertEqual(body["source_type"], "calendar")
        self.assertEqual(body["imported_count"], 1)
        self.assertTrue(body["import_record_ids"])
        inbox_response = self.client.get("/api/v1/inbox", headers=self.headers)
        self.assertEqual(inbox_response.status_code, 200)
        self.assertEqual(len(inbox_response.json()), 1)
        self.assertEqual(inbox_response.json()[0]["status"], "pending")
        self.assertEqual(inbox_response.json()[0]["title"], "手动同步 API 验证")
        self.assertEqual(other_response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
