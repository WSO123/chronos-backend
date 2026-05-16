from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy.orm import Session

from app.models.ai_job import AIJob
from app.models.enums import AIJobStatus, AIJobType
from app.models.mixins import utc_now


class AIJobService:
    def create_job(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        job_type: AIJobType,
        input_entity_type: str,
        input_entity_id: uuid.UUID,
        provider: str | None = None,
        model: str | None = None,
        prompt_version: str | None = None,
        metadata: dict | None = None,
    ) -> AIJob:
        job = AIJob(
            user_id=user_id,
            job_type=job_type,
            status=AIJobStatus.QUEUED,
            input_entity_type=input_entity_type,
            input_entity_id=input_entity_id,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            job_metadata=metadata or {},
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def mark_running(
        self,
        db: Session,
        *,
        job_id: uuid.UUID,
        celery_task_id: str | None = None,
        started_at: datetime | None = None,
    ) -> AIJob:
        job = self._get_job(db, job_id)
        job.status = AIJobStatus.RUNNING
        job.celery_task_id = celery_task_id or job.celery_task_id
        job.started_at = started_at or utc_now()
        db.commit()
        db.refresh(job)
        return job

    def mark_succeeded(
        self,
        db: Session,
        *,
        job_id: uuid.UUID,
        result_entity_type: str | None = None,
        result_entity_id: uuid.UUID | None = None,
        latency_ms: int | None = None,
    ) -> AIJob:
        return self._finish_job(
            db,
            job_id=job_id,
            status=AIJobStatus.SUCCEEDED,
            result_entity_type=result_entity_type,
            result_entity_id=result_entity_id,
            latency_ms=latency_ms,
        )

    def mark_succeeded_with_fallback(
        self,
        db: Session,
        *,
        job_id: uuid.UUID,
        fallback_reason: str,
        result_entity_type: str | None = None,
        result_entity_id: uuid.UUID | None = None,
        latency_ms: int | None = None,
    ) -> AIJob:
        job = self._get_job(db, job_id)
        job.job_metadata = {**job.job_metadata, "fallback_reason": fallback_reason}
        return self._finish_job(
            db,
            job_id=job_id,
            status=AIJobStatus.SUCCEEDED_WITH_FALLBACK,
            result_entity_type=result_entity_type,
            result_entity_id=result_entity_id,
            latency_ms=latency_ms,
        )

    def mark_failed(
        self,
        db: Session,
        *,
        job_id: uuid.UUID,
        error_message: str,
        latency_ms: int | None = None,
    ) -> AIJob:
        job = self._get_job(db, job_id)
        job.error_message = error_message
        return self._finish_job(
            db,
            job_id=job_id,
            status=AIJobStatus.FAILED,
            latency_ms=latency_ms,
        )

    def retry_job(self, db: Session, *, job_id: uuid.UUID) -> AIJob:
        job = self._get_job(db, job_id)
        if job.status not in {AIJobStatus.FAILED, AIJobStatus.SUCCEEDED_WITH_FALLBACK}:
            raise ValueError("Only failed or fallback jobs can be retried")

        job.status = AIJobStatus.QUEUED
        job.retry_count += 1
        job.error_message = None
        job.started_at = None
        job.finished_at = None
        db.commit()
        db.refresh(job)
        return job

    def _finish_job(
        self,
        db: Session,
        *,
        job_id: uuid.UUID,
        status: AIJobStatus,
        result_entity_type: str | None = None,
        result_entity_id: uuid.UUID | None = None,
        latency_ms: int | None = None,
    ) -> AIJob:
        job = self._get_job(db, job_id)
        job.status = status
        job.result_entity_type = result_entity_type
        job.result_entity_id = result_entity_id
        job.latency_ms = latency_ms
        job.finished_at = utc_now()
        db.commit()
        db.refresh(job)
        return job

    def _get_job(self, db: Session, job_id: uuid.UUID) -> AIJob:
        job = db.get(AIJob, job_id)
        if job is None:
            raise ValueError("AI job not found")
        return job


ai_job_service = AIJobService()
