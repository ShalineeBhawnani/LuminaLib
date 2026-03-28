"""Authentication routes: signup, login, profile, signout."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.models import User
from app.schemas.schemas import (
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
    UserUpdateRequest,
)
from app.services.auth_service import AuthService

router = APIRouter()


def _get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, svc: AuthService = Depends(_get_auth_service)):
    return await svc.signup(payload)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, svc: AuthService = Depends(_get_auth_service)):
    return await svc.login(payload)


@router.get("/me", response_model=UserResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    svc: AuthService = Depends(_get_auth_service),
):
    return await svc.update_profile(current_user, payload)


@router.post("/signout", status_code=status.HTTP_204_NO_CONTENT)
async def signout():
    """
    Stateless JWT signout.
    Clients must discard the token locally.
    For server-side invalidation, add a token denylist (Redis-backed).
    """
    return
