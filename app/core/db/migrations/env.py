from logging.config import fileConfig

from sqlalchemy import pool
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.engine import Connection

from app.core.config import settings
from app.core.db.base import Base

# Ensure models are imported so that Base.metadata is populated
from app.core.db.schemas.auth import User  # noqa: F401


# Alembic Config
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use app metadata
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = str(settings.postgres.connection_string)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    url = str(settings.postgres.connection_string)
    connectable = create_async_engine(url, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
