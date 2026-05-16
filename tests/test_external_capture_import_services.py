import unittest

from app.models.activity_event import ActivityEvent
from app.models.capture import CaptureInput
from app.models.enums import CaptureInputType, CaptureSource, DataSourceStatus, DataSourceType, TaskSource
from app.models.external_import import ExternalCaptureImport
from app.models.inbox import InboxItem
from app.models.task import Task
from app.services.data_source_service import data_source_service
from app.services.errors import InvalidStateError, ValidationDomainError
from app.services.external_capture_import_service import external_capture_import_service
from app.services.inbox_service import inbox_service
from tests.db import TestingSessionLocal, reset_database
from tests.factories import create_user


class ExternalCaptureImportServiceTests(unittest.TestCase):
    def setUp(self):
        reset_database()
        self.db = TestingSessionLocal()
        self.user = create_user(self.db)

    def tearDown(self):
        self.db.close()

    def test_calendar_import_creates_external_capture_and_inbox_item(self):
        connection = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.CALENDAR,
            provider="google_calendar",
        )

        result = external_capture_import_service.import_item(
            self.db,
            user_id=self.user.id,
            data_source_connection_id=connection.id,
            external_item_id="calendar-event-1",
            external_item_type="calendar_event",
            title="完成项目复盘",
            body="整理会议结论",
            external_payload={"html_link": "https://calendar.example/event"},
        )
        events = self.db.query(ActivityEvent).filter(ActivityEvent.user_id == self.user.id).all()

        self.assertTrue(result["created"])
        self.assertEqual(result["capture"].input_type, CaptureInputType.EXTERNAL)
        self.assertEqual(result["capture"].source, CaptureSource.CALENDAR)
        self.assertEqual(result["import_record"].capture_input_id, result["capture"].id)
        self.assertEqual(result["inbox_item"].title, "完成项目复盘")
        self.assertEqual(result["inbox_item"].description, "整理会议结论")
        self.assertIn("EXTERNAL_CAPTURE_IMPORTED", {event.event_type for event in events})

    def test_duplicate_external_item_is_idempotent(self):
        connection = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.EMAIL,
            provider="gmail",
        )

        first = external_capture_import_service.import_item(
            self.db,
            user_id=self.user.id,
            data_source_connection_id=connection.id,
            external_item_id="email-1",
            external_item_type="email_message",
            title="完成合同确认",
        )
        second = external_capture_import_service.import_item(
            self.db,
            user_id=self.user.id,
            data_source_connection_id=connection.id,
            external_item_id="email-1",
            external_item_type="email_message",
            title="完成合同确认",
        )

        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(second["import_record"].id, first["import_record"].id)
        self.assertEqual(self.db.query(ExternalCaptureImport).count(), 1)
        self.assertEqual(self.db.query(CaptureInput).count(), 1)
        self.assertEqual(self.db.query(InboxItem).count(), 1)

    def test_confirm_external_inbox_item_preserves_task_source(self):
        connection = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.CALENDAR,
            provider="google_calendar",
        )
        result = external_capture_import_service.import_item(
            self.db,
            user_id=self.user.id,
            data_source_connection_id=connection.id,
            external_item_id="calendar-event-2",
            external_item_type="calendar_event",
            title="完成发布准备",
        )

        confirmed = inbox_service.confirm_item(
            self.db,
            item_id=result["inbox_item"].id,
            user_id=self.user.id,
        )
        task = self.db.get(Task, confirmed.result_entity_id)

        self.assertIsNotNone(task)
        self.assertEqual(task.source, TaskSource.CALENDAR)

    def test_paused_source_cannot_import(self):
        connection = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.EMAIL,
            provider="gmail",
        )
        data_source_service.update_connection(
            self.db,
            connection_id=connection.id,
            user_id=self.user.id,
            updates={"status": DataSourceStatus.PAUSED},
        )

        with self.assertRaises(InvalidStateError):
            external_capture_import_service.import_item(
                self.db,
                user_id=self.user.id,
                data_source_connection_id=connection.id,
                external_item_id="email-2",
                external_item_type="email_message",
                title="完成邮件跟进",
            )

    def test_health_source_cannot_import_capture(self):
        connection = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.HEALTH,
            provider="apple_health",
        )

        with self.assertRaises(ValidationDomainError):
            external_capture_import_service.import_item(
                self.db,
                user_id=self.user.id,
                data_source_connection_id=connection.id,
                external_item_id="sleep-1",
                external_item_type="sleep_sample",
                title="Sleep sample",
            )

    def test_blank_external_item_id_is_rejected(self):
        connection = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.EMAIL,
            provider="gmail",
        )

        with self.assertRaises(ValidationDomainError):
            external_capture_import_service.import_item(
                self.db,
                user_id=self.user.id,
                data_source_connection_id=connection.id,
                external_item_id="   ",
                external_item_type="email_message",
                title="完成邮件跟进",
            )


if __name__ == "__main__":
    unittest.main()
