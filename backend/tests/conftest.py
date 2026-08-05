"""Configuración común de los tests."""

from __future__ import annotations

import os

# Estas variables se setean ANTES de importar la aplicación: `get_settings`
# cachea la configuración con `lru_cache`, así que el primer import fija los
# valores para todo el proceso de test.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("JWT_SECRET_KEY", "clave-solo-para-tests-no-usar-en-produccion")
os.environ.setdefault("OPENAI_API_KEY", "sk-dummy-test")
os.environ.setdefault("APP_TIMEZONE", "America/Argentina/Buenos_Aires")
os.environ.setdefault("DEFAULT_CURRENCY", "ARS")
os.environ.setdefault("SUPPORTED_CURRENCIES", "ARS")
os.environ.setdefault(
    "DATABASE_URL",
    "mysql+aiomysql://finanzas:finanzas@127.0.0.1:3306/finanzas_test?charset=utf8mb4",
)

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Cliente HTTP contra la app en memoria, sin levantar un servidor."""
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        yield http_client
