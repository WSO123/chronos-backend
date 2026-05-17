import unittest

from app.ai.providers.base import LLMProviderError
from app.models.activity_event import ActivityEvent
from app.models.ai_job import AIJob
from app.models.enums import InboxItemStatus, InboxItemType, TaskSource
from app.models.goal import Goal
from app.models.task import Task
from app.services.capture_service import CaptureService, capture_service
from app.services.errors import ValidationDomainError
from app.services.inbox_service import inbox_service
from tests.db import TestingSessionLocal, reset_database
from tests.factories import create_user


class FailingCaptureParserAgent:
    prompt_version = "test-capture-parser"
    prompt_checksum = "0" * 64

    def run(self, **kwargs):
        del kwargs
        raise LLMProviderError("provider unavailable")


class CaptureInboxServiceTests(unittest.TestCase):
    def setUp(self):
        reset_database()
        self.db = TestingSessionLocal()
        self.user = create_user(self.db)

    def tearDown(self):
        self.db.close()

    def test_text_capture_creates_parse_result_and_inbox_item(self):
        capture, parse_result, inbox_item = capture_service.create_text_capture(
            self.db,
            user_id=self.user.id,
            raw_text="完成 API 文档",
        )

        self.assertEqual(capture.status.value, "parsed")
        self.assertEqual(parse_result.result_type.value, "task")
        self.assertEqual(inbox_item.item_type, InboxItemType.TASK)
        self.assertEqual(inbox_item.status, InboxItemStatus.PENDING)

    def test_text_capture_records_capture_parser_ai_job(self):
        capture, parse_result, inbox_item = capture_service.create_text_capture(
            self.db,
            user_id=self.user.id,
            raw_text="完成 API 文档",
        )

        job = self.db.query(AIJob).one()

        self.assertEqual(job.job_type.value, "capture_parser")
        self.assertEqual(job.status.value, "succeeded")
        self.assertEqual(job.input_entity_id, capture.id)
        self.assertEqual(job.result_entity_type, "inbox")
        self.assertEqual(job.result_entity_id, inbox_item.id)
        self.assertEqual(job.provider, "mock")
        self.assertEqual(job.prompt_version, "p2-capture-parser-agent-v1")
        self.assertTrue(job.job_metadata["output_applied"])
        self.assertEqual(parse_result.raw_model_output["parser"], "llm_agent")
        self.assertEqual(parse_result.raw_model_output["ai_job_id"], str(job.id))
        self.assertEqual(parse_result.raw_model_output["output"]["result_type"], "task")

    def test_capture_parser_agent_failure_falls_back_to_rule_parser(self):
        service = CaptureService(parser_agent=FailingCaptureParserAgent())

        _, parse_result, inbox_item = service.create_text_capture(
            self.db,
            user_id=self.user.id,
            raw_text="完成 fallback 任务",
        )
        job = self.db.query(AIJob).one()

        self.assertEqual(parse_result.result_type.value, "task")
        self.assertEqual(inbox_item.item_type, InboxItemType.TASK)
        self.assertEqual(parse_result.raw_model_output["parser"], "rule")
        self.assertEqual(parse_result.raw_model_output["agent"]["status"], "fallback")
        self.assertEqual(job.status.value, "succeeded_with_fallback")
        self.assertEqual(job.job_metadata["failure_type"], "provider_error")
        self.assertFalse(job.job_metadata["output_applied"])

    def test_confirm_task_inbox_item_creates_task_and_events(self):
        _, _, inbox_item = capture_service.create_text_capture(
            self.db,
            user_id=self.user.id,
            raw_text="完成 Capture Inbox",
        )

        confirmed = inbox_service.confirm_item(self.db, item_id=inbox_item.id, user_id=self.user.id)
        task = self.db.get(Task, confirmed.result_entity_id)
        events = self.db.query(ActivityEvent).filter(ActivityEvent.user_id == self.user.id).all()

        self.assertEqual(confirmed.status, InboxItemStatus.CONFIRMED)
        self.assertEqual(confirmed.result_entity_type, "task")
        self.assertIsNotNone(task)
        self.assertEqual(task.source, TaskSource.CAPTURE)
        self.assertIn("INBOX_ITEM_CONFIRMED", {event.event_type for event in events})
        self.assertIn("TASK_CREATED", {event.event_type for event in events})

    def test_confirm_goal_inbox_item_creates_goal(self):
        _, _, inbox_item = capture_service.create_text_capture(
            self.db,
            user_id=self.user.id,
            raw_text="目标：上线 Chronos MVP",
        )

        confirmed = inbox_service.confirm_item(self.db, item_id=inbox_item.id, user_id=self.user.id)
        goal = self.db.get(Goal, confirmed.result_entity_id)

        self.assertEqual(confirmed.result_entity_type, "goal")
        self.assertIsNotNone(goal)

    def test_unknown_item_must_be_edited_before_confirm(self):
        _, _, inbox_item = capture_service.create_text_capture(
            self.db,
            user_id=self.user.id,
            raw_text="随便记一下",
        )

        with self.assertRaises(ValidationDomainError):
            inbox_service.confirm_item(self.db, item_id=inbox_item.id, user_id=self.user.id)

        edited = inbox_service.update_item(
            self.db,
            item_id=inbox_item.id,
            user_id=self.user.id,
            updates={"item_type": InboxItemType.TASK, "title": "整理随手记"},
        )
        confirmed = inbox_service.confirm_item(self.db, item_id=edited.id, user_id=self.user.id)

        self.assertEqual(confirmed.status, InboxItemStatus.CONFIRMED)
        self.assertEqual(confirmed.result_entity_type, "task")

    def test_confirmed_item_confirm_is_idempotent(self):
        _, _, inbox_item = capture_service.create_text_capture(
            self.db,
            user_id=self.user.id,
            raw_text="完成测试",
        )
        first_confirmed = inbox_service.confirm_item(self.db, item_id=inbox_item.id, user_id=self.user.id)

        second_confirmed = inbox_service.confirm_item(self.db, item_id=inbox_item.id, user_id=self.user.id)
        tasks = self.db.query(Task).filter(Task.user_id == self.user.id).all()
        events = self.db.query(ActivityEvent).filter(ActivityEvent.user_id == self.user.id).all()

        self.assertEqual(second_confirmed.result_entity_id, first_confirmed.result_entity_id)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(
            len([event for event in events if event.event_type == "INBOX_ITEM_CONFIRMED"]),
            1,
        )


if __name__ == "__main__":
    unittest.main()
