from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.auth import (
    AuthLoginRequest,
    AuthLogoutRequest,
    AuthLogoutResponse,
    AuthRefreshRequest,
    AuthRegisterRequest,
    AuthTokenResponse,
    AuthUserResponse,
)
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: AuthRegisterRequest, db: Session = Depends(get_db)):
    token_pair = auth_service.register(
        db,
        email=payload.email,
        password=payload.password,
        name=payload.name,
        timezone_name=payload.timezone,
    )
    return auth_service.to_token_response(token_pair)


@router.post("/login", response_model=AuthTokenResponse)
def login(payload: AuthLoginRequest, db: Session = Depends(get_db)):
    token_pair = auth_service.login(db, email=payload.email, password=payload.password)
    return auth_service.to_token_response(token_pair)


@router.post("/refresh", response_model=AuthTokenResponse)
def refresh(payload: AuthRefreshRequest, db: Session = Depends(get_db)):
    token_pair = auth_service.refresh(db, refresh_token=payload.refresh_token)
    return auth_service.to_token_response(token_pair)


@router.post("/logout", response_model=AuthLogoutResponse)
def logout(payload: AuthLogoutRequest, db: Session = Depends(get_db)):
    return auth_service.logout(db, refresh_token=payload.refresh_token)


@router.get("/me", response_model=AuthUserResponse)
def get_auth_me(current_user: User = Depends(get_current_user)):
    return auth_service.to_user_response(current_user)
