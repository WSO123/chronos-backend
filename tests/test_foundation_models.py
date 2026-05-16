import unittest

from app.core.db import Base
import app.models  # noqa: F401
from app.models.enums import AIJobStatus, TaskStatus, ValueLevel


class FoundationModelTests(unittest.TestCase):
    def test_foundation_tables_are_registered(self):
        expected_tables = {
            "users",
            "user_settings",
            "goals",
            "tasks",
            "task_steps",
            "activity_events",
            "ai_jobs",
        }

        self.assertTrue(expected_tables.issubset(set(Base.metadata.tables.keys())))

    def test_core_enum_values_match_docs(self):
        self.assertEqual(TaskStatus.ACTIVE.value, "active")
        self.assertEqual(TaskStatus.IN_FOCUS.value, "in_focus")
        self.assertEqual(AIJobStatus.SUCCEEDED_WITH_FALLBACK.value, "succeeded_with_fallback")
        self.assertEqual(ValueLevel.HIGH.value, "high")


if __name__ == "__main__":
    unittest.main()
