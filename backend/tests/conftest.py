"""Configuración común de los tests."""

from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

_URL_POR_DEFECTO = "mysql+aiomysql://finanzas:finanzas@127.0.0.1:3306/finanzas?charset=utf8mb4"


def _derivar_url_de_test(url: str) -> str:
    """Devuelve la misma URL apuntando a la base `<nombre>_test`.

    Los tests truncan todas las tablas entre casos, así que apuntar a la base
    de desarrollo borraría datos reales. Esta derivación es automática a
    propósito: si dependiera de que alguien acuerde de setear una variable, el
    día que se olvide se lleva puesta su base.
    """
    sin_query, separador, query = url.partition("?")
    prefijo, _, nombre = sin_query.rstrip("/").rpartition("/")
    if not nombre.endswith("_test"):
        sin_query = f"{prefijo}/{nombre}_test"
    return f"{sin_query}{separador}{query}"


# Estas variables se setean ANTES de importar la aplicación: `get_settings`
# cachea la configuración con `lru_cache`, así que el primer import fija los
# valores para todo el proceso de test.
os.environ["APP_ENV"] = "test"
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("JWT_SECRET_KEY", "clave-solo-para-tests-no-usar-en-produccion")
os.environ.setdefault("OPENAI_API_KEY", "sk-dummy-test")
os.environ.setdefault("APP_TIMEZONE", "America/Argentina/Buenos_Aires")
os.environ.setdefault("DEFAULT_CURRENCY", "ARS")
os.environ.setdefault("SUPPORTED_CURRENCIES", "ARS")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or _derivar_url_de_test(
    os.environ.get("DATABASE_URL", _URL_POR_DEFECTO)
)

from collections.abc import AsyncIterator, Iterator  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.infrastructure.db.base import Base  # noqa: E402
from app.infrastructure.db.session import (  # noqa: E402
    dispose_engine,
    get_engine,
    get_session_factory,
)


@pytest.fixture(autouse=True)
async def _cerrar_pool_entre_tests() -> AsyncIterator[None]:
    """Cierra el pool de conexiones al terminar cada test.

    `get_engine` cachea el engine para todo el proceso, pero pytest-asyncio
    crea un event loop nuevo por test. Sin esto, el segundo test que toca la
    base toma una conexión del pool creada en un loop ya cerrado y falla con
    "attached to a different loop".
    """
    yield
    await dispose_engine()


@pytest.fixture(scope="session")
def esquema() -> Iterator[None]:
    """Crea el esquema de la base de test corriendo las migraciones.

    Se usa Alembic y no `metadata.create_all` a propósito: así la suite prueba
    la migración real, que es lo que se va a ejecutar en producción, y no una
    aproximación generada desde los modelos.
    """
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")
    yield


@pytest.fixture
async def db_session(esquema: None) -> AsyncIterator[AsyncSession]:
    """Sesión contra la base de test, con las tablas vacías."""
    engine = get_engine()
    async with engine.begin() as conn:
        # Se desactivan las FK para poder truncar en cualquier orden; TRUNCATE
        # no las respeta ni siquiera cuando no hay filas referenciadas.
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for tabla in Base.metadata.sorted_tables:
            await conn.execute(text(f"TRUNCATE TABLE `{tabla.name}`"))
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

    async with get_session_factory()() as session:
        yield session


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Cliente HTTP contra la app en memoria, sin levantar un servidor."""
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        yield http_client
