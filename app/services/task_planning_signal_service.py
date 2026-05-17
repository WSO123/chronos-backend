from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
from time import perf_counter
import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.ai.agents.task_semantic_planning import (
    TaskSemanticPlanningAgent,
    task_semantic_planning_agent,
)
from app.ai.providers.base import LLMProviderError, empty_llm_usage
from app.ai.providers.registry import llm_provider_registry
from app.ai.schemas.task_semantic_planning import TaskSemanticPlanningOutput
from app.models.ai_job import AIJob
from app.models.enums import AIJobStatus, AIJobType, EntityType, TaskStatus, ValueLevel
from app.models.mixins import utc_now
from app.models.task import Task
from app.models.task_dependency import TaskDependency
from app.models.task_planning_signal import TaskPlanningSignal
from app.services.activity_event_service import activity_event_service
from app.services.ai_job_service import ai_job_service
from app.services.errors import InvalidStateError, NotFoundError


class TaskPlanningSignalService:
    def __init__(self, *, agent: TaskSemanticPlanningAgent | None = None) -> None:
        self.agent = agent or task_semantic_planning_agent

    def latest_signal(self, db: Session, *, task_id: uuid.UUID, user_id: uuid.UUID) -> TaskPlanningSignal | None:
        stmt = (
            select(TaskPlanningSignal)
            .where(TaskPlanningSignal.user_id == user_id, TaskPlanningSignal.task_id == task_id)
            .order_by(TaskPlanningSignal.created_at.desc(), TaskPlanningSignal.id.desc())
        )
        return db.scalars(stmt).first()

    def latest_signal_freshness(self, db: Session, *, task_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        task = self._get_user_task(db, task_id=task_id, user_id=user_id)
        signal = self.latest_signal(db, task_id=task_id, user_id=user_id)
        if signal is None:
            return {"signal": None, "is_fresh": False, "reason": "missing"}
        freshness = self.signal_freshness(db, task=task, signal=signal)
        return {"signal": signal, **freshness}

    def signal_freshness(self, db: Session, *, task: Task, signal: TaskPlanningSignal) -> dict:
        stored_signature = (signal.raw_payload or {}).get("_input_signature")
        current_signature = self._input_signature(db, task=task)
        if stored_signature:
            if stored_signature == current_signature:
                return {"is_fresh": True, "reason": "signature_match"}
            return {"is_fresh": False, "reason": "task_context_changed"}

        if self._created_after_context_update(db, task=task, signal=signal):
            return {"is_fresh": True, "reason": "legacy_timestamp_fresh"}
        return {"is_fresh": False, "reason": "legacy_context_changed"}

    def generate_signal(self, db: Session, *, task_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        task = self._get_user_task(db, task_id=task_id, user_id=user_id)
        if task.status == TaskStatus.ARCHIVED:
            raise InvalidStateError("archived task cannot generate planning signal")

        provider = llm_provider_registry.current_provider()
        job = ai_job_service.create_job(
            db,
            user_id=user_id,
            job_type=AIJobType.TASK_SEMANTIC_PLANNING,
            input_entity_type=EntityType.TASK.value,
            input_entity_id=task.id,
            provider=provider.provider_name,
            model=provider.model_name,
            prompt_version=self.agent.prompt_version,
            metadata={
                "mode": "sync_structured_agent",
                "prompt_checksum": self.agent.prompt_checksum,
                "fallback_generator": "rule-task-semantic-planning-v1",
            },
            commit=False,
        )
        job.status = AIJobStatus.RUNNING
        job.started_at = utc_now()
        started = perf_counter()

        try:
            agent_result = self.agent.run(
                task_context=self._task_context(db, task=task),
                fallback_output=self._fallback_output(db, task=task),
                provider=provider,
            )
            signal = self._create_signal(
                db,
                task=task,
                job=job,
                output=self._clean_output(agent_result.output),
                source="ai",
            )
            job.provider = agent_result.provider
            job.model = agent_result.model
            job.prompt_version = agent_result.prompt_version
            job.status = AIJobStatus.SUCCEEDED
            job.job_metadata = {
                **job.job_metadata,
                "output_applied": True,
                "confidence": agent_result.output.confidence,
                "prompt_checksum": agent_result.prompt_checksum,
                "provider_response_id": agent_result.response_id,
                "usage": agent_result.usage,
            }
        except Exception as exc:  # noqa: BLE001 - planning should still get a bounded signal.
            output = TaskSemanticPlanningOutput.model_validate(self._fallback_output(db, task=task))
            signal = self._create_signal(
                db,
                task=task,
                job=job,
                output=output,
                source="rule",
            )
            job.status = AIJobStatus.SUCCEEDED_WITH_FALLBACK
            job.error_message = str(exc)
            job.job_metadata = {
                **job.job_metadata,
                "output_applied": False,
                "fallback_reason": self._fallback_reason(exc),
                "fallback_error_type": exc.__class__.__name__,
                "fallback_root_error_type": self._root_error_type(exc),
                "failure_type": self._failure_type(exc),
            }

        job.result_entity_type = EntityType.TASK_PLANNING_SIGNAL.value
        job.result_entity_id = signal.id
        job.finished_at = utc_now()
        job.latency_ms = max(0, int((perf_counter() - started) * 1000))
        job.job_metadata = {
            **job.job_metadata,
            "task_planning_signal_id": str(signal.id),
            "provider_latency_ms": job.latency_ms,
            "provider_observability_version": "v1",
            "usage": self._usage_metadata(job.job_metadata.get("usage")),
        }
        activity_event_service.add_event(
            db,
            user_id=task.user_id,
            entity_type=EntityType.TASK,
            entity_id=task.id,
            event_type="TASK_PLANNING_SIGNAL_GENERATED",
            related_task_id=task.id,
            payload={
                "ai_job_id": str(job.id),
                "task_planning_signal_id": str(signal.id),
                "ai_job_status": job.status.value,
                "output_applied": job.job_metadata.get("output_applied"),
                "fallback_reason": job.job_metadata.get("fallback_reason"),
            },
        )
        db.commit()
        db.refresh(signal)
        db.refresh(job)
        return {"ai_job": self.ai_job_summary(job), "planning_signal": self.signal_summary(signal)}

    def signal_summary(self, signal: TaskPlanningSignal | None) -> dict | None:
        if signal is None:
            return None
        return {
            "id": signal.id,
            "task_id": signal.task_id,
            "ai_job_id": signal.ai_job_id,
            "source": signal.source,
            "task_type": signal.task_type,
            "complexity": signal.complexity,
            "cognitive_load": signal.cognitive_load,
            "energy_fit": signal.energy_fit,
            "blocking_risk": signal.blocking_risk,
            "estimated_duration_min": signal.estimated_duration_min,
            "duration_confidence": signal.duration_confidence,
            "goal_alignment_score": signal.goal_alignment_score,
            "semantic_priority_score": signal.semantic_priority_score,
            "breakdown_recommended": signal.breakdown_recommended,
            "minimum_viable_step": signal.minimum_viable_step,
            "semantic_summary": signal.semantic_summary,
            "confidence": signal.confidence,
            "created_at": signal.created_at,
        }

    def ai_job_summary(self, job: AIJob) -> dict:
        return {
            "id": job.id,
            "job_type": job.job_type,
            "status": job.status,
            "result_entity_type": job.result_entity_type,
            "result_entity_id": job.result_entity_id,
            "error_message": job.error_message,
            "provider": job.provider,
            "model": job.model,
            "prompt_version": job.prompt_version,
            "job_metadata": job.job_metadata,
        }

    def _create_signal(
        self,
        db: Session,
        *,
        task: Task,
        job: AIJob,
        output: TaskSemanticPlanningOutput,
        source: str,
    ) -> TaskPlanningSignal:
        payload = output.model_dump()
        payload["_input_signature"] = self._input_signature(db, task=task)
        payload["_input_signature_version"] = "task-semantic-planning-input-v1"
        signal = TaskPlanningSignal(
            user_id=task.user_id,
            task_id=task.id,
            ai_job_id=job.id,
            source=source,
            task_type=output.task_type,
            complexity=output.complexity,
            cognitive_load=output.cognitive_load,
            energy_fit=output.energy_fit,
            blocking_risk=output.blocking_risk,
            estimated_duration_min=output.estimated_duration_min,
            duration_confidence=output.duration_confidence,
            goal_alignment_score=output.goal_alignment_score,
            semantic_priority_score=output.semantic_priority_score,
            breakdown_recommended=output.breakdown_recommended,
            minimum_viable_step=output.minimum_viable_step,
            semantic_summary=output.semantic_summary,
            confidence=output.confidence,
            raw_payload=payload,
        )
        db.add(signal)
        db.flush()
        return signal

    def _clean_output(self, output: TaskSemanticPlanningOutput) -> TaskSemanticPlanningOutput:
        payload = output.model_dump()
        payload["task_type"] = " ".join(payload["task_type"].strip().split())[:64] or "general"
        if payload["minimum_viable_step"] is not None:
            payload["minimum_viable_step"] = " ".join(payload["minimum_viable_step"].strip().split())[:255] or None
        payload["semantic_summary"] = " ".join(payload["semantic_summary"].strip().split())[:500]
        if not payload["semantic_summary"]:
            payload["semantic_summary"] = "已生成任务语义规划信号。"
        return TaskSemanticPlanningOutput.model_validate(payload)

    def _task_context(self, db: Session, *, task: Task) -> dict:
        dependencies = self._dependency_counts(db, task=task)
        return {
            "task_id": str(task.id),
            "title": task.title,
            "description": task.description,
            "estimated_duration_min": task.estimated_duration_min,
            "actual_duration_min": task.actual_duration_min,
            "priority": task.priority,
            "value_level": task.value_level.value,
            "deadline": task.deadline.isoformat() if task.deadline else None,
            "status": task.status.value,
            "progress": str(task.progress),
            "goal": self._goal_context(task),
            "step_count": len(task.steps),
            "incomplete_steps": [step.title for step in task.steps if not step.is_completed][:6],
            "dependency_counts": dependencies,
        }

    def _input_signature(self, db: Session, *, task: Task) -> str:
        payload = self._task_context(db, task=task)
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _created_after_context_update(self, db: Session, *, task: Task, signal: TaskPlanningSignal) -> bool:
        context_updated_at = self._context_updated_at(db, task=task)
        return self._comparable_datetime(signal.created_at) >= self._comparable_datetime(context_updated_at)

    def _context_updated_at(self, db: Session, *, task: Task) -> datetime:
        candidates = [task.updated_at]
        if task.goal is not None:
            candidates.append(task.goal.updated_at)
        candidates.extend(step.updated_at for step in task.steps)
        dependency_edges = db.scalars(
            select(TaskDependency).where(
                TaskDependency.user_id == task.user_id,
                or_(
                    TaskDependency.dependent_task_id == task.id,
                    TaskDependency.prerequisite_task_id == task.id,
                ),
            )
        ).all()
        candidates.extend(edge.updated_at for edge in dependency_edges)
        return max(candidates, key=self._comparable_datetime)

    def _comparable_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def _goal_context(self, task: Task) -> dict | None:
        if task.goal is None:
            return None
        return {
            "goal_id": str(task.goal.id),
            "title": task.goal.title,
            "description": task.goal.description,
            "deadline": task.goal.deadline.isoformat() if task.goal.deadline else None,
            "value_level": task.goal.value_level.value,
            "status": task.goal.status.value,
        }

    def _fallback_output(self, db: Session, *, task: Task) -> dict:
        dependencies = self._dependency_counts(db, task=task)
        complexity = self._fallback_complexity(task)
        cognitive_load = self._fallback_cognitive_load(task, complexity=complexity)
        estimated_duration_min = task.estimated_duration_min or self._fallback_duration(complexity=complexity)
        goal_alignment_score = self._fallback_goal_alignment(task)
        semantic_priority_score = self._fallback_semantic_priority(
            task,
            goal_alignment_score=goal_alignment_score,
            dependency_counts=dependencies,
        )
        blocking_risk = self._fallback_blocking_risk(task, dependency_counts=dependencies)
        return {
            "task_type": self._fallback_task_type(task),
            "complexity": complexity,
            "cognitive_load": cognitive_load,
            "energy_fit": self._fallback_energy_fit(complexity=complexity, cognitive_load=cognitive_load),
            "blocking_risk": blocking_risk,
            "estimated_duration_min": estimated_duration_min,
            "duration_confidence": 0.78 if task.estimated_duration_min else 0.56,
            "goal_alignment_score": goal_alignment_score,
            "semantic_priority_score": semantic_priority_score,
            "breakdown_recommended": estimated_duration_min >= 45 or complexity == "high",
            "minimum_viable_step": self._minimum_viable_step(task),
            "semantic_summary": self._semantic_summary(
                task,
                complexity=complexity,
                goal_alignment_score=goal_alignment_score,
                blocking_risk=blocking_risk,
            ),
            "confidence": 0.66,
        }

    def _dependency_counts(self, db: Session, *, task: Task) -> dict:
        stmt = select(TaskDependency).where(TaskDependency.user_id == task.user_id)
        prerequisite_count = 0
        dependent_count = 0
        for edge in db.scalars(stmt).all():
            if edge.dependent_task_id == task.id:
                prerequisite_count += 1
            if edge.prerequisite_task_id == task.id:
                dependent_count += 1
        return {"prerequisite_count": prerequisite_count, "dependent_count": dependent_count}

    def _fallback_task_type(self, task: Task) -> str:
        text = f"{task.title} {task.description or ''}".lower()
        if any(keyword in text for keyword in ["写", "draft", "write", "文档", "文章", "方案"]):
            return "writing"
        if any(keyword in text for keyword in ["code", "api", "实现", "开发", "bug", "测试", "test"]):
            return "coding"
        if any(keyword in text for keyword in ["research", "调研", "分析", "阅读", "学习"]):
            return "research"
        if any(keyword in text for keyword in ["review", "检查", "复盘", "校对"]):
            return "review"
        if any(keyword in text for keyword in ["邮件", "email", "沟通", "同步", "会议"]):
            return "communication"
        if any(keyword in text for keyword in ["整理", "归档", "admin", "报销", "清理"]):
            return "admin"
        return "general"

    def _fallback_complexity(self, task: Task) -> str:
        text = f"{task.title} {task.description or ''}".lower()
        if task.estimated_duration_min and task.estimated_duration_min >= 75:
            return "high"
        if any(keyword in text for keyword in ["架构", "方案", "重构", "系统", "research", "分析", "实现"]):
            return "high"
        if task.estimated_duration_min and task.estimated_duration_min <= 25:
            return "low"
        if any(keyword in text for keyword in ["检查", "整理", "回复", "确认", "review"]):
            return "low"
        return "medium"

    def _fallback_cognitive_load(self, task: Task, *, complexity: str) -> str:
        if task.value_level == ValueLevel.HIGH or complexity == "high":
            return "high"
        if complexity == "low":
            return "low"
        return "medium"

    def _fallback_duration(self, *, complexity: str) -> int:
        return {"low": 25, "medium": 35, "high": 60}[complexity]

    def _fallback_goal_alignment(self, task: Task) -> float:
        if task.goal is None:
            return 0.45 if task.value_level == ValueLevel.HIGH else 0.3
        if task.goal.value_level == ValueLevel.HIGH:
            return 0.9
        if task.goal.value_level == ValueLevel.MEDIUM:
            return 0.68
        return 0.48

    def _fallback_semantic_priority(
        self,
        task: Task,
        *,
        goal_alignment_score: float,
        dependency_counts: dict,
    ) -> float:
        priority_score = max(0, 6 - task.priority) / 5
        value_score = {ValueLevel.HIGH: 1.0, ValueLevel.MEDIUM: 0.62, ValueLevel.LOW: 0.25}[task.value_level]
        deadline_score = self._deadline_signal(task.deadline)
        dependency_score = 0.82 if dependency_counts["dependent_count"] else 0.35
        score = (
            goal_alignment_score * 0.34
            + value_score * 0.24
            + priority_score * 0.16
            + deadline_score * 0.16
            + dependency_score * 0.10
        )
        return round(min(max(score, 0.0), 1.0), 2)

    def _deadline_signal(self, deadline: date | None) -> float:
        if deadline is None:
            return 0.25
        days = (deadline - utc_now().date()).days
        if days < 0:
            return 1.0
        if days == 0:
            return 0.9
        if days <= 3:
            return 0.72
        if days <= 7:
            return 0.5
        return 0.25

    def _fallback_blocking_risk(self, task: Task, *, dependency_counts: dict) -> str:
        if (
            dependency_counts["dependent_count"]
            or task.value_level == ValueLevel.HIGH
            or (task.goal is not None and task.goal.value_level == ValueLevel.HIGH)
        ):
            return "high"
        if task.goal is not None or task.priority <= 3:
            return "medium"
        return "low"

    def _fallback_energy_fit(self, *, complexity: str, cognitive_load: str) -> str:
        if complexity == "high" or cognitive_load == "high":
            return "high_energy"
        if complexity == "low" and cognitive_load == "low":
            return "low_energy"
        return "steady"

    def _minimum_viable_step(self, task: Task) -> str:
        incomplete_steps = sorted(
            [step for step in task.steps if not step.is_completed],
            key=lambda step: (step.sort_order, step.created_at),
        )
        if incomplete_steps:
            return incomplete_steps[0].title[:255]
        return f"先完成一个可验证的小结果：{task.title}"[:255]

    def _semantic_summary(
        self,
        task: Task,
        *,
        complexity: str,
        goal_alignment_score: float,
        blocking_risk: str,
    ) -> str:
        if goal_alignment_score >= 0.8:
            return f"该任务与高价值目标关联较强，复杂度为 {complexity}，应保护一个最小推进动作。"
        if blocking_risk == "high":
            return f"该任务可能影响后续推进，复杂度为 {complexity}，适合尽早厘清。"
        return f"该任务复杂度为 {complexity}，可作为今日计划的普通语义信号。"

    def _get_user_task(self, db: Session, *, task_id: uuid.UUID, user_id: uuid.UUID) -> Task:
        stmt = (
            select(Task)
            .options(selectinload(Task.goal), selectinload(Task.steps))
            .where(Task.id == task_id, Task.user_id == user_id)
        )
        task = db.scalars(stmt).first()
        if task is None:
            raise NotFoundError("Task not found")
        return task

    def _usage_metadata(self, usage: object) -> dict:
        if not isinstance(usage, dict):
            return empty_llm_usage()
        return {**empty_llm_usage(), **usage}

    def _fallback_reason(self, exc: Exception) -> str:
        if isinstance(exc, ValueError):
            return "task_semantic_planning_agent_invalid_output"
        return "task_semantic_planning_agent_failed"

    def _failure_type(self, exc: Exception) -> str:
        if isinstance(exc, ValueError):
            return "invalid_output"
        if isinstance(exc, LLMProviderError):
            return "provider_error"
        return "agent_error"

    def _root_error_type(self, exc: Exception) -> str:
        root = exc
        while root.__cause__ is not None:
            root = root.__cause__
        return root.__class__.__name__


task_planning_signal_service = TaskPlanningSignalService()
