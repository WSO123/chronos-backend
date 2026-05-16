from __future__ import annotations

from datetime import UTC, date, timedelta
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import FocusSessionStatus
from app.models.focus_session import FocusSession
from app.services.report_service import report_service


class InsightService:
    def get_detail(self, db: Session, *, user_id: uuid.UUID, anchor_date: date | None = None) -> dict:
        resolved_anchor_date = report_service.resolve_report_date(db, user_id=user_id, report_date=anchor_date)
        period_start = resolved_anchor_date - timedelta(days=resolved_anchor_date.weekday())
        weekly_report = report_service.get_weekly_report(db, user_id=user_id, week_start=period_start)
        period_end = weekly_report["week_end"]
        summary = weekly_report["summary"]
        windows = self._efficiency_windows(
            db,
            user_id=user_id,
            period_start=period_start,
            period_end=period_end,
        )
        overview = {
            "average_completion_rate": summary["average_completion_rate"],
            "total_completed_task_count": summary["total_completed_task_count"],
            "high_value_completed_task_count": summary["high_value_completed_task_count"],
            "total_focus_minutes": summary["total_focus_minutes"],
            "overdue_task_count": summary["overdue_task_count"],
            "at_risk_goal_count": summary["at_risk_goal_count"],
        }
        patterns = self._behavior_patterns(summary=summary, windows=windows)
        recommendations = self._recommendations(summary=summary, windows=windows)
        return {
            "anchor_date": resolved_anchor_date,
            "period_start": weekly_report["week_start"],
            "period_end": period_end,
            "overview": overview,
            "behavior_patterns": patterns,
            "efficiency_windows": windows,
            "recommendations": recommendations,
            "strategy_notes": self._strategy_notes(summary=summary, windows=windows),
            "source": {
                "generated_by": "rule-insight-v1",
                "period_days": 7,
                "data_points": self._data_points(weekly_report=weekly_report, windows=windows),
            },
        }

    def _efficiency_windows(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        period_start: date,
        period_end: date,
    ) -> list[dict]:
        start_at, _ = report_service.date_bounds(db, user_id=user_id, target_date=period_start)
        _, end_at = report_service.date_bounds(db, user_id=user_id, target_date=period_end)
        timezone = report_service.user_timezone(db, user_id=user_id)
        buckets = [
            {"label": "morning", "start_hour": 5, "end_hour": 12, "focus_minutes": 0, "completed_focus_count": 0},
            {"label": "afternoon", "start_hour": 12, "end_hour": 18, "focus_minutes": 0, "completed_focus_count": 0},
            {"label": "evening", "start_hour": 18, "end_hour": 24, "focus_minutes": 0, "completed_focus_count": 0},
            {"label": "late_night", "start_hour": 0, "end_hour": 5, "focus_minutes": 0, "completed_focus_count": 0},
        ]
        stmt = select(FocusSession).where(
            FocusSession.user_id == user_id,
            FocusSession.status.in_(
                [
                    FocusSessionStatus.COMPLETED,
                    FocusSessionStatus.INTERRUPTED,
                    FocusSessionStatus.POSTPONED,
                ]
            ),
            FocusSession.ended_at >= start_at,
            FocusSession.ended_at < end_at,
        )
        for session in db.scalars(stmt).all():
            session_start = session.started_at
            if session_start.tzinfo is None:
                session_start = session_start.replace(tzinfo=UTC)
            hour = session_start.astimezone(timezone).hour
            bucket = self._bucket_for_hour(buckets, hour)
            bucket["focus_minutes"] += session.actual_duration_min
            if session.status == FocusSessionStatus.COMPLETED:
                bucket["completed_focus_count"] += 1

        max_focus_minutes = max((bucket["focus_minutes"] for bucket in buckets), default=0)
        return [
            {
                **bucket,
                "signal": self._window_signal(bucket=bucket, max_focus_minutes=max_focus_minutes),
            }
            for bucket in buckets
        ]

    def _bucket_for_hour(self, buckets: list[dict], hour: int) -> dict:
        for bucket in buckets:
            if bucket["start_hour"] <= hour < bucket["end_hour"]:
                return bucket
        return buckets[-1]

    def _window_signal(self, *, bucket: dict, max_focus_minutes: int) -> str:
        if bucket["focus_minutes"] == 0:
            return "no_data"
        if bucket["focus_minutes"] == max_focus_minutes:
            return "strong"
        return "visible"

    def _behavior_patterns(self, *, summary: dict, windows: list[dict]) -> list[dict]:
        patterns: list[dict] = []
        if summary["high_value_completed_task_count"] > 0:
            patterns.append(
                {
                    "key": "high_value_progress",
                    "title": "高价值任务有推进",
                    "signal": "positive",
                    "evidence": f"本周完成了 {summary['high_value_completed_task_count']} 个高价值任务。",
                    "suggestion": "下周继续把高价值任务放在 Today 的前段。",
                }
            )
        elif summary["total_completed_task_count"] > 0:
            patterns.append(
                {
                    "key": "low_value_drift",
                    "title": "完成了任务，但高价值任务偏少",
                    "signal": "watch",
                    "evidence": "本周有完成记录，但没有高价值任务完成。",
                    "suggestion": "下周先保护一个高价值任务，再处理轻任务。",
                }
            )
        if summary["overdue_task_count"] > 0:
            patterns.append(
                {
                    "key": "lagging_tasks",
                    "title": "存在滞后任务",
                    "signal": "risk",
                    "evidence": f"当前有 {summary['overdue_task_count']} 个任务已过截止时间。",
                    "suggestion": "先判断它们是否仍重要，重要的保留并前置，不重要的后移或归档。",
                }
            )
        if summary["total_interrupted_count"] > 0:
            patterns.append(
                {
                    "key": "focus_interruptions",
                    "title": "专注节奏被打断",
                    "signal": "watch",
                    "evidence": f"本周出现 {summary['total_interrupted_count']} 次 Focus 中断。",
                    "suggestion": "把容易中断的任务拆成更短步骤，再进入 Focus。",
                }
            )
        best_window = self._best_window(windows)
        if best_window is not None:
            patterns.append(
                {
                    "key": "best_focus_window",
                    "title": "存在更适合执行的时段",
                    "signal": "positive",
                    "evidence": f"{self._window_label(best_window['label'])}累计 Focus {best_window['focus_minutes']} 分钟。",
                    "suggestion": "把更重要或更难开始的任务放到这个时段。",
                }
            )
        if not patterns:
            patterns.append(
                {
                    "key": "insufficient_data",
                    "title": "本周数据还不够稳定",
                    "signal": "neutral",
                    "evidence": "还没有足够的完成、专注或延后记录。",
                    "suggestion": "先完成一次 Today -> Focus -> Report 闭环，洞察会更可靠。",
                }
            )
        return patterns[:5]

    def _recommendations(self, *, summary: dict, windows: list[dict]) -> list[dict]:
        recommendations: list[dict] = []
        best_window = self._best_window(windows)
        if best_window is not None:
            recommendations.append(
                {
                    "category": "schedule",
                    "title": "把难任务放到优势时段",
                    "suggestion": f"下周优先在{self._window_label(best_window['label'])}开始一个高价值任务。",
                    "rationale": "这是本周 Focus 时长最集中的时段。",
                }
            )
        if summary["overdue_task_count"] > 0:
            recommendations.append(
                {
                    "category": "planning",
                    "title": "清理滞后任务",
                    "suggestion": "先处理仍有价值的滞后任务，低价值滞后任务可以继续后移或归档。",
                    "rationale": "滞后任务会挤占 Today 的行动清晰度。",
                }
            )
        if summary["high_value_completed_task_count"] == 0 and summary["total_completed_task_count"] > 0:
            recommendations.append(
                {
                    "category": "value",
                    "title": "保护高价值任务",
                    "suggestion": "下周每天开始前只选一个最重要任务放到 Today 前段。",
                    "rationale": "本周有完成动作，但高价值任务没有形成闭环。",
                }
            )
        if not recommendations:
            recommendations.append(
                {
                    "category": "rhythm",
                    "title": "保持轻量节奏",
                    "suggestion": "继续从 Today 推荐序列的第一项开始，完成后再看下一步。",
                    "rationale": "当前没有明显风险，维持稳定比增加复杂度更重要。",
                }
            )
        return recommendations[:3]

    def _strategy_notes(self, *, summary: dict, windows: list[dict]) -> list[str]:
        notes: list[str] = []
        if summary["at_risk_goal_count"] > 0:
            notes.append("下周 Today 编排需要继续保护有风险的 Goal，避免被轻任务挤掉。")
        if summary["total_focus_minutes"] == 0:
            notes.append("当前洞察缺少 Focus 数据，先完成一次专注闭环会让建议更可信。")
        best_window = self._best_window(windows)
        if best_window is not None:
            notes.append(f"可以把高价值任务优先安排在{self._window_label(best_window['label'])}。")
        if not notes:
            notes.append("当前策略保持轻量即可，重点是让每天第一步更容易开始。")
        return notes[:3]

    def _best_window(self, windows: list[dict]) -> dict | None:
        candidates = [window for window in windows if window["focus_minutes"] > 0]
        if not candidates:
            return None
        return max(candidates, key=lambda window: (window["focus_minutes"], window["completed_focus_count"]))

    def _window_label(self, label: str) -> str:
        labels = {
            "morning": "上午",
            "afternoon": "下午",
            "evening": "晚上",
            "late_night": "深夜",
        }
        return labels.get(label, label)

    def _data_points(self, *, weekly_report: dict, windows: list[dict]) -> int:
        non_empty_days = len(
            [
                day
                for day in weekly_report["daily_trends"]
                if day["planned_task_count"] or day["completed_task_count"] or day["focus_minutes"]
            ]
        )
        active_windows = len([window for window in windows if window["focus_minutes"] > 0])
        return non_empty_days + active_windows + len(weekly_report["lagging_tasks"])


insight_service = InsightService()
