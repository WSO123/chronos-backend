import unittest

from app.services.activity_event_service import activity_event_service
from app.services.ai_job_service import ai_job_service
from app.services.goal_service import goal_service
from app.services.task_service import task_service


class FoundationServiceTests(unittest.TestCase):
    def test_service_singletons_are_importable(self):
        self.assertIsNotNone(activity_event_service)
        self.assertIsNotNone(ai_job_service)
        self.assertIsNotNone(goal_service)
        self.assertIsNotNone(task_service)


if __name__ == "__main__":
    unittest.main()
