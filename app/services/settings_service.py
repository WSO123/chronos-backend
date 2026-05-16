from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User, UserSettings
from app.services.errors import NotFoundError, ValidationDomainError


class SettingsService:
    def get_settings(self, db: Session, *, user_id: uuid.UUID) -> UserSettings:
        return self._get_or_create_settings(db, user_id=user_id)

    def update_settings(self, db: Session, *, user_id: uuid.UUID, payload: dict) -> UserSettings:
        settings = self._get_or_create_settings(db, user_id=user_id)
        update_data = {key: value for key, value in payload.items() if value is not None}
        self._validate_channel_config(settings=settings, update_data=update_data)
        for key, value in update_data.items():
            setattr(settings, key, value)
        db.commit()
        db.refresh(settings)
        return settings

    def to_response(self, settings: UserSettings) -> dict:
        return {
            "notification_enabled": settings.notification_enabled,
            "reminder_execution_enabled": settings.reminder_execution_enabled,
            "reminder_deadline_enabled": settings.reminder_deadline_enabled,
            "reminder_channel_in_app_enabled": settings.reminder_channel_in_app_enabled,
            "reminder_channel_push_enabled": settings.reminder_channel_push_enabled,
            "reminder_channel_email_enabled": settings.reminder_channel_email_enabled,
            "execution_reminder_limit": settings.execution_reminder_limit,
            "execution_reminder_start_hour": settings.execution_reminder_start_hour,
            "execution_reminder_spacing_minutes": settings.execution_reminder_spacing_minutes,
            "deadline_reminder_hour": settings.deadline_reminder_hour,
            "focus_mode_default_minutes": settings.focus_mode_default_minutes,
            "planning_preference": settings.planning_preference,
            "ai_strategy_preference": settings.ai_strategy_preference,
        }

    def _get_or_create_settings(self, db: Session, *, user_id: uuid.UUID) -> UserSettings:
        user = db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found")
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = db.scalars(stmt).first()
        if settings is not None:
            return settings
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
        return settings

    def _validate_channel_config(self, *, settings: UserSettings, update_data: dict) -> None:
        next_in_app = update_data.get("reminder_channel_in_app_enabled", settings.reminder_channel_in_app_enabled)
        next_push = update_data.get("reminder_channel_push_enabled", settings.reminder_channel_push_enabled)
        next_email = update_data.get("reminder_channel_email_enabled", settings.reminder_channel_email_enabled)
        if not any([next_in_app, next_push, next_email]):
            raise ValidationDomainError("At least one reminder channel must stay enabled")


settings_service = SettingsService()
