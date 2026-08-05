"""Tests del contrato de error.

El contrato (docs/PROMPT.md §7) es `{code, message, details}` con `code` en
inglés y estable, y `message` en español. Lo fácil de romper es lo segundo: los
errores que levanta el framework traen el texto en inglés y, si se reenvían tal
cual, la respuesta queda mezclada sin que nadie lo note.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

# Palabras que solo pueden venir de un mensaje del framework, no de uno propio.
_DELATORES_DE_INGLES = ("There was", "error parsing", "Not Found", "Method Not Allowed")


def _es_contrato_valido(cuerpo: dict[str, object]) -> bool:
    return (
        set(cuerpo) == {"code", "message", "details"}
        and isinstance(cuerpo["code"], str)
        and isinstance(cuerpo["message"], str)
        and isinstance(cuerpo["details"], list)
    )


async def test_un_body_con_utf8_invalido_responde_en_espanol(client: AsyncClient) -> None:
    """El caso que destapó el problema: FastAPI lo corta antes de validar.

    Un cliente que declara `application/json` pero manda bytes que no son UTF-8
    (típico de PowerShell, que serializa en ISO-8859-1) no llega a la
    validación de Pydantic: FastAPI levanta un HTTPException con el texto en
    inglés. Sin reemplazarlo, la respuesta rompe el contrato.
    """
    # Arrange: 0xE1 es "á" en ISO-8859-1 y no es UTF-8 válido.
    cuerpo_invalido = b'{"email": "a@b.com", "full_name": "Dami\xe1n"}'

    # Act
    respuesta = await client.post(
        "/api/v1/auth/register",
        content=cuerpo_invalido,
        headers={"Content-Type": "application/json"},
    )

    # Assert
    cuerpo = respuesta.json()
    assert _es_contrato_valido(cuerpo)
    assert not any(delator in cuerpo["message"] for delator in _DELATORES_DE_INGLES)
    assert cuerpo["code"] == "bad_request"


async def test_un_json_malformado_cae_en_validacion(client: AsyncClient) -> None:
    """JSON roto pero UTF-8 válido sí llega a Pydantic: es 422, no 400."""
    # Arrange / Act
    respuesta = await client.post(
        "/api/v1/auth/register",
        content=b"{esto no es json",
        headers={"Content-Type": "application/json"},
    )

    # Assert
    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert _es_contrato_valido(cuerpo)
    assert cuerpo["code"] == "validation_error"


async def test_un_nombre_con_acentos_sobrevive_el_viaje(client: AsyncClient) -> None:
    """La contracara: con UTF-8 correcto, los acentos vuelven intactos."""
    # Arrange / Act
    respuesta = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "nandu@ejemplo.com",
            "password": "una-contrasena-larga",
            "full_name": "Damián Ñandú Orsi",
        },
    )

    # Assert
    assert respuesta.status_code == 201
    assert respuesta.json()["full_name"] == "Damián Ñandú Orsi"


async def test_una_ruta_inexistente_responde_en_espanol(client: AsyncClient) -> None:
    # Arrange / Act
    respuesta = await client.get("/api/v1/no-existe")

    # Assert
    assert respuesta.status_code == 404
    cuerpo = respuesta.json()
    assert _es_contrato_valido(cuerpo)
    assert cuerpo["code"] == "not_found"
    assert cuerpo["message"] == "El recurso solicitado no existe."


async def test_un_metodo_no_permitido_responde_en_espanol(client: AsyncClient) -> None:
    # Arrange / Act
    respuesta = await client.get("/api/v1/auth/login")

    # Assert
    assert respuesta.status_code == 405
    cuerpo = respuesta.json()
    assert _es_contrato_valido(cuerpo)
    assert cuerpo["code"] == "method_not_allowed"


async def test_los_errores_de_validacion_detallan_el_campo(client: AsyncClient) -> None:
    """`details` es lo que le permite al frontend marcar el campo exacto."""
    # Arrange / Act
    respuesta = await client.post(
        "/api/v1/auth/register",
        json={"email": "no-es-un-email", "password": "corta", "full_name": ""},
    )

    # Assert
    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "validation_error"
    campos = {detalle["field"] for detalle in cuerpo["details"]}
    assert {"email", "password", "full_name"} <= campos


async def test_ningun_error_filtra_un_stacktrace(client: AsyncClient) -> None:
    # Arrange / Act
    respuestas = [
        await client.get("/api/v1/no-existe"),
        await client.get("/api/v1/users/me"),
        await client.post("/api/v1/auth/register", json={}),
    ]

    # Assert
    for respuesta in respuestas:
        assert "Traceback" not in respuesta.text
        assert 'File "/srv' not in respuesta.text
