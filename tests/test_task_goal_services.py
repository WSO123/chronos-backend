import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.models.activity_event import ActivityEvent
from app.models.enums import AIJobStatus, GoalHomeFilter, GoalStatus, TaskStatus, ValueLevel
from app.services.errors import InvalidStateError
from app.services.focus_service import focus_service
from app.services.goal_service import goal_service
from app.services.planning_service import planning_service
from app.services.task_service import task_service
from tests.db import TestingSessionLocal, reset_database
from tests.factories import create_user


class TaskGoalServiceTests(unittest.TestCase):
    def setUp(self):
        reset_database()
        self.db = TestingSessionLocal()
        self.user = create_user(self.db)

    def tearDown(self):
        self.db.close()

    def test_create_task_with_goal_and_complete_records_events(self):
        goal = goal_service.create_goal(
            self.db,
            user_id=self.user.id,
            title="Ship Chronos MVP",
            value_level=ValueLevel.HIGH,
        )
        task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=goal.id,
            title="Design Task API",
            value_level=ValueLevel.HIGH,
        )

        completed = task_service.complete_task(self.db, task_id=task.id, user_id=self.user.id)
        events = self.db.query(ActivityEvent).filter(ActivityEvent.related_task_id == task.id).all()

        self.assertEqual(completed.status, TaskStatus.COMPLETED)
        self.assertEqual(completed.progress, 1)
        self.assertIn("TASK_CREATED", {event.event_type for event in events})
        self.assertIn("TASK_COMPLETED", {event.event_type for event in events})

    def test_adjust_task_priority_records_user_correction_event(self):
        task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Protect this task",
            priority=5,
            value_level=ValueLevel.LOW,
        )

        result = task_service.adjust_task_priority(
            self.db,
            task_id=task.id,
            user_id=self.user.id,
            priority=1,
            value_level=ValueLevel.HIGH,
            reason="Actually important today",
        )
        events = task_service.list_task_events(self.db, task_id=task.id, user_id=self.user.id)

        self.assertEqual(result["previous_priority"], 5)
        self.assertEqual(result["current_priority"], 1)
        self.assertEqual(result["previous_value_level"], ValueLevel.LOW)
        self.assertEqual(result["current_value_level"], ValueLevel.HIGH)
        self.assertEqual(result["changed_fields"], ["priority", "value_level"])
        self.assertEqual(result["reason"], "Actually important today")
        self.assertIn("TASK_PRIORITY_ADJUSTED", [event.event_type for event in events])

    def test_postponing_completed_task_raises_invalid_state(self):
        task = task_service.create_task(self.db, user_id=self.user.id, title="Finish this")
        task_service.complete_task(self.db, task_id=task.id, user_id=self.user.id)

        with self.assertRaises(InvalidStateError):
            task_service.postpone_task(self.db, task_id=task.id, user_id=self.user.id)

    def test_completing_completed_task_raises_invalid_state(self):
        task = task_service.create_task(self.db, user_id=self.user.id, title="Finish once")
        task_service.complete_task(self.db, task_id=task.id, user_id=self.user.id)

        with self.assertRaises(InvalidStateError):
            task_service.complete_task(self.db, task_id=task.id, user_id=self.user.id)

    def test_create_and_complete_step_records_event(self):
        task = task_service.create_task(self.db, user_id=self.user.id, title="Break down")
        step = task_service.create_step(
            self.db,
            task_id=task.id,
            user_id=self.user.id,
            title="First step",
        )

        completed_step = task_service.complete_step(
            self.db,
            task_id=task.id,
            step_id=step.id,
            user_id=self.user.id,
        )
        events = task_service.list_task_events(self.db, task_id=task.id, user_id=self.user.id)

        self.assertTrue(completed_step.is_completed)
        self.assertIn("TASK_STEP_COMPLETED", [event.event_type for event in events])

    def test_task_detail_returns_light_execution_context(self):
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        goal = goal_service.create_goal(
            self.db,
            user_id=self.user.id,
            title="Launch MVP",
            value_level=ValueLevel.HIGH,
        )
        task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=goal.id,
            title="Write Task Detail",
            priority=1,
            value_level=ValueLevel.HIGH,
        )
        task_service.create_step(self.db, task_id=task.id, user_id=self.user.id, title="Return light context")
        planning_service.get_today(self.db, user_id=self.user.id, plan_date=today)

        detail = task_service.get_task_detail(self.db, task_id=task.id, user_id=self.user.id)

        self.assertEqual(detail["goal"]["title"], "Launch MVP")
        self.assertEqual(detail["ai_info"]["recommended_duration_min"], 25)
        self.assertEqual(detail["ai_info"]["execution_suggestion"], "Continue with: Return light context")
        self.assertIsNotNone(detail["today_context"])
        self.assertEqual(detail["today_context"]["plan_version"], 1)
        self.assertTrue(detail["actions"]["can_start_focus"])
        self.assertFalse(detail["focus_state"]["is_currently_focusing_this_task"])

    def test_task_detail_disables_start_focus_when_another_session_is_active(self):
        first = task_service.create_task(self.db, user_id=self.user.id, title="Currently focusing")
        second = task_service.create_task(self.db, user_id=self.user.id, title="Waiting task")
        session = focus_service.start_session(self.db, user_id=self.user.id, task_id=first.id)

        detail = task_service.get_task_detail(self.db, task_id=second.id, user_id=self.user.id)

        self.assertEqual(detail["focus_state"]["active_focus_session_id"], session.id)
        self.assertFalse(detail["focus_state"]["is_currently_focusing_this_task"])
        self.assertFalse(detail["actions"]["can_start_focus"])

    def test_goal_detail_returns_progress_task_groups_and_suggestion(self):
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        goal = goal_service.create_goal(
            self.db,
            user_id=self.user.id,
            title="Build Goal Detail",
            deadline=today + timedelta(days=2),
            value_level=ValueLevel.HIGH,
        )
        next_task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=goal.id,
            title="Implement aggregate",
            estimated_duration_min=40,
            priority=1,
            value_level=ValueLevel.HIGH,
        )
        completed_task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=goal.id,
            title="Write baseline",
            estimated_duration_min=20,
        )
        postponed_task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=goal.id,
            title="Polish later",
            estimated_duration_min=15,
        )
        task_service.create_step(self.db, task_id=next_task.id, user_id=self.user.id, title="Add schema")
        task_service.complete_task(self.db, task_id=completed_task.id, user_id=self.user.id)
        task_service.postpone_task(self.db, task_id=postponed_task.id, user_id=self.user.id)

        detail = goal_service.get_goal_detail(self.db, goal_id=goal.id, user_id=self.user.id)

        self.assertEqual(detail["overview"].id, goal.id)
        self.assertEqual(detail["progress"]["total_task_count"], 3)
        self.assertEqual(detail["progress"]["completed_task_count"], 1)
        self.assertEqual(detail["progress"]["unfinished_task_count"], 2)
        self.assertEqual(detail["progress"]["postponed_task_count"], 1)
        self.assertEqual(detail["progress"]["completion_rate"], 0.33)
        self.assertEqual(detail["progress"]["risk_level"], "at_risk")
        self.assertEqual(detail["task_list"]["recommended_next_task"]["id"], next_task.id)
        self.assertEqual(detail["task_list"]["unfinished_tasks"][0]["id"], next_task.id)
        self.assertEqual(detail["task_list"]["completed_tasks"][0]["id"], completed_task.id)
        self.assertEqual(detail["task_list"]["recommended_next_task"]["step_count"], 1)
        self.assertEqual(len(detail["dependency_map"]["nodes"]), 3)
        self.assertEqual(detail["dependency_map"]["edges"], [])
        self.assertEqual(detail["ai_suggestion"]["next_action_task_id"], next_task.id)
        self.assertFalse(detail["actions"]["can_mark_complete"])

    def test_task_dependencies_create_edges_and_goal_dependency_map(self):
        goal = goal_service.create_goal(self.db, user_id=self.user.id, title="Dependency goal")
        prerequisite = task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=goal.id,
            title="Prepare context",
        )
        dependent = task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=goal.id,
            title="Write final draft",
        )

        edge = task_service.add_task_dependency(
            self.db,
            task_id=dependent.id,
            user_id=self.user.id,
            prerequisite_task_id=prerequisite.id,
            reason="Context first",
        )
        dependencies = task_service.get_task_dependencies(self.db, task_id=dependent.id, user_id=self.user.id)
        task_detail = task_service.get_task_detail(self.db, task_id=dependent.id, user_id=self.user.id)
        goal_detail = goal_service.get_goal_detail(self.db, goal_id=goal.id, user_id=self.user.id)

        self.assertEqual(edge["prerequisite_task"]["task_id"], prerequisite.id)
        self.assertEqual(edge["dependent_task"]["task_id"], dependent.id)
        self.assertEqual(dependencies["prerequisites"][0]["reason"], "Context first")
        self.assertEqual(task_detail["dependency_info"]["prerequisites"][0]["id"], edge["id"])
        self.assertEqual(goal_detail["dependency_map"]["edges"][0]["from_task_id"], prerequisite.id)
        self.assertEqual(goal_detail["dependency_map"]["edges"][0]["to_task_id"], dependent.id)

    def test_task_dependency_rejects_cycles(self):
        first = task_service.create_task(self.db, user_id=self.user.id, title="First")
        second = task_service.create_task(self.db, user_id=self.user.id, title="Second")
        task_service.add_task_dependency(
            self.db,
            task_id=second.id,
            user_id=self.user.id,
            prerequisite_task_id=first.id,
        )

        with self.assertRaises(InvalidStateError):
            task_service.add_task_dependency(
                self.db,
                task_id=first.id,
                user_id=self.user.id,
                prerequisite_task_id=second.id,
            )

    def test_task_dependency_delete_returns_updated_dependency_state(self):
        prerequisite = task_service.create_task(self.db, user_id=self.user.id, title="Read brief")
        dependent = task_service.create_task(self.db, user_id=self.user.id, title="Write answer")
        edge = task_service.add_task_dependency(
            self.db,
            task_id=dependent.id,
            user_id=self.user.id,
            prerequisite_task_id=prerequisite.id,
        )

        updated = task_service.delete_task_dependency(
            self.db,
            task_id=dependent.id,
            user_id=self.user.id,
            prerequisite_task_id=prerequisite.id,
        )
        events = task_service.list_task_events(self.db, task_id=dependent.id, user_id=self.user.id)

        self.assertEqual(updated["task_id"], dependent.id)
        self.assertEqual(updated["prerequisites"], [])
        self.assertIn("TASK_DEPENDENCY_DELETED", [event.event_type for event in events])
        self.assertEqual(edge["dependent_task"]["task_id"], dependent.id)

    def test_completed_goal_detail_has_no_next_action(self):
        goal = goal_service.create_goal(self.db, user_id=self.user.id, title="Completed goal")
        task_service.create_task(self.db, user_id=self.user.id, goal_id=goal.id, title="Leftover task")
        goal_service.update_goal(
            self.db,
            goal_id=goal.id,
            user_id=self.user.id,
            updates={"status": GoalStatus.COMPLETED},
        )

        detail = goal_service.get_goal_detail(self.db, goal_id=goal.id, user_id=self.user.id)

        self.assertIsNone(detail["task_list"]["recommended_next_task"])
        self.assertIsNone(detail["ai_suggestion"]["next_action_task_id"])
        self.assertEqual(detail["ai_suggestion"]["summary"], "This goal is already complete.")

    def test_goal_progress_timeline_returns_key_milestones(self):
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        goal = goal_service.create_goal(
            self.db,
            user_id=self.user.id,
            title="Timeline goal",
            deadline=today + timedelta(days=5),
            value_level=ValueLevel.HIGH,
        )
        completed_task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=goal.id,
            title="Finished milestone",
        )
        postponed_task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=goal.id,
            title="Delayed milestone",
        )
        task_service.complete_task(self.db, task_id=completed_task.id, user_id=self.user.id)
        task_service.postpone_task(self.db, task_id=postponed_task.id, user_id=self.user.id)

        timeline = goal_service.get_goal_progress_timeline(self.db, goal_id=goal.id, user_id=self.user.id)
        milestone_types = [milestone["milestone_type"] for milestone in timeline["milestones"]]

        self.assertEqual(timeline["summary"]["total_task_count"], 2)
        self.assertEqual(timeline["summary"]["completed_task_count"], 1)
        self.assertEqual(timeline["summary"]["completion_rate"], 0.5)
        self.assertIn("goal_created", milestone_types)
        self.assertIn("task_added", milestone_types)
        self.assertIn("task_completed", milestone_types)
        self.assertIn("task_postponed", milestone_types)
        self.assertIn("deadline", milestone_types)
        self.assertEqual(timeline["note"], "Timeline is derived from goal and task activity events; it does not change Today ordering.")

    def test_goals_home_returns_summary_filters_and_goal_cards(self):
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        active_goal = goal_service.create_goal(
            self.db,
            user_id=self.user.id,
            title="Active high value goal",
            deadline=today + timedelta(days=3),
            value_level=ValueLevel.HIGH,
        )
        next_task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=active_goal.id,
            title="Next important step",
            priority=1,
            value_level=ValueLevel.HIGH,
        )
        done_task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=active_goal.id,
            title="Finished setup",
        )
        task_service.complete_task(self.db, task_id=done_task.id, user_id=self.user.id)
        completed_goal = goal_service.create_goal(self.db, user_id=self.user.id, title="Completed goal")
        completed_goal_task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=completed_goal.id,
            title="Completed goal task",
        )
        task_service.complete_task(self.db, task_id=completed_goal_task.id, user_id=self.user.id)
        goal_service.update_goal(
            self.db,
            goal_id=completed_goal.id,
            user_id=self.user.id,
            updates={"status": GoalStatus.COMPLETED},
        )
        archived_goal = goal_service.create_goal(self.db, user_id=self.user.id, title="Archived goal")
        goal_service.update_goal(
            self.db,
            goal_id=archived_goal.id,
            user_id=self.user.id,
            updates={"status": GoalStatus.ARCHIVED},
        )

        home = goal_service.get_goals_home(
            self.db,
            user_id=self.user.id,
            selected_filter=GoalHomeFilter.ACTIVE,
        )
        completed_home = goal_service.get_goals_home(
            self.db,
            user_id=self.user.id,
            selected_filter=GoalHomeFilter.COMPLETED,
        )

        self.assertEqual(home["summary"]["total_goal_count"], 2)
        self.assertEqual(home["summary"]["active_goal_count"], 1)
        self.assertEqual(home["summary"]["completed_goal_count"], 1)
        self.assertEqual(home["summary"]["due_soon_goal_count"], 1)
        self.assertEqual(home["summary"]["high_value_goal_count"], 1)
        self.assertEqual(home["summary"]["weekly_completed_task_count"], 2)
        self.assertEqual(home["summary"]["weekly_touched_goal_count"], 2)
        self.assertEqual(home["filters"]["all"], 2)
        self.assertEqual(home["filters"]["active"], 1)
        self.assertEqual(len(home["goals"]), 1)
        self.assertEqual(home["goals"][0]["id"], active_goal.id)
        self.assertEqual(home["goals"][0]["recommended_next_task_id"], next_task.id)
        self.assertEqual(home["goals"][0]["associated_task_count"], 2)
        self.assertEqual(completed_home["goals"][0]["id"], completed_goal.id)

    def test_breakdown_task_creates_rule_steps_and_ai_job(self):
        task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Break this into steps",
            estimated_duration_min=70,
        )

        result = task_service.breakdown_task(self.db, task_id=task.id, user_id=self.user.id)
        events = task_service.list_task_events(self.db, task_id=task.id, user_id=self.user.id)

        self.assertEqual(result["ai_job"]["status"], AIJobStatus.SUCCEEDED_WITH_FALLBACK)
        self.assertEqual(result["ai_job"]["job_metadata"]["fallback_reason"], "rule_mock_breakdown")
        self.assertEqual(len(result["created_steps"]), 4)
        self.assertEqual([step.sort_order for step in result["created_steps"]], [1, 2, 3, 4])
        self.assertIn("TASK_BREAKDOWN_GENERATED", [event.event_type for event in events])
        self.assertIn("TASK_STEP_CREATED", [event.event_type for event in events])

    def test_breakdown_task_preserves_existing_steps(self):
        task = task_service.create_task(self.db, user_id=self.user.id, title="Already split")
        existing_step = task_service.create_step(self.db, task_id=task.id, user_id=self.user.id, title="Keep this")

        result = task_service.breakdown_task(self.db, task_id=task.id, user_id=self.user.id)
        detail = task_service.get_task_detail(self.db, task_id=task.id, user_id=self.user.id)

        self.assertEqual(result["created_steps"], [])
        self.assertEqual(result["ai_job"]["job_metadata"]["fallback_reason"], "existing_steps_preserved")
        self.assertEqual(len(detail["steps"]), 1)
        self.assertEqual(detail["steps"][0].id, existing_step.id)

    def test_breakdown_completed_task_raises_invalid_state(self):
        task = task_service.create_task(self.db, user_id=self.user.id, title="Already done")
        task_service.complete_task(self.db, task_id=task.id, user_id=self.user.id)

        with self.assertRaises(InvalidStateError):
            task_service.breakdown_task(self.db, task_id=task.id, user_id=self.user.id)


if __name__ == "__main__":
    unittest.main()
