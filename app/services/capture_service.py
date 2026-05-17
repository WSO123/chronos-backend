from __future__ import annotations

from decimal import Decimal
from time import perf_counter
import uuid

from sqlalchemy.orm import Session

from app.ai.agents.capture_parser import CaptureParserAgent, capture_parser_agent
from app.ai.providers.base import LLMProviderError, empty_llm_usage
from app.ai.providers.registry import llm_provider_registry
from app.ai.schemas.capture import CaptureParserOutput
from app.models.ai_job import AIJob
from app.models.capture import AIParseResult, CaptureInput
from app.models.enums import (
    AIJobStatus,
    AIJobType,
    CaptureInputType,
    CaptureSource,
    CaptureStatus,
    EntityType,
    InboxItemStatus,
    InboxItemType,
    ParseResultType,
)
from app.models.inbox import InboxItem
from app.models.mixins import utc_now
from app.services.activity_event_service import activity_event_service
from app.services.ai_job_service import ai_job_service
from app.services.capture_parser import ParsedCapture, rule_capture_parser
from app.services.errors import NotFoundError, ValidationDomainError


class CaptureService:
    def __init__(
        self,
        *,
        parser_agent: CaptureParserAgent | None = None,
        rule_parser=rule_capture_parser,
    ) -> None:
        self.parser_agent = parser_agent or capture_parser_agent
        self.rule_parser = rule_parser

    def create_text_capture(self, db: Session, *, user_id: uuid.UUID, raw_text: str) -> tuple[CaptureInput, AIParseResult, InboxItem]:
        return self._create_parsed_capture(
            db,
            user_id=user_id,
            raw_text=raw_text,
            input_type=CaptureInputType.TEXT,
            source=CaptureSource.MANUAL,
            parse_context=None,
            commit=True,
        )

    def create_external_capture(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        raw_text: str,
        source: CaptureSource,
        parse_context: dict | None = None,
        commit: bool = True,
    ) -> tuple[CaptureInput, AIParseResult, InboxItem]:
        if source not in {CaptureSource.CALENDAR, CaptureSource.EMAIL}:
            raise ValidationDomainError("External capture source must be calendar or email")
        return self._create_parsed_capture(
            db,
            user_id=user_id,
            raw_text=raw_text,
            input_type=CaptureInputType.EXTERNAL,
            source=source,
            parse_context=parse_context,
            commit=commit,
        )

    def _create_parsed_capture(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        raw_text: str,
        input_type: CaptureInputType,
        source: CaptureSource,
        parse_context: dict | None,
        commit: bool,
    ) -> tuple[CaptureInput, AIParseResult, InboxItem]:
        cleaned_text = raw_text.strip()
        if not cleaned_text:
            raise ValidationDomainError("Capture text cannot be empty")

        capture = CaptureInput(
            user_id=user_id,
            input_type=input_type,
            raw_text=cleaned_text,
            source=source,
            status=CaptureStatus.RECEIVED,
        )
        db.add(capture)
        db.flush()
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.CAPTURE,
            entity_id=capture.id,
            event_type="CAPTURE_CREATED",
            payload={"input_type": input_type.value, "source": source.value},
        )

        fallback_parsed = self.rule_parser.parse_text(cleaned_text)
        parsed, job = self._run_capture_parser_agent(
            db,
            capture=capture,
            raw_text=cleaned_text,
            input_type=input_type,
            source=source,
            parse_context=parse_context,
            fallback_parsed=fallback_parsed,
        )
        raw_model_output = dict(parsed.raw_model_output)
        if parse_context:
            raw_model_output["context"] = parse_context
        raw_model_output["ai_job_id"] = str(job.id)
        parse_result = AIParseResult(
            capture_input_id=capture.id,
            result_type=parsed.result_type,
            title=parsed.title,
            description=parsed.description,
            estimated_duration_min=parsed.estimated_duration_min,
            suggested_priority=parsed.suggested_priority,
            suggested_deadline=parsed.suggested_deadline,
            confidence=Decimal(str(parsed.confidence)),
            raw_model_output=raw_model_output,
        )
        db.add(parse_result)
        db.flush()

        inbox_item = InboxItem(
            user_id=user_id,
            capture_input_id=capture.id,
            parse_result_id=parse_result.id,
            item_type=parsed.item_type,
            title=parsed.title,
            description=parsed.description,
            suggested_priority=parsed.suggested_priority,
            suggested_deadline=parsed.suggested_deadline,
            status=InboxItemStatus.PENDING,
        )
        db.add(inbox_item)
        capture.status = CaptureStatus.PARSED
        db.flush()
        job.result_entity_type = EntityType.INBOX.value
        job.result_entity_id = inbox_item.id
        db.flush()

        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.CAPTURE,
            entity_id=capture.id,
            event_type="CAPTURE_PARSED",
            payload={
                "result_type": parsed.result_type.value,
                "confidence": parsed.confidence,
                "source": source.value,
                "ai_job_id": str(job.id),
                "ai_job_status": job.status.value,
            },
        )
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.INBOX,
            entity_id=inbox_item.id,
            event_type="INBOX_ITEM_CREATED",
            payload={"item_type": parsed.item_type.value},
        )
        if commit:
            db.commit()
            db.refresh(capture)
            db.refresh(parse_result)
            db.refresh(inbox_item)
        return capture, parse_result, inbox_item

    def _run_capture_parser_agent(
        self,
        db: Session,
        *,
        capture: CaptureInput,
        raw_text: str,
        input_type: CaptureInputType,
        source: CaptureSource,
        parse_context: dict | None,
        fallback_parsed: ParsedCapture,
    ) -> tuple[ParsedCapture, AIJob]:
        provider = llm_provider_registry.current_provider()
        job = ai_job_service.create_job(
            db,
            user_id=capture.user_id,
            job_type=AIJobType.CAPTURE_PARSER,
            input_entity_type=EntityType.CAPTURE.value,
            input_entity_id=capture.id,
            provider=provider.provider_name,
            model=provider.model_name,
            prompt_version=self.parser_agent.prompt_version,
            metadata={
                "mode": "sync_structured_agent",
                "input_type": input_type.value,
                "source": source.value,
                "prompt_checksum": self.parser_agent.prompt_checksum,
                "fallback_parser": "rule-capture-parser-v1",
            },
            commit=False,
        )
        job.status = AIJobStatus.RUNNING
        job.started_at = utc_now()
        started = perf_counter()

        try:
            agent_result = self.parser_agent.run(
                raw_text=raw_text,
                input_type=input_type.value,
                source=source.value,
                parse_context=parse_context,
                fallback_output=self._fallback_output(fallback_parsed),
                provider=provider,
            )
            parsed = self._parsed_from_agent_output(agent_result.output, agent_result=agent_result)
            job.provider = agent_result.provider
            job.model = agent_result.model
            job.prompt_version = agent_result.prompt_version
            job.status = AIJobStatus.SUCCEEDED
            job.job_metadata = {
                **job.job_metadata,
                "output_applied": True,
                "result_type": agent_result.output.result_type.value,
                "item_type": agent_result.output.item_type.value,
                "confidence": agent_result.output.confidence,
                "prompt_checksum": agent_result.prompt_checksum,
                "provider_response_id": agent_result.response_id,
                "usage": agent_result.usage,
            }
        except Exception as exc:  # noqa: BLE001 - Capture must still enter Inbox.
            parsed = self._fallback_parsed_output(fallback_parsed=fallback_parsed, exc=exc)
            job.status = AIJobStatus.SUCCEEDED_WITH_FALLBACK
            job.error_message = str(exc)
            job.job_metadata = {
                **job.job_metadata,
                "output_applied": False,
                "fallback_reason": self._capture_parser_fallback_reason(exc),
                "fallback_error_type": exc.__class__.__name__,
                "fallback_root_error_type": self._root_error_type(exc),
                "failure_type": self._capture_parser_failure_type(exc),
            }

        job.finished_at = utc_now()
        job.latency_ms = max(0, int((perf_counter() - started) * 1000))
        job.job_metadata = {
            **job.job_metadata,
            "provider_latency_ms": job.latency_ms,
            "provider_observability_version": "v1",
            "usage": self._usage_metadata(job.job_metadata.get("usage")),
        }
        return parsed, job

    def _parsed_from_agent_output(
        self,
        output: CaptureParserOutput,
        *,
        agent_result,
    ) -> ParsedCapture:
        self._validate_output_compatibility(output)
        return ParsedCapture(
            result_type=output.result_type,
            item_type=output.item_type,
            title=" ".join(output.title.strip().split())[:255],
            description=self._clean_optional_text(output.description),
            estimated_duration_min=output.estimated_duration_min,
            suggested_priority=output.suggested_priority,
            suggested_deadline=output.suggested_deadline,
            confidence=round(output.confidence, 2),
            raw_model_output={
                "parser": "llm_agent",
                "agent": "capture_parser",
                "prompt_version": agent_result.prompt_version,
                "prompt_checksum": agent_result.prompt_checksum,
                "provider": agent_result.provider,
                "model": agent_result.model,
                "provider_response_id": agent_result.response_id,
                "output": output.model_dump(mode="json"),
            },
        )

    def _validate_output_compatibility(self, output: CaptureParserOutput) -> None:
        expected = {
            ParseResultType.TASK: InboxItemType.TASK,
            ParseResultType.GOAL: InboxItemType.GOAL,
            ParseResultType.IDEA: InboxItemType.IDEA,
            ParseResultType.UNKNOWN: InboxItemType.UNKNOWN,
        }.get(output.result_type)
        if expected is not None and output.item_type != expected:
            raise ValueError(f"Capture parser returned incompatible item_type for {output.result_type.value}")
        if output.result_type == ParseResultType.CALENDAR_ITEM and output.item_type in {
            InboxItemType.TASK,
            InboxItemType.GOAL,
        }:
            raise ValueError("Calendar item output must stay confirmable as idea or unknown in v1")

    def _fallback_parsed_output(self, *, fallback_parsed: ParsedCapture, exc: Exception) -> ParsedCapture:
        raw_model_output = {
            **fallback_parsed.raw_model_output,
            "agent": {
                "name": "capture_parser",
                "status": "fallback",
                "fallback_reason": self._capture_parser_fallback_reason(exc),
                "failure_type": self._capture_parser_failure_type(exc),
                "error_type": exc.__class__.__name__,
            },
        }
        return ParsedCapture(
            result_type=fallback_parsed.result_type,
            item_type=fallback_parsed.item_type,
            title=fallback_parsed.title,
            description=fallback_parsed.description,
            estimated_duration_min=fallback_parsed.estimated_duration_min,
            suggested_priority=fallback_parsed.suggested_priority,
            suggested_deadline=fallback_parsed.suggested_deadline,
            confidence=fallback_parsed.confidence,
            raw_model_output=raw_model_output,
        )

    def _fallback_output(self, parsed: ParsedCapture) -> dict:
        return {
            "result_type": parsed.result_type.value,
            "item_type": parsed.item_type.value,
            "title": parsed.title,
            "description": parsed.description,
            "estimated_duration_min": parsed.estimated_duration_min,
            "suggested_priority": parsed.suggested_priority,
            "suggested_deadline": parsed.suggested_deadline.isoformat() if parsed.suggested_deadline else None,
            "confidence": parsed.confidence,
            "rationale": "Rule parser fallback output for local mock mode.",
        }

    def _usage_metadata(self, usage: object) -> dict:
        if not isinstance(usage, dict):
            return empty_llm_usage()
        return {**empty_llm_usage(), **usage}

    def _capture_parser_fallback_reason(self, exc: Exception) -> str:
        if isinstance(exc, ValueError):
            return "capture_parser_agent_invalid_output"
        return "capture_parser_agent_failed"

    def _capture_parser_failure_type(self, exc: Exception) -> str:
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

    def _clean_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    def get_capture(self, db: Session, *, capture_id: uuid.UUID, user_id: uuid.UUID) -> CaptureInput:
        capture = db.get(CaptureInput, capture_id)
        if capture is None or capture.user_id != user_id:
            raise NotFoundError("Capture not found")
        return capture


capture_service = CaptureService()
