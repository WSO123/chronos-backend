from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Protocol

from app.models.data_source import DataSourceConnection
from app.models.enums import DataSourceType


@dataclass(frozen=True)
class HealthMetricFetchResult:
    metrics: list[dict[str, Any]]
    next_cursor: str | None = None
    provider_mode: str = "fake"


class HealthProviderAdapter(Protocol):
    provider: str

    def fetch_daily_metrics(
        self,
        connection: DataSourceConnection,
        *,
        days: int = 7,
        end_date: date | None = None,
    ) -> HealthMetricFetchResult:
        ...


class FakeHealthProviderAdapter:
    def __init__(self, *, provider: str) -> None:
        self.provider = provider

    def fetch_daily_metrics(
        self,
        connection: DataSourceConnection,
        *,
        days: int = 7,
        end_date: date | None = None,
    ) -> HealthMetricFetchResult:
        metadata = connection.connection_metadata or {}
        raw_metrics = metadata.get("fake_energy_metrics", [])
        if not isinstance(raw_metrics, list):
            raw_metrics = []
        normalized = [
            self._normalize_metric(metric)
            for metric in raw_metrics
            if isinstance(metric, dict)
        ]
        normalized = self._filter_window(normalized, days=days, end_date=end_date)
        return HealthMetricFetchResult(
            metrics=normalized,
            next_cursor=metadata.get("fake_next_cursor"),
            provider_mode="fake",
        )

    def _normalize_metric(self, metric: dict[str, Any]) -> dict[str, Any]:
        metric_date = self._normalize_date(metric.get("metric_date"))
        external_metric_id = metric.get("external_metric_id") or f"{self.provider}-{metric_date.isoformat()}"
        return {
            "external_metric_id": str(external_metric_id),
            "metric_date": metric_date,
            "sleep_minutes": metric.get("sleep_minutes"),
            "sleep_quality_score": metric.get("sleep_quality_score"),
            "stress_score": metric.get("stress_score"),
            "energy_score": metric.get("energy_score"),
            "note": metric.get("note"),
            "metric_metadata": {
                **(metric.get("metric_metadata") or {}),
                "provider_mode": "fake",
                "provider": self.provider,
                "external_metric_id": str(external_metric_id),
            },
        }

    def _normalize_date(self, value: Any) -> date:
        if value is None:
            raise ValueError("Health metric_date is required")
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        return date.fromisoformat(str(value))

    def _filter_window(
        self,
        metrics: list[dict[str, Any]],
        *,
        days: int,
        end_date: date | None,
    ) -> list[dict[str, Any]]:
        if end_date is None:
            return metrics[-max(days, 0) :]
        start_date = end_date - timedelta(days=max(days - 1, 0))
        return [
            metric
            for metric in metrics
            if start_date <= metric["metric_date"] <= end_date
        ]


class HealthProviderRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, HealthProviderAdapter] = {}

    def register(self, adapter: HealthProviderAdapter) -> None:
        self._adapters[adapter.provider] = adapter

    def adapter_for(self, connection: DataSourceConnection) -> HealthProviderAdapter | None:
        if connection.source_type != DataSourceType.HEALTH:
            return None
        return self._adapters.get(connection.provider)


health_provider_registry = HealthProviderRegistry()
for provider in ("apple_health", "google_fit"):
    health_provider_registry.register(FakeHealthProviderAdapter(provider=provider))
