import unittest

from fastapi.testclient import TestClient

from app.core.db import get_db
from main import app
from tests.db import TestingSessionLocal, override_get_db, reset_database
from tests.factories import create_user


class CaptureInboxAPITests(unittest.TestCase):
    def setUp(self):
        reset_database()
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.db = TestingSessionLocal()
        self.user = create_user(self.db, name="Alice")
        self.other_user = create_user(self.db, name="Bob")
        self.headers = {"X-User-Id": str(self.user.id)}
        self.other_headers = {"X-User-Id": str(self.other_user.id)}

    def tearDown(self):
        self.db.close()
        app.dependency_overrides.clear()

    def test_capture_to_inbox_to_task_happy_path(self):
        capture_response = self.client.post(
            "/api/v1/captures",
            json={"raw_text": "完成 Capture Inbox API"},
            headers=self.headers,
        )
        self.assertEqual(capture_response.status_code, 201)
        body = capture_response.json()
        self.assertEqual(body["capture"]["status"], "parsed")
        self.assertEqual(body["parse_result"]["result_type"], "task")
        item_id = body["inbox_item"]["id"]

        inbox_response = self.client.get("/api/v1/inbox", headers=self.headers)
        self.assertEqual(inbox_response.status_code, 200)
        self.assertEqual(len(inbox_response.json()), 1)

        confirm_response = self.client.post(f"/api/v1/inbox/{item_id}/confirm", headers=self.headers)
        self.assertEqual(confirm_response.status_code, 200)
        confirm_body = confirm_response.json()
        self.assertEqual(confirm_body["result_entity_type"], "task")
        self.assertEqual(confirm_body["inbox_item"]["status"], "confirmed")

        pending_response = self.client.get("/api/v1/inbox", headers=self.headers)
        all_status_response = self.client.get("/api/v1/inbox?include_all=true", headers=self.headers)
        self.assertEqual(pending_response.status_code, 200)
        self.assertEqual(pending_response.json(), [])
        self.assertEqual(all_status_response.status_code, 200)
        self.assertEqual(len(all_status_response.json()), 1)
        self.assertEqual(all_status_response.json()[0]["status"], "confirmed")

        task_response = self.client.get(
            f"/api/v1/tasks/{confirm_body['result_entity_id']}",
            headers=self.headers,
        )
        self.assertEqual(task_response.status_code, 200)
        self.assertEqual(task_response.json()["source"], "capture")
        self.assertEqual(task_response.json()["estimated_duration_min"], 25)

        second_confirm_response = self.client.post(f"/api/v1/inbox/{item_id}/confirm", headers=self.headers)
        self.assertEqual(second_confirm_response.status_code, 200)
        self.assertEqual(second_confirm_response.json()["result_entity_id"], confirm_body["result_entity_id"])

    def test_capture_goal_confirm_happy_path(self):
        capture_response = self.client.post(
            "/api/v1/captures",
            json={"raw_text": "目标：完成 Chronos MVP"},
            headers=self.headers,
        )
        item_id = capture_response.json()["inbox_item"]["id"]

        confirm_response = self.client.post(f"/api/v1/inbox/{item_id}/confirm", headers=self.headers)

        self.assertEqual(confirm_response.status_code, 200)
        self.assertEqual(confirm_response.json()["result_entity_type"], "goal")

    def test_edit_unknown_item_then_confirm(self):
        capture_response = self.client.post(
            "/api/v1/captures",
            json={"raw_text": "随手记一些事情"},
            headers=self.headers,
        )
        item_id = capture_response.json()["inbox_item"]["id"]

        update_response = self.client.patch(
            f"/api/v1/inbox/{item_id}",
            json={"item_type": "task", "title": "整理随手记"},
            headers=self.headers,
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["status"], "edited")

        confirm_response = self.client.post(f"/api/v1/inbox/{item_id}/confirm", headers=self.headers)

        self.assertEqual(confirm_response.status_code, 200)
        self.assertEqual(confirm_response.json()["result_entity_type"], "task")

    def test_discard_inbox_item_and_block_confirm(self):
        capture_response = self.client.post(
            "/api/v1/captures",
            json={"raw_text": "完成一个可以丢弃的任务"},
            headers=self.headers,
        )
        item_id = capture_response.json()["inbox_item"]["id"]

        discard_response = self.client.post(f"/api/v1/inbox/{item_id}/discard", headers=self.headers)
        confirm_response = self.client.post(f"/api/v1/inbox/{item_id}/confirm", headers=self.headers)

        self.assertEqual(discard_response.status_code, 200)
        self.assertEqual(discard_response.json()["status"], "discarded")
        self.assertEqual(confirm_response.status_code, 400)
        self.assertEqual(confirm_response.json()["error"]["code"], "INVALID_STATE")

    def test_user_id_isolation_for_inbox(self):
        capture_response = self.client.post(
            "/api/v1/captures",
            json={"raw_text": "完成私有任务"},
            headers=self.headers,
        )
        item_id = capture_response.json()["inbox_item"]["id"]

        response = self.client.get(f"/api/v1/inbox/{item_id}", headers=self.other_headers)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
