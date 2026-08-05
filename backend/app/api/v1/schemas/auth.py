"""Schemas de request y response de autenticación."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field

LARGO_MINIMO_CONTRASENA = 8
# Argon2 no trunca, pero un límite alto evita que alguien mande megabytes y
# haga trabajar al hasher de gusto.
LARGO_MAXIMO_CONTRASENA = 128


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=LARGO_MINIMO_CONTRASENA,
        max_length=LARGO_MAXIMO_CONTRASENA,
        description="Mínimo 8 caracteres.",
    )
    full_name: str = Field(min_length=1, max_length=120)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "damian@ejemplo.com",
                "password": "una-contrasena-larga",
                "full_name": "Damián Orsi",
            }
        }
    )


class LoginRequest(BaseModel):
    email: EmailStr
    # Sin restricciones de largo: validar acá revelaría la política de
    # contraseñas al atacante y rechazaría credenciales viejas todavía válidas.
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Segundos de validez del access token.")


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
