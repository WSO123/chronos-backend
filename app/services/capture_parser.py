from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.models.enums import InboxItemType, ParseResultType


@dataclass(frozen=True)
class ParsedCapture:
    result_type: ParseResultType
    item_type: InboxItemType
    title: str
    description: str | None
    estimated_duration_min: int | None
    suggested_priority: int | None
    suggested_deadline: date | None
    confidence: float
    raw_model_output: dict


class RuleCaptureParser:
    goal_keywords = ("目标", "goal", "希望", "计划")
    task_keywords = ("todo", "任务", "完成", "处理", "写", "做")

    def parse_text(self, raw_text: str) -> ParsedCapture:
        text = raw_text.strip()
        lowered = text.lower()

        if not text:
            return self._unknown(raw_text)

        if self._looks_like_goal(lowered):
            return ParsedCapture(
                result_type=ParseResultType.GOAL,
                item_type=InboxItemType.GOAL,
                title=self._clean_title(text),
                description=None,
                estimated_duration_min=None,
                suggested_priority=None,
                suggested_deadline=None,
                confidence=0.72,
                raw_model_output={"parser": "rule", "matched": "goal_keyword"},
            )

        if self._looks_like_task(lowered):
            return ParsedCapture(
                result_type=ParseResultType.TASK,
                item_type=InboxItemType.TASK,
                title=self._clean_title(text),
                description=None,
                estimated_duration_min=25,
                suggested_priority=3,
                suggested_deadline=None,
                confidence=0.68,
                raw_model_output={"parser": "rule", "matched": "task_keyword"},
            )

        return self._unknown(raw_text)

    def _looks_like_goal(self, text: str) -> bool:
        return any(keyword in text for keyword in self.goal_keywords)

    def _looks_like_task(self, text: str) -> bool:
        return any(keyword in text for keyword in self.task_keywords)

    def _unknown(self, raw_text: str) -> ParsedCapture:
        return ParsedCapture(
            result_type=ParseResultType.UNKNOWN,
            item_type=InboxItemType.UNKNOWN,
            title=self._clean_title(raw_text) or "Untitled input",
            description=None,
            estimated_duration_min=None,
            suggested_priority=None,
            suggested_deadline=None,
            confidence=0.35,
            raw_model_output={"parser": "rule", "matched": "fallback_unknown"},
        )

    def _clean_title(self, text: str) -> str:
        title = " ".join(text.strip().split())
        return title[:255]


rule_capture_parser = RuleCaptureParser()
