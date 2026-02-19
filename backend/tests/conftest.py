"""Shared pytest fixtures for ThreatHunt tests.

Provides:
- Async test database (in-memory SQLite)
- Test client (httpx AsyncClient on the FastAPI app)
- Factory functions for creating test hunts, datasets, etc.
"""

import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Force test database
os.environ["TH_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["TH_JWT_SECRET"] = "test-secret-key-for-tests"

from app.db.engine import Base, get_db
from app.main import app


# ── Database fixtures ─────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with overridden DB dependency."""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Factory helpers ───────────────────────────────────────────────────

def make_csv_bytes(
    columns: list[str],
    rows: list[list[str]],
    delimiter: str = ",",
) -> bytes:
    """Create CSV content as bytes for upload tests."""
    lines = [delimiter.join(columns)]
    for row in rows:
        lines.append(delimiter.join(str(v) for v in row))
    return "\n".join(lines).encode("utf-8")


SAMPLE_CSV = make_csv_bytes(
    ["timestamp", "hostname", "src_ip", "dst_ip", "process_name", "command_line"],
    [
        ["2025-01-15T10:30:00Z", "DESKTOP-ABC", "192.168.1.100", "10.0.0.50", "cmd.exe", "cmd /c whoami"],
        ["2025-01-15T10:31:00Z", "DESKTOP-ABC", "192.168.1.100", "10.0.0.51", "powershell.exe", "powershell -enc SGVsbG8="],
        ["2025-01-15T10:32:00Z", "DESKTOP-XYZ", "192.168.1.101", "8.8.8.8", "chrome.exe", "chrome.exe --no-sandbox"],
        ["2025-01-15T10:33:00Z", "DESKTOP-ABC", "192.168.1.100", "203.0.113.5", "svchost.exe", "svchost.exe -k netsvcs"],
        ["2025-01-15T10:34:00Z", "SERVER-DC01", "10.0.0.1", "10.0.0.50", "lsass.exe", "lsass.exe"],
    ],
)

SAMPLE_HASH_CSV = make_csv_bytes(
    ["filename", "md5", "sha256", "size"],
    [
        ["malware.exe", "d41d8cd98f00b204e9800998ecf8427e", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "1024"],
        ["benign.dll", "098f6bcd4621d373cade4e832627b4f6", "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8", "2048"],
    ],
)
