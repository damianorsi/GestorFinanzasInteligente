"""Health check contra una base de datos real.

Requiere MySQL levantado (docker compose, o el service container de CI).
Se excluye con: pytest -m "not integration"
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_health_conecta_contra_mysql(client: AsyncClient) -> None:
    # Arrange / Act
    response = await client.get("/health")

    # Assert
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


async def test_openapi_se_genera(client: AsyncClient) -> None:
    # Arrange / Act
    response = await client.get("/openapi.json")

    # Assert
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Gestor Inteligente de Finanzas Personales"
    assert "/health" in schema["paths"]
