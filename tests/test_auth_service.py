"""
Unit tests for authentication service.
Uses an in-memory SQLite database (async) for fast, isolated testing.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.schemas.schemas import LoginRequest, SignupRequest
from app.services.auth_service import AuthService
from app.core.exceptions import ConflictError, UnauthorizedError

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def db_session():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def auth_service(db_session: AsyncSession) -> AuthService:
    return AuthService(db_session)


@pytest.mark.asyncio
async def test_signup_success(auth_service: AuthService, db_session: AsyncSession):
    payload = SignupRequest(
        email="alice@example.com",
        username="alice",
        password="securepass",
        full_name="Alice",
    )
    user = await auth_service.signup(payload)
    await db_session.commit()

    assert user.id is not None
    assert user.email == "alice@example.com"
    assert user.hashed_password != "securepass"


@pytest.mark.asyncio
async def test_signup_duplicate_email_raises(auth_service: AuthService, db_session: AsyncSession):
    payload = SignupRequest(email="bob@example.com", username="bob", password="password1")
    await auth_service.signup(payload)
    await db_session.commit()

    with pytest.raises(ConflictError):
        await auth_service.signup(payload)


@pytest.mark.asyncio
async def test_login_success(auth_service: AuthService, db_session: AsyncSession):
    signup = SignupRequest(email="carol@example.com", username="carol", password="mypassword")
    await auth_service.signup(signup)
    await db_session.commit()

    token_resp = await auth_service.login(LoginRequest(email="carol@example.com", password="mypassword"))
    assert token_resp.access_token
    assert token_resp.token_type == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password_raises(auth_service: AuthService, db_session: AsyncSession):
    signup = SignupRequest(email="dave@example.com", username="dave", password="correct")
    await auth_service.signup(signup)
    await db_session.commit()

    with pytest.raises(UnauthorizedError):
        await auth_service.login(LoginRequest(email="dave@example.com", password="wrong"))
