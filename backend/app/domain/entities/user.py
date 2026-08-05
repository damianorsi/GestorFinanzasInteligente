"""Entidad `User`."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.exceptions import InvalidUserError

LARGO_MAXIMO_EMAIL = 255
LARGO_MAXIMO_NOMBRE = 120


@dataclass(slots=True)
class User:
    """Persona usuaria de la aplicación.

    La validación fuerte de email vive en el borde HTTP (Pydantic). Acá se hace
    solo la comprobación de sanidad que el dominio necesita para no guardar
    basura si alguna vez se crea un usuario fuera de la API.
    """

    email: str
    full_name: str
    id: int | None = None
    is_active: bool = True

    def __post_init__(self) -> None:
        email = self.email.strip().lower()
        local, _, dominio = email.partition("@")
        if not local or not dominio or "." not in dominio or len(email) > LARGO_MAXIMO_EMAIL:
            raise InvalidUserError(f"Email inválido: {self.email!r}")
        self.email = email

        nombre = self.full_name.strip()
        if not nombre:
            raise InvalidUserError("El nombre no puede estar vacío.")
        if len(nombre) > LARGO_MAXIMO_NOMBRE:
            raise InvalidUserError(
                f"El nombre no puede superar los {LARGO_MAXIMO_NOMBRE} caracteres."
            )
        self.full_name = nombre
