from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import uuid
from typing import Protocol


@dataclass(frozen=True)
class NotificationDeliveryRequest:
    reminder_id: uuid.UUID
    user_id: uuid.UUID
    channel: str
    title: str
    message: str | None
    scheduled_for: datetime
    metadata: dict


@dataclass(frozen=True)
class NotificationDeliveryResult:
    reminder_id: uuid.UUID
    channel: str
    status: str
    provider: str
    reason: str | None = None


class NotificationDeliveryProvider(Protocol):
    channel: str

    def deliver(self, request: NotificationDeliveryRequest) -> NotificationDeliveryResult:
        ...


class InAppNotificationProvider:
    channel = "in_app"
    provider = "reminder_center"

    def deliver(self, request: NotificationDeliveryRequest) -> NotificationDeliveryResult:
        return NotificationDeliveryResult(
            reminder_id=request.reminder_id,
            channel=request.channel,
            status="sent",
            provider=self.provider,
        )


class UnconfiguredNotificationProvider:
    def __init__(self, *, channel: str) -> None:
        self.channel = channel
        self.provider = "unconfigured"

    def deliver(self, request: NotificationDeliveryRequest) -> NotificationDeliveryResult:
        return NotificationDeliveryResult(
            reminder_id=request.reminder_id,
            channel=request.channel,
            status="skipped",
            provider=self.provider,
            reason="provider_not_configured",
        )


class NotificationDeliveryRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, NotificationDeliveryProvider] = {}

    def register(self, provider: NotificationDeliveryProvider) -> None:
        self._providers[provider.channel] = provider

    def provider_for(self, channel: str) -> NotificationDeliveryProvider:
        return self._providers.get(channel) or UnconfiguredNotificationProvider(channel=channel)

    def deliver(self, request: NotificationDeliveryRequest) -> NotificationDeliveryResult:
        return self.provider_for(request.channel).deliver(request)


notification_delivery_registry = NotificationDeliveryRegistry()
notification_delivery_registry.register(InAppNotificationProvider())
