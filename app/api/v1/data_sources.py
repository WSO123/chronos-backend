import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.core.db import get_db
from app.models.enums import DataSourceType
from app.schemas.data_sources import (
    DataSourceConnectionCreate,
    DataSourceConnectionResponse,
    DataSourceConnectionUpdate,
    DataSourceListResponse,
)
from app.services.data_source_service import data_source_service

router = APIRouter(prefix="/data-sources", tags=["data-sources"])


@router.get("", response_model=DataSourceListResponse)
def list_data_sources(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return data_source_service.list_sources(db, user_id=user_id)


@router.put(
    "/{source_type}/{provider}",
    response_model=DataSourceConnectionResponse,
    status_code=status.HTTP_200_OK,
)
def connect_data_source(
    source_type: DataSourceType,
    provider: str,
    payload: DataSourceConnectionCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return data_source_service.connect_source(
        db,
        user_id=user_id,
        source_type=source_type,
        provider=provider,
        external_account_label=payload.external_account_label,
        scopes=payload.scopes,
        sync_enabled=payload.sync_enabled,
        connection_metadata=payload.connection_metadata,
    )


@router.patch("/{connection_id}", response_model=DataSourceConnectionResponse)
def update_data_source_connection(
    connection_id: uuid.UUID,
    payload: DataSourceConnectionUpdate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return data_source_service.update_connection(
        db,
        connection_id=connection_id,
        user_id=user_id,
        updates=payload.model_dump(exclude_unset=True),
    )


@router.post("/{connection_id}/disconnect", response_model=DataSourceConnectionResponse)
def disconnect_data_source(
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return data_source_service.disconnect_source(db, connection_id=connection_id, user_id=user_id)
