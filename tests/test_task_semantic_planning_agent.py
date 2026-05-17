import unittest

from app.ai.agents.task_semantic_planning import TaskSemanticPlanningAgent
from app.ai.prompts.registry import prompt_registry


class TaskSemanticPlanningAgentTests(unittest.TestCase):
    def test_agent_returns_structured_semantic_signal_with_mock_provider(self):
        agent = TaskSemanticPlanningAgent()

        result = agent.run(
            task_context={
                "task_id": "task-1",
                "title": "写完高价值目标方案",
                "priority": 4,
                "value_level": "medium",
                "goal": {"title": "Launch MVP", "value_level": "high"},
            },
            fallback_output={
                "task_type": "writing",
                "complexity": "high",
                "cognitive_load": "high",
                "energy_fit": "high_energy",
                "blocking_risk": "high",
                "estimated_duration_min": 60,
                "duration_confidence": 0.72,
                "goal_alignment_score": 0.92,
                "semantic_priority_score": 0.88,
                "breakdown_recommended": True,
                "minimum_viable_step": "先写出方案的核心判断",
                "semantic_summary": "该任务直接推进高价值目标。",
                "confidence": 0.81,
            },
        )

        self.assertEqual(result.output.task_type, "writing")
        self.assertEqual(result.output.complexity, "high")
        self.assertEqual(result.output.goal_alignment_score, 0.92)
        self.assertEqual(result.provider, "mock")
        self.assertEqual(result.prompt_version, "p2-task-semantic-planning-agent-v1")
        self.assertEqual(len(result.prompt_checksum), 64)

    def test_prompt_registry_loads_task_semantic_planning_prompt(self):
        template = prompt_registry.get("task_semantic_planning")

        self.assertEqual(template.key, "task_semantic_planning")
        self.assertEqual(template.version, "p2-task-semantic-planning-agent-v1")
        self.assertIn("语义信号", template.content)


if __name__ == "__main__":
    unittest.main()
