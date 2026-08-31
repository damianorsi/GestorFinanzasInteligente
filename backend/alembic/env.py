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


def _comparar_default_del_servidor(
    contexto: object,
    columna_inspeccionada: object,
    columna_del_modelo: object,
    default_inspeccionado: object,
    default_del_modelo: object,
    default_del_modelo_renderizado: str | None,
) -> bool | None:
    """Decide si el default del servidor cambió de verdad.

    MySQL devuelve `CURRENT_TIMESTAMP` donde el modelo declara `now()`, y
    Alembic los toma por distintos. Sin esta comparación, **cada autogenerate
    propone un `alter_column` por cada `created_at` y `updated_at` del
    esquema**: catorce operaciones que reescriben todas las tablas para
    dejarlas exactamente igual. Ya se colaron una vez en una migración y
    hubo que sacarlas a mano.

    Se normaliza el texto de los dos lados y se comparan. Devolver `False`
    significa "no cambió".
    """
    if default_inspeccionado is None or default_del_modelo is None:
        # Sin uno de los dos lados no hay nada que normalizar: devolver None
        # deja que decida Alembic con su criterio de siempre.
        return None

    def normalizar(valor: object) -> str:
        texto = str(getattr(valor, "arg", valor)).strip().lower()
        # MySQL devuelve `CURRENT_TIMESTAMP` donde el modelo dice `now()`, y
        # entrecomilla los defaults numéricos: `'1'` contra `1`.
        return texto.replace("current_timestamp", "now").replace("()", "").strip("()").strip("'\"")

    return normalizar(default_del_modelo) != normalizar(default_inspeccionado)


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
        compare_server_default=_comparar_default_del_servidor,
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
