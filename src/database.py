import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy import text

from .config import settings
from .models import Base

logger = logging.getLogger(__name__)

# Define global engine and session maker
engine = None
AsyncSessionLocal = None


def get_database_path() -> Path:
    """
    Determines the absolute path for the SQLite database file.
    """
    db_url = settings.database_url
    if not db_url.startswith("sqlite:///"):
        raise ValueError(f"Unsupported DATABASE_URL: {db_url}. Only sqlite is supported.")

    # Extract the path from the URL
    db_file_str = db_url[len("sqlite:///"):]

    # The path inside the container should be absolute
    return Path(f"/{db_file_str}").resolve()


async def init_database():
    """
    Initializes the database, creates the engine, and creates all tables.
    """
    global engine, AsyncSessionLocal

    db_path = get_database_path()
    db_dir = db_path.parent

    logger.info(f"Initializing database at {db_path}")

    # Ensure the data directory exists
    try:
        db_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Database directory '{db_dir}' is ready.")
    except Exception as e:
        logger.error(f"Failed to create database directory '{db_dir}': {e}")
        raise

    # For aiosqlite, the path in the URL must be relative to the connection root,
    # and for an absolute path, it must start with '////'.
    db_url_async = f"sqlite+aiosqlite:///{db_path}"

    logger.debug(f"Using async database URL: {db_url_async}")

    try:
        engine = create_async_engine(db_url_async, echo=settings.log_level == "DEBUG")
        AsyncSessionLocal = async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False
        )

        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database connection successful and tables created.")

    except Exception as e:
        logger.error(f"Failed to initialize database engine or create tables: {e}")
        raise


@asynccontextmanager
async def get_db_session():
    """
    Provides a transactional database session.
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db():
    """
    FastAPI dependency to get a database session.
    """
    async with get_db_session() as session:
        yield session


async def close_database():
    """
    Closes the database engine connections.
    """
    if engine:
        await engine.dispose()
        logger.info("Database connections closed.")


async def check_database_health() -> bool:
    """
    Checks if the database is accessible and responsive.
    """
    try:
        async with get_db_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
