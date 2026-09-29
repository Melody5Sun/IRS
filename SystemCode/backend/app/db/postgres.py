from functools import lru_cache

from sqlalchemy import Engine, create_engine

from app.core.config import settings


def require_database_url(database_url: str | None = None) -> str:
    url = database_url or settings.database_url
    if not url:
        raise RuntimeError("DATABASE_URL is required for the PostgreSQL runtime.")
    if not url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise ValueError("DATABASE_URL must point to PostgreSQL.")
    return url


@lru_cache(maxsize=1)
def get_postgres_engine() -> Engine:
    return create_engine(
        require_database_url(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        future=True,
    )


def dispose_postgres_engine() -> None:
    if get_postgres_engine.cache_info().currsize:
        get_postgres_engine().dispose()
        get_postgres_engine.cache_clear()
