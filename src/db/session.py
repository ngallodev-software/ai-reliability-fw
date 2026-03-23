from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_engine = None
_async_session = None


def init_reliability(database_url: str) -> None:
    """
    Initialize the reliability-fw database connection.

    Call once at application startup before any reliability-fw DB operations.
    The database_url must use the asyncpg driver
    (e.g. postgresql+asyncpg://user:pass@host/db).
    """
    global _engine, _async_session
    _engine = create_async_engine(
        database_url,
        echo=False,
        future=True,
        connect_args={"server_settings": {"search_path": "reliability,public"}},
    )
    _async_session = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    if _async_session is None:
        raise RuntimeError(
            "reliability-fw is not initialized. "
            "Call init_reliability(database_url) before using any DB operations."
        )
    async with _async_session() as session:
        yield session
