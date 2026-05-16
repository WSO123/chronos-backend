import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.core.db import get_db
from app.models.enums import InboxItemStatus
from app.schemas.inbox import InboxConfirmResponse, InboxItemResponse, InboxItemUpdate
from app.services.inbox_service import inbox_service

router = APIRouter(prefix="/inbox", tags=["inbox"])


@router.get("", response_model=list[InboxItemResponse])
def list_inbox_items(
    status: InboxItemStatus | None = InboxItemStatus.PENDING,
    include_all: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return inbox_service.list_items(
        db,
        user_id=user_id,
        status=None if include_all else status,
        limit=limit,
        offset=offset,
    )


@router.get("/{item_id}", response_model=InboxItemResponse)
def get_inbox_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return inbox_service.get_item(db, item_id=item_id, user_id=user_id)


@router.patch("/{item_id}", response_model=InboxItemResponse)
def update_inbox_item(
    item_id: uuid.UUID,
    payload: InboxItemUpdate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return inbox_service.update_item(
        db,
        item_id=item_id,
        user_id=user_id,
        updates=payload.model_dump(exclude_unset=True),
    )


@router.post("/{item_id}/confirm", response_model=InboxConfirmResponse)
def confirm_inbox_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    item = inbox_service.confirm_item(db, item_id=item_id, user_id=user_id)
    return {
        "inbox_item": item,
        "result_entity_type": item.result_entity_type,
        "result_entity_id": item.result_entity_id,
    }


@router.post("/{item_id}/discard", response_model=InboxItemResponse)
def discard_inbox_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return inbox_service.discard_item(db, item_id=item_id, user_id=user_id)
