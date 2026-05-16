from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import DataSourceStatus, DataSourceType
from app.schemas.common import TimestampedResponse


class DataSourceConnectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_account_label: str | None = Field(default=None, max_length=255)
    scopes: list[str] | None = None
    sync_enabled: bool = True
    connection_metadata: dict = Field(default_factory=dict)


class DataSourceConnectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: DataSourceStatus | None = None
    external_account_label: str | None = Field(default=None, max_length=255)
    scopes: list[str] | None = None
    sync_enabled: bool | None = None
    sync_cursor: str | None = Field(default=None, max_length=500)
    last_sync_at: datetime | None = None
    connection_metadata: dict | None = None

    @model_validator(mode="after")
    def require_one_update(self) -> "DataSourceConnectionUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        if "scopes" in self.model_fields_set and self.scopes is None:
            raise ValueError("scopes cannot be null")
        if "connection_metadata" in self.model_fields_set and self.connection_metadata is None:
            raise ValueError("connection_metadata cannot be null")
        return self


class DataSourceConnectionResponse(TimestampedResponse):
    user_id: uuid.UUID
    source_type: DataSourceType
    provider: str
    status: DataSourceStatus
    external_account_label: str | None
    scopes: list[str]
    sync_enabled: bool
    sync_cursor: str | None
    last_sync_at: datetime | None
    connected_at: datetime | None
    revoked_at: datetime | None
    connection_metadata: dict


class DataSourceCatalogEntryResponse(BaseModel):
    source_type: DataSourceType
    display_name: str
    supported_providers: list[str]
    default_scopes: list[str]
    capabilities: list[str]
    status: DataSourceStatus
    connection: DataSourceConnectionResponse | None


class DataSourceListResponse(BaseModel):
    sources: list[DataSourceCatalogEntryResponse]
    connected_count: int


class DataSourceSyncSummaryItemResponse(BaseModel):
    connection_id: uuid.UUID
    source_type: DataSourceType
    provider: str
    status: DataSourceStatus
    sync_enabled: bool
    last_sync_at: datetime | None
    latest_run_id: uuid.UUID | None
    latest_run_status: str | None
    latest_run_finished_at: datetime | None
    latest_run_error_message: str | None
    retryable: bool
    next_retry_at: datetime | None
    imported_count: int
    reused_count: int
    needs_attention: bool
    attention_reason: str | None


class DataSourceSyncSummaryResponse(BaseModel):
    connected_count: int
    sync_enabled_count: int
    attention_count: int
    latest_success_at: datetime | None
    latest_failure_at: datetime | None
    items: list[DataSourceSyncSummaryItemResponse]


class DataSourceManualSyncResponse(BaseModel):
    status: str
    sync_run_id: uuid.UUID | None
    skip_reason: str | None = None
    error_message: str | None = None
    connection_id: uuid.UUID
    user_id: uuid.UUID
    source_type: DataSourceType
    provider: str
    processed_count: int = 0
    imported_count: int = 0
    reused_count: int = 0
    import_record_ids: list[uuid.UUID] = Field(default_factory=list)
    energy_metric_ids: list[uuid.UUID] = Field(default_factory=list)
    sync_cursor: str | None = None
    last_sync_at: datetime | None = None
    fetched_from_provider: bool = False
    provider_mode: str | None = None
    retryable: bool = False
    next_retry_at: datetime | None = None


class DataSourceSyncRunResponse(TimestampedResponse):
    user_id: uuid.UUID
    data_source_connection_id: uuid.UUID | None
    source_type: DataSourceType
    provider: str
    status: str
    trigger: str
    attempt: int
    max_attempts: int
    retryable: bool
    next_retry_at: datetime | None
    skip_reason: str | None
    error_message: str | None
    processed_count: int
    imported_count: int
    reused_count: int
    fetched_from_provider: bool
    provider_mode: str | None
    sync_cursor_before: str | None
    sync_cursor_after: str | None
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    run_metadata: dict
