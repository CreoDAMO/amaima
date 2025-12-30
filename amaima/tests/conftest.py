# tests/conftest.py

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.database import get_db
from app.auth.jwt import create_access_token
from app.models.user import User

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def db_session():
    """Create database session for testing"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database override"""
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

@pytest.fixture
async def authenticated_client(client: AsyncClient) -> AsyncClient:
    """Create authenticated test client"""
    token = create_access_token(user_id="test_user_id")
    client.headers["Authorization"] = f"Bearer {token}"
    return client

@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create test user in database"""
    user = User(
        id="test_user_id",
        email="test@example.com",
        name="Test User",
        password_hash="hashed_password"
    )
    db_session.add(user)
    await db_session.commit()
    return user
