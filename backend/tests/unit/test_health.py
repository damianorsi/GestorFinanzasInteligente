"""Tests del health check, con la verificación de base de datos mockeada."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.api.v1.routers import health as health_module


@pytest.fixture
def base_disponible(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _ok() -> bool:
        return True

    monkeypatch.setattr(health_module, "_check_database", _ok)


@pytest.fixture
def base_caida(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _falla() -> bool:
        return False

    monkeypatch.setattr(health_module, "_check_database", _falla)


async def test_health_devuelve_200_con_la_base_disponible(
    client: AsyncClient, base_disponible: None
) -> None:
    # Arrange / Act
    response = await client.get("/health")

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


async def test_health_devuelve_503_con_la_base_caida(client: AsyncClient, base_caida: None) -> None:
    # Arrange / Act
    response = await client.get("/health")

    # Assert
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "error"


async def test_health_expone_la_configuracion_de_localizacion(
    client: AsyncClient, base_disponible: None
) -> None:
    # Arrange / Act
    body = (await client.get("/health")).json()

    # Assert
    assert body["timezone"] == "America/Argentina/Buenos_Aires"
    assert body["default_currency"] == "ARS"


async def test_health_informa_el_scheduler_deshabilitado(
    client: AsyncClient, base_disponible: None
) -> None:
    """El scheduler llega en la fase 12; el contrato ya es el definitivo."""
    # Arrange / Act
    body = (await client.get("/health")).json()

    # Assert
    assert body["scheduler"] == "disabled"


async def test_toda_respuesta_lleva_request_id(client: AsyncClient, base_disponible: None) -> None:
    # Arrange / Act
    response = await client.get("/health")

    # Assert
    assert response.headers.get("X-Request-ID")


async def test_el_request_id_entrante_se_respeta(
    client: AsyncClient, base_disponible: None
) -> None:
    # Arrange
    entrante = "abc123def456"

    # Act
    response = await client.get("/health", headers={"X-Request-ID": entrante})

    # Assert
    assert response.headers["X-Request-ID"] == entrante
