from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.models.data_source import DataSourceConnection
from app.models.enums import DataSourceType


@dataclass(frozen=True)
class ProviderFetchResult:
    items: list[dict[str, Any]]
    next_cursor: str | None = None
    provider_mode: str = "fake"


class DataSourceProviderAdapter(Protocol):
    source_type: DataSourceType
    provider: str

    def fetch_items(self, connection: DataSourceConnection, *, limit: int = 50) -> ProviderFetchResult:
        ...


class FakeDataSourceProviderAdapter:
    def __init__(self, *, source_type: DataSourceType, provider: str) -> None:
        self.source_type = source_type
        self.provider = provider

    def fetch_items(self, connection: DataSourceConnection, *, limit: int = 50) -> ProviderFetchResult:
        metadata = connection.connection_metadata or {}
        raw_items = metadata.get("fake_items", [])
        if not isinstance(raw_items, list):
            raw_items = []
        limited_items = [item for item in raw_items[: max(limit, 0)] if isinstance(item, dict)]
        items = [self._normalize_item(item, index=index) for index, item in enumerate(limited_items, start=1)]
        return ProviderFetchResult(
            items=items,
            next_cursor=metadata.get("fake_next_cursor"),
            provider_mode="fake",
        )

    def _normalize_item(self, item: dict[str, Any], *, index: int) -> dict[str, Any]:
        external_item_id = item.get("external_item_id") or f"fake-{self.provider}-{index}"
        external_item_type = item.get("external_item_type") or self._default_external_item_type()
        title = item.get("title") or self._default_title(index)
        external_payload = {
            **(item.get("external_payload") or {}),
            "provider_mode": "fake",
            "source_type": self.source_type.value,
            "provider": self.provider,
        }
        return {
            "external_item_id": str(external_item_id),
            "external_item_type": str(external_item_type),
            "title": str(title),
            "body": item.get("body"),
            "occurred_at": self._normalize_occurred_at(item.get("occurred_at")),
            "external_payload": external_payload,
        }

    def _default_external_item_type(self) -> str:
        if self.source_type == DataSourceType.CALENDAR:
            return "calendar_event"
        if self.source_type == DataSourceType.EMAIL:
            return "email_message"
        return "external_item"

    def _default_title(self, index: int) -> str:
        if self.source_type == DataSourceType.CALENDAR:
            return f"Fake calendar item {index}"
        if self.source_type == DataSourceType.EMAIL:
            return f"Fake email item {index}"
        return f"Fake external item {index}"

    def _normalize_occurred_at(self, value: Any) -> datetime | str | None:
        if value is None or isinstance(value, datetime):
            return value
        return str(value)


class DataSourceProviderRegistry:
    def __init__(self) -> None:
        self._adapters: dict[tuple[DataSourceType, str], DataSourceProviderAdapter] = {}

    def register(self, adapter: DataSourceProviderAdapter) -> None:
        self._adapters[(adapter.source_type, adapter.provider)] = adapter

    def adapter_for(self, connection: DataSourceConnection) -> DataSourceProviderAdapter | None:
        return self._adapters.get((connection.source_type, connection.provider))


data_source_provider_registry = DataSourceProviderRegistry()
for provider in ("google_calendar", "outlook_calendar", "apple_calendar"):
    data_source_provider_registry.register(
        FakeDataSourceProviderAdapter(source_type=DataSourceType.CALENDAR, provider=provider)
    )
for provider in ("gmail", "outlook_email"):
    data_source_provider_registry.register(
        FakeDataSourceProviderAdapter(source_type=DataSourceType.EMAIL, provider=provider)
    )
