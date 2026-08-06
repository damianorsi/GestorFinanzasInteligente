"""Entorno de Alembic, configurado para SQLAlchemy async."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings

# Import con efecto colateral: registra todos los modelos en Base.metadata
# para que el autogenerate los vea. No borrar aunque parezca sin uso.
from app.infrastructure.db import models  # noqa: F401
from app.infrastructure.db.base import Base

config = context.config

if config.config_file_name is not None:
    # `disable_existing_loggers=False` es obligatorio: el default de
    # `fileConfig` es True y apaga TODOS los loggers ya creados que no estén
    # nombrados en el ini, o sea todo `app.*`. Corriendo las migraciones en el
    # mismo proceso que la aplicación —el caso de la suite de tests, y de
    # cualquiera que llame a Alembic desde Python— eso deja la aplicación sin
    # logs desde ahí en adelante, sin un solo error que lo delate.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# ConfigParser interpreta `%` como interpolación: si la contraseña de la base
# tiene un `%`, sin escapar esto revienta con InterpolationSyntaxError.
_url = get_settings().database_url.replace("%", "%%")
config.set_main_option("sqlalchemy.url", _url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse a la base."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
