import unittest
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.core.db import get_db
from main import app
from tests.db import TestingSessionLocal, override_get_db, reset_database
from tests.factories import create_user


class TaskGoalAPITests(unittest.TestCase):
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

    def test_goal_and_task_happy_path(self):
        goal_response = self.client.post(
            "/api/v1/goals",
            json={"title": "Launch MVP", "value_level": "high"},
            headers=self.headers,
        )
        self.assertEqual(goal_response.status_code, 201)
        goal_id = goal_response.json()["id"]

        task_response = self.client.post(
            "/api/v1/tasks",
            json={
                "title": "Implement Task API",
                "goal_id": goal_id,
                "priority": 2,
                "value_level": "high",
            },
            headers=self.headers,
        )
        self.assertEqual(task_response.status_code, 201)
        task_body = task_response.json()
        self.assertEqual(task_body["title"], "Implement Task API")
        self.assertEqual(task_body["goal_id"], goal_id)
        task_id = task_body["id"]

        step_response = self.client.post(
            f"/api/v1/tasks/{task_id}/steps",
            json={"title": "Write schemas"},
            headers=self.headers,
        )
        self.assertEqual(step_response.status_code, 201)
        step_id = step_response.json()["id"]

        complete_step_response = self.client.post(
            f"/api/v1/tasks/{task_id}/steps/{step_id}/complete",
            headers=self.headers,
        )
        self.assertEqual(complete_step_response.status_code, 200)
        self.assertTrue(complete_step_response.json()["is_completed"])

        complete_task_response = self.client.post(
            f"/api/v1/tasks/{task_id}/complete",
            headers=self.headers,
        )
        self.assertEqual(complete_task_response.status_code, 200)
        self.assertEqual(complete_task_response.json()["status"], "completed")

        events_response = self.client.get(f"/api/v1/tasks/{task_id}/events", headers=self.headers)
        self.assertEqual(events_response.status_code, 200)
        event_types = {event["event_type"] for event in events_response.json()}
        self.assertIn("TASK_CREATED", event_types)
        self.assertIn("TASK_STEP_COMPLETED", event_types)
        self.assertIn("TASK_COMPLETED", event_types)

    def test_adjust_task_priority_api_returns_adjustment_summary(self):
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Re-rank this task", "priority": 5, "value_level": "low"},
            headers=self.headers,
        )
        task_id = task_response.json()["id"]

        response = self.client.patch(
            f"/api/v1/tasks/{task_id}/priority",
            json={"priority": 1, "value_level": "high", "reason": "Protect high-value work"},
            headers=self.headers,
        )
        events_response = self.client.get(f"/api/v1/tasks/{task_id}/events", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["previous_priority"], 5)
        self.assertEqual(body["current_priority"], 1)
        self.assertEqual(body["previous_value_level"], "low")
        self.assertEqual(body["current_value_level"], "high")
        self.assertEqual(body["changed_fields"], ["priority", "value_level"])
        self.assertEqual(body["task"]["priority"], 1)
        self.assertEqual(body["task"]["value_level"], "high")
        self.assertIn("TASK_PRIORITY_ADJUSTED", {event["event_type"] for event in events_response.json()})

    def test_adjust_task_priority_requires_priority_or_value_level(self):
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "No empty adjustment"},
            headers=self.headers,
        )

        response = self.client.patch(
            f"/api/v1/tasks/{task_response.json()['id']}/priority",
            json={"reason": "Missing fields"},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 422)

    def test_get_task_returns_task_detail_execution_context(self):
        goal_response = self.client.post(
            "/api/v1/goals",
            json={"title": "Detail Goal", "value_level": "high"},
            headers=self.headers,
        )
        goal_id = goal_response.json()["id"]
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Open Task Detail", "goal_id": goal_id, "priority": 1, "value_level": "high"},
            headers=self.headers,
        )
        task_id = task_response.json()["id"]
        self.client.post(
            f"/api/v1/tasks/{task_id}/steps",
            json={"title": "Check context"},
            headers=self.headers,
        )
        today_response = self.client.get("/api/v1/today", headers=self.headers)
        self.assertEqual(today_response.status_code, 200)

        detail_response = self.client.get(f"/api/v1/tasks/{task_id}", headers=self.headers)

        self.assertEqual(detail_response.status_code, 200)
        body = detail_response.json()
        self.assertEqual(body["title"], "Open Task Detail")
        self.assertEqual(body["goal"]["title"], "Detail Goal")
        self.assertEqual(body["ai_info"]["execution_suggestion"], "Continue with: Check context")
        self.assertIsNotNone(body["today_context"])
        self.assertTrue(body["actions"]["can_start_focus"])
        self.assertFalse(body["focus_state"]["is_currently_focusing_this_task"])

    def test_get_goal_detail_returns_goal_progress_and_next_task(self):
        goal_response = self.client.post(
            "/api/v1/goals",
            json={"title": "Goal Detail API", "value_level": "high"},
            headers=self.headers,
        )
        goal_id = goal_response.json()["id"]
        next_task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Do the important part", "goal_id": goal_id, "priority": 1, "value_level": "high"},
            headers=self.headers,
        )
        completed_task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Already done part", "goal_id": goal_id},
            headers=self.headers,
        )
        self.client.post(f"/api/v1/tasks/{completed_task_response.json()['id']}/complete", headers=self.headers)

        response = self.client.get(f"/api/v1/goals/{goal_id}/detail", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["overview"]["id"], goal_id)
        self.assertEqual(body["progress"]["total_task_count"], 2)
        self.assertEqual(body["progress"]["completed_task_count"], 1)
        self.assertEqual(body["task_list"]["recommended_next_task"]["id"], next_task_response.json()["id"])
        self.assertEqual(body["ai_suggestion"]["next_action_task_id"], next_task_response.json()["id"])
        self.assertEqual(body["dependency_map"]["edges"], [])
        self.assertFalse(body["actions"]["can_mark_complete"])

    def test_task_dependency_api_and_goal_detail_edges(self):
        goal_response = self.client.post("/api/v1/goals", json={"title": "API dependency goal"}, headers=self.headers)
        self.assertEqual(goal_response.status_code, 201)
        prerequisite_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "API prerequisite", "goal_id": goal_response.json()["id"]},
            headers=self.headers,
        )
        dependent_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "API dependent", "goal_id": goal_response.json()["id"]},
            headers=self.headers,
        )
        self.assertEqual(prerequisite_response.status_code, 201)
        self.assertEqual(dependent_response.status_code, 201)
        prerequisite_id = prerequisite_response.json()["id"]
        dependent_id = dependent_response.json()["id"]

        create_response = self.client.post(
            f"/api/v1/tasks/{dependent_id}/dependencies",
            json={"prerequisite_task_id": prerequisite_id, "reason": "Do first"},
            headers=self.headers,
        )
        dependencies_response = self.client.get(f"/api/v1/tasks/{dependent_id}/dependencies", headers=self.headers)
        detail_response = self.client.get(f"/api/v1/goals/{goal_response.json()['id']}/detail", headers=self.headers)

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["prerequisite_task"]["task_id"], prerequisite_id)
        self.assertEqual(dependencies_response.status_code, 200)
        self.assertEqual(dependencies_response.json()["prerequisites"][0]["reason"], "Do first")
        self.assertEqual(detail_response.json()["dependency_map"]["edges"][0]["from_task_id"], prerequisite_id)
        self.assertEqual(detail_response.json()["dependency_map"]["edges"][0]["to_task_id"], dependent_id)

        cycle_response = self.client.post(
            f"/api/v1/tasks/{prerequisite_id}/dependencies",
            json={"prerequisite_task_id": dependent_id},
            headers=self.headers,
        )
        self.assertEqual(cycle_response.status_code, 400)
        self.assertEqual(cycle_response.json()["error"]["code"], "INVALID_STATE")

        delete_response = self.client.delete(
            f"/api/v1/tasks/{dependent_id}/dependencies/{prerequisite_id}",
            headers=self.headers,
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()["prerequisites"], [])

    def test_task_dependency_api_keeps_user_isolation(self):
        own_task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Private dependent"},
            headers=self.headers,
        )
        other_task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Other prerequisite"},
            headers=self.other_headers,
        )

        response = self.client.post(
            f"/api/v1/tasks/{own_task_response.json()['id']}/dependencies",
            json={"prerequisite_task_id": other_task_response.json()["id"]},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")

    def test_goal_detail_user_isolation(self):
        goal_response = self.client.post(
            "/api/v1/goals",
            json={"title": "Private Goal Detail"},
            headers=self.headers,
        )
        goal_id = goal_response.json()["id"]

        response = self.client.get(f"/api/v1/goals/{goal_id}/detail", headers=self.other_headers)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")

    def test_goals_home_returns_summary_and_filter_results(self):
        due_date = (date.today() + timedelta(days=2)).isoformat()
        goal_response = self.client.post(
            "/api/v1/goals",
            json={"title": "Goals Home API", "deadline": due_date, "value_level": "high"},
            headers=self.headers,
        )
        goal_id = goal_response.json()["id"]
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Next goal task", "goal_id": goal_id, "priority": 1, "value_level": "high"},
            headers=self.headers,
        )
        other_goal_response = self.client.post(
            "/api/v1/goals",
            json={"title": "Other user goal"},
            headers=self.other_headers,
        )

        response = self.client.get("/api/v1/goals/home?filter=due_soon", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["selected_filter"], "due_soon")
        self.assertEqual(body["summary"]["total_goal_count"], 1)
        self.assertEqual(body["filters"]["due_soon"], 1)
        self.assertEqual(len(body["goals"]), 1)
        self.assertEqual(body["goals"][0]["id"], goal_id)
        self.assertEqual(body["goals"][0]["recommended_next_task_id"], task_response.json()["id"])
        self.assertNotEqual(body["goals"][0]["id"], other_goal_response.json()["id"])

    def test_breakdown_task_returns_ai_job_and_created_steps(self):
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Break down by API", "estimated_duration_min": 70},
            headers=self.headers,
        )
        task_id = task_response.json()["id"]

        breakdown_response = self.client.post(f"/api/v1/tasks/{task_id}/breakdown", headers=self.headers)
        job_id = breakdown_response.json()["ai_job"]["id"]
        job_response = self.client.get(f"/api/v1/ai-jobs/{job_id}", headers=self.headers)
        detail_response = self.client.get(f"/api/v1/tasks/{task_id}", headers=self.headers)

        self.assertEqual(breakdown_response.status_code, 200)
        self.assertEqual(breakdown_response.json()["ai_job"]["status"], "succeeded_with_fallback")
        self.assertEqual(len(breakdown_response.json()["created_steps"]), 4)
        self.assertEqual(job_response.status_code, 200)
        self.assertEqual(job_response.json()["id"], job_id)
        self.assertEqual(job_response.json()["job_type"], "task_breakdown")
        self.assertEqual(len(detail_response.json()["steps"]), 4)

    def test_ai_job_user_isolation(self):
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Private breakdown"},
            headers=self.headers,
        )
        task_id = task_response.json()["id"]
        breakdown_response = self.client.post(f"/api/v1/tasks/{task_id}/breakdown", headers=self.headers)
        job_id = breakdown_response.json()["ai_job"]["id"]

        response = self.client.get(f"/api/v1/ai-jobs/{job_id}", headers=self.other_headers)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")

    def test_completed_task_cannot_be_broken_down(self):
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Do not split after done"},
            headers=self.headers,
        )
        task_id = task_response.json()["id"]
        self.client.post(f"/api/v1/tasks/{task_id}/complete", headers=self.headers)

        response = self.client.post(f"/api/v1/tasks/{task_id}/breakdown", headers=self.headers)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "INVALID_STATE")

    def test_user_id_isolation(self):
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Private task"},
            headers=self.headers,
        )
        self.assertEqual(task_response.status_code, 201)
        task_id = task_response.json()["id"]

        forbidden_response = self.client.get(f"/api/v1/tasks/{task_id}", headers=self.other_headers)

        self.assertEqual(forbidden_response.status_code, 404)
        self.assertEqual(forbidden_response.json()["error"]["code"], "NOT_FOUND")

    def test_task_source_cannot_be_spoofed_by_client(self):
        response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Pretend AI made this", "source": "ai"},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "REQUEST_VALIDATION_ERROR")

    def test_invalid_state_returns_error_payload(self):
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Complete then postpone"},
            headers=self.headers,
        )
        task_id = task_response.json()["id"]
        self.client.post(f"/api/v1/tasks/{task_id}/complete", headers=self.headers)

        response = self.client.post(f"/api/v1/tasks/{task_id}/postpone", headers=self.headers)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "INVALID_STATE")

    def test_repeated_complete_returns_invalid_state(self):
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Complete once"},
            headers=self.headers,
        )
        task_id = task_response.json()["id"]
        self.client.post(f"/api/v1/tasks/{task_id}/complete", headers=self.headers)

        response = self.client.post(f"/api/v1/tasks/{task_id}/complete", headers=self.headers)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "INVALID_STATE")

    def test_completed_task_cannot_create_or_complete_steps(self):
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Lock steps after complete"},
            headers=self.headers,
        )
        task_id = task_response.json()["id"]
        step_response = self.client.post(
            f"/api/v1/tasks/{task_id}/steps",
            json={"title": "Existing step"},
            headers=self.headers,
        )
        step_id = step_response.json()["id"]
        self.client.post(f"/api/v1/tasks/{task_id}/complete", headers=self.headers)

        create_step_response = self.client.post(
            f"/api/v1/tasks/{task_id}/steps",
            json={"title": "Too late"},
            headers=self.headers,
        )
        complete_step_response = self.client.post(
            f"/api/v1/tasks/{task_id}/steps/{step_id}/complete",
            headers=self.headers,
        )

        self.assertEqual(create_step_response.status_code, 400)
        self.assertEqual(create_step_response.json()["error"]["code"], "INVALID_STATE")
        self.assertEqual(complete_step_response.status_code, 400)
        self.assertEqual(complete_step_response.json()["error"]["code"], "INVALID_STATE")

    def test_goal_list_supports_pagination(self):
        for title in ("Goal A", "Goal B", "Goal C"):
            response = self.client.post("/api/v1/goals", json={"title": title}, headers=self.headers)
            self.assertEqual(response.status_code, 201)

        response = self.client.get("/api/v1/goals?limit=1&offset=1", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_missing_user_id_returns_error_payload(self):
        response = self.client.get("/api/v1/goals")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "MISSING_USER_ID")

    def test_request_validation_returns_error_payload(self):
        response = self.client.post("/api/v1/tasks", json={}, headers=self.headers)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "REQUEST_VALIDATION_ERROR")


if __name__ == "__main__":
    unittest.main()
