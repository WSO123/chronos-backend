from __future__ import annotations

from datetime import date, timedelta
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.data_source import DataSourceConnection
from app.models.energy import EnergyDailyMetric
from app.models.enums import DataSourceType
from app.models.user import User
from app.services.errors import NotFoundError, ValidationDomainError
from app.services.report_service import report_service


class EnergyService:
    allowed_sources = {"manual", "health_import", "estimated"}

    def upsert_daily_metric(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        payload: dict,
    ) -> EnergyDailyMetric:
        self._ensure_user(db, user_id=user_id)
        self._validate_payload(payload)
        connection_id = payload.get("data_source_connection_id")
        if connection_id is not None:
            self._ensure_health_connection(db, user_id=user_id, connection_id=connection_id)

        metric = self._metric_for_date(db, user_id=user_id, metric_date=payload["metric_date"])
        if metric is None:
            metric = EnergyDailyMetric(user_id=user_id, metric_date=payload["metric_date"])
            db.add(metric)

        metric.data_source_connection_id = connection_id
        metric.source = payload.get("source") or "manual"
        metric.sleep_minutes = payload.get("sleep_minutes")
        metric.sleep_quality_score = payload.get("sleep_quality_score")
        metric.stress_score = payload.get("stress_score")
        metric.energy_score = (
            payload["energy_score"]
            if payload.get("energy_score") is not None
            else self._derive_energy_score(payload)
        )
        metric.note = payload.get("note")
        metric.metric_metadata = payload.get("metric_metadata") or {}
        db.commit()
        db.refresh(metric)
        return metric

    def get_dashboard(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        end_date: date | None = None,
        days: int = 7,
    ) -> dict:
        self._ensure_user(db, user_id=user_id)
        days = min(max(days, 1), 31)
        resolved_end = report_service.resolve_report_date(db, user_id=user_id, report_date=end_date)
        start_date = resolved_end - timedelta(days=days - 1)
        metrics = self._metrics_between(db, user_id=user_id, start_date=start_date, end_date=resolved_end)
        by_date = {metric.metric_date: metric for metric in metrics}
        trends = [
            self._trend_day(day, by_date.get(day))
            for day in (start_date + timedelta(days=offset) for offset in range(days))
        ]
        today_metric = by_date.get(resolved_end)
        summary = self._summary(resolved_end, today_metric)
        return {
            "start_date": start_date,
            "end_date": resolved_end,
            "summary": summary,
            "trends": trends,
            "task_match": self._task_match(summary),
            "suggestions": self._suggestions(summary),
        }

    def to_response(self, metric: EnergyDailyMetric) -> dict:
        return {
            "id": metric.id,
            "created_at": metric.created_at,
            "updated_at": metric.updated_at,
            "user_id": metric.user_id,
            "data_source_connection_id": metric.data_source_connection_id,
            "metric_date": metric.metric_date,
            "source": metric.source,
            "sleep_minutes": metric.sleep_minutes,
            "sleep_quality_score": metric.sleep_quality_score,
            "stress_score": metric.stress_score,
            "energy_score": metric.energy_score,
            "energy_level": self.energy_level(metric.energy_score),
            "note": metric.note,
            "metric_metadata": metric.metric_metadata,
        }

    def energy_level(self, energy_score: int | None) -> str:
        if energy_score is None:
            return "unknown"
        if energy_score < 45:
            return "low"
        if energy_score < 75:
            return "medium"
        return "high"

    def _ensure_user(self, db: Session, *, user_id: uuid.UUID) -> User:
        user = db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    def _ensure_health_connection(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        connection_id: uuid.UUID,
    ) -> DataSourceConnection:
        connection = db.get(DataSourceConnection, connection_id)
        if connection is None or connection.user_id != user_id:
            raise NotFoundError("Data source connection not found")
        if connection.source_type != DataSourceType.HEALTH:
            raise ValidationDomainError("Energy metrics can only link to health data source connections")
        return connection

    def _validate_payload(self, payload: dict) -> None:
        source = payload.get("source") or "manual"
        if source not in self.allowed_sources:
            raise ValidationDomainError(f"Energy metric source {source} is not supported")
        has_metric = any(
            payload.get(field) is not None
            for field in ("sleep_minutes", "sleep_quality_score", "stress_score", "energy_score")
        )
        if not has_metric:
            raise ValidationDomainError("At least one energy metric value is required")

    def _metric_for_date(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        metric_date: date,
    ) -> EnergyDailyMetric | None:
        stmt = select(EnergyDailyMetric).where(
            EnergyDailyMetric.user_id == user_id,
            EnergyDailyMetric.metric_date == metric_date,
        )
        return db.scalars(stmt).first()

    def _metrics_between(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> list[EnergyDailyMetric]:
        stmt = (
            select(EnergyDailyMetric)
            .where(
                EnergyDailyMetric.user_id == user_id,
                EnergyDailyMetric.metric_date >= start_date,
                EnergyDailyMetric.metric_date <= end_date,
            )
            .order_by(EnergyDailyMetric.metric_date)
        )
        return list(db.scalars(stmt).all())

    def _derive_energy_score(self, payload: dict) -> int | None:
        if payload.get("energy_score") is not None:
            return payload["energy_score"]

        score = 65.0
        sleep_minutes = payload.get("sleep_minutes")
        sleep_quality_score = payload.get("sleep_quality_score")
        stress_score = payload.get("stress_score")
        if sleep_minutes is not None:
            if sleep_minutes < 360:
                score -= 18
            elif sleep_minutes < 420:
                score -= 8
            elif sleep_minutes <= 540:
                score += 8
            elif sleep_minutes > 600:
                score -= 4
        if sleep_quality_score is not None:
            score += (sleep_quality_score - 70) * 0.25
        if stress_score is not None:
            score += (50 - stress_score) * 0.35
        return max(0, min(round(score), 100))

    def _trend_day(self, day: date, metric: EnergyDailyMetric | None) -> dict:
        if metric is None:
            return {
                "date": day,
                "sleep_minutes": None,
                "sleep_quality_score": None,
                "stress_score": None,
                "energy_score": None,
                "energy_level": "unknown",
                "has_data": False,
            }
        return {
            "date": day,
            "sleep_minutes": metric.sleep_minutes,
            "sleep_quality_score": metric.sleep_quality_score,
            "stress_score": metric.stress_score,
            "energy_score": metric.energy_score,
            "energy_level": self.energy_level(metric.energy_score),
            "has_data": True,
        }

    def _summary(self, summary_date: date, metric: EnergyDailyMetric | None) -> dict:
        if metric is None:
            return {
                "date": summary_date,
                "energy_score": None,
                "energy_level": "unknown",
                "sleep_minutes": None,
                "sleep_quality_score": None,
                "stress_score": None,
                "status_message": "No energy data yet.",
            }
        level = self.energy_level(metric.energy_score)
        messages = {
            "low": "Energy looks low. Keep the plan lighter and protect only the essential work.",
            "medium": "Energy looks workable. Keep a steady sequence and avoid overloading the day.",
            "high": "Energy looks strong. This is a good day for deeper high-value work.",
            "unknown": "Energy is not clear yet.",
        }
        return {
            "date": summary_date,
            "energy_score": metric.energy_score,
            "energy_level": level,
            "sleep_minutes": metric.sleep_minutes,
            "sleep_quality_score": metric.sleep_quality_score,
            "stress_score": metric.stress_score,
            "status_message": messages[level],
        }

    def _task_match(self, summary: dict) -> dict:
        level = summary["energy_level"]
        stress_score = summary["stress_score"]
        if level == "high" and (stress_score is None or stress_score < 65):
            return {
                "recommended_mode": "deep_work",
                "reason": "Energy is high enough for focused high-value tasks.",
            }
        if level == "low" or (stress_score is not None and stress_score >= 75):
            return {
                "recommended_mode": "light",
                "reason": "Energy or stress suggests using a lighter execution sequence.",
            }
        return {
            "recommended_mode": "balanced",
            "reason": "Energy supports a normal plan without aggressive expansion.",
        }

    def _suggestions(self, summary: dict) -> list[dict]:
        if summary["energy_level"] == "unknown":
            return [
                {
                    "key": "no_energy_data",
                    "title": "Energy data is not ready",
                    "message": "Add a lightweight check-in or connect health data before using energy-aware planning.",
                    "signal": "neutral",
                }
            ]

        suggestions: list[dict] = []
        if summary["sleep_minutes"] is not None and summary["sleep_minutes"] < 360:
            suggestions.append(
                {
                    "key": "short_sleep",
                    "title": "Sleep was short",
                    "message": "Prefer a smaller plan and avoid stacking too many high-effort tasks.",
                    "signal": "risk",
                }
            )
        if summary["stress_score"] is not None and summary["stress_score"] >= 75:
            suggestions.append(
                {
                    "key": "high_stress",
                    "title": "Stress is elevated",
                    "message": "Use lighter tasks or shorter Focus blocks to keep the day sustainable.",
                    "signal": "risk",
                }
            )
        if summary["energy_level"] == "high":
            suggestions.append(
                {
                    "key": "protect_deep_work",
                    "title": "Protect deeper work",
                    "message": "This is a good window to move one high-value task forward.",
                    "signal": "positive",
                }
            )
        if not suggestions:
            suggestions.append(
                {
                    "key": "steady_day",
                    "title": "Keep a steady sequence",
                    "message": "A balanced plan is likely enough today.",
                    "signal": "neutral",
                }
            )
        return suggestions[:3]


energy_service = EnergyService()
