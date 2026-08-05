"""Ayudas compartidas por los tests de integración."""

from __future__ import annotations

from dataclasses import dataclass

from httpx import AsyncClient

CONTRASENA = "una-contrasena-larga"


@dataclass(frozen=True, slots=True)
class CuentaDePrueba:
    user_id: int
    access_token: str
    refresh_token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}


async def crear_cuenta(
    client: AsyncClient,
    email: str,
    password: str = CONTRASENA,
    nombre: str = "Usuario de prueba",
) -> CuentaDePrueba:
    """Registra una cuenta, inicia sesión y devuelve sus credenciales."""
    registro = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": nombre},
    )
    assert registro.status_code == 201, registro.text

    sesion = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert sesion.status_code == 200, sesion.text
    tokens = sesion.json()

    return CuentaDePrueba(
        user_id=registro.json()["id"],
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
    )
