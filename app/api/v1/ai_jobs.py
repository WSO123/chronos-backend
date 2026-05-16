import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.core.db import get_db
from app.schemas.ai_jobs import AIJobResponse
from app.services.ai_job_service import ai_job_service

router = APIRouter(prefix="/ai-jobs", tags=["ai-jobs"])


@router.get("/{job_id}", response_model=AIJobResponse)
def get_ai_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return ai_job_service.get_job(db, job_id=job_id, user_id=user_id)
