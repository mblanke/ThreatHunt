"""Database engine, session factory, and base model.

Uses async SQLAlchemy with aiosqlite for local dev and asyncpg for production PostgreSQL.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency that yields an async DB session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables (for dev / first-run). In production use Alembic."""
    from sqlalchemy import inspect as sa_inspect

    async with engine.begin() as conn:
        # Only create tables that don't already exist (safe alongside Alembic)
        def _create_missing(sync_conn):
            inspector = sa_inspect(sync_conn)
            existing = set(inspector.get_table_names())
            tables_to_create = [
                t for t in Base.metadata.sorted_tables
                if t.name not in existing
            ]
            Base.metadata.create_all(sync_conn, tables=tables_to_create)

        await conn.run_sync(_create_missing)


async def dispose_db() -> None:
    """Dispose of the engine connection pool."""
    await engine.dispose()
