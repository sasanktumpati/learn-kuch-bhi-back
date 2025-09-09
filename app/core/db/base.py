from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.ext.declarative import declarative_base

from app.core.config import settings

from typing import AsyncIterator
import logging


Base = declarative_base()


connection_string = str(settings.postgres.connection_string)

# TODO: Change echo to False in production
engine = create_async_engine(
    connection_string,
    echo=settings.app.is_testing is True,
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


logger = logging.getLogger(__name__)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Session rolled back due to error: {e}")
            raise
