"""Database engine, session factory, and base model.

Uses async SQLAlchemy with aiosqlite for local dev and asyncpg for production PostgreSQL.
"""

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

_engine_kwargs: dict = dict(
    echo=settings.DEBUG,
    future=True,
)

if _is_sqlite:
    _engine_kwargs["connect_args"] = {"timeout": 60, "check_same_thread": False}
    # NullPool: each session gets its own connection.
    # Combined with WAL mode, this allows concurrent reads while a write is in progress.
    from sqlalchemy.pool import NullPool
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, connection_record):
    """Enable WAL mode and tune busy-timeout for SQLite connections."""
    if _is_sqlite:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# Alias expected by other modules
async_session = async_session_factory


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
    """Dispose of the engine on shutdown."""
    await engine.dispose()
