"""Authentication business logic."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.models import User
from app.schemas.schemas import LoginRequest, SignupRequest, TokenResponse, UserUpdateRequest


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def signup(self, payload: SignupRequest) -> User:
        # Check uniqueness
        existing = await self._db.execute(
            select(User).where((User.email == payload.email) | (User.username == payload.username))
        )
        if existing.scalar_one_or_none():
            raise ConflictError("Email or username already registered.")

        user = User(
            email=payload.email,
            username=payload.username,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
        )
        self._db.add(user)
        await self._db.flush()
        return user

    async def login(self, payload: LoginRequest) -> TokenResponse:
        result = await self._db.execute(select(User).where(User.email == payload.email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(payload.password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password.")

        if not user.is_active:
            raise UnauthorizedError("Account is deactivated.")

        token = create_access_token(subject=str(user.id))
        return TokenResponse(access_token=token)

    async def update_profile(self, user: User, payload: UserUpdateRequest) -> User:
        if payload.full_name is not None:
            user.full_name = payload.full_name
        if payload.username is not None:
            user.username = payload.username
        self._db.add(user)
        await self._db.flush()
        return user
