"""DTOs de autenticación."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.entities import User


class TokenType(StrEnum):
    """Tipo de token, embebido en el claim `typ`.

    Distinguirlos importa: sin esto, un refresh token —que dura siete días—
    serviría para autenticar requests como si fuera un access token de quince
    minutos, y la rotación no protegería de nada.
    """

    ACCESS = "access"
    REFRESH = "refresh"


@dataclass(frozen=True, slots=True)
class IssuedToken:
    """Un token recién emitido, con los datos que el emisor ya conoce."""

    value: str
    expires_at: datetime
    jti: str


@dataclass(frozen=True, slots=True)
class TokenPair:
    access: IssuedToken
    refresh: IssuedToken


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """Claims ya validados de un token."""

    user_id: int
    jti: str
    token_type: TokenType
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class UserCredentials:
    """Un usuario junto a su hash de contraseña.

    El hash no vive en la entidad `User` porque no es una regla de negocio; se
    junta con ella solo acá, donde el caso de uso de login lo necesita.
    """

    user: User
    password_hash: str


@dataclass(frozen=True, slots=True)
class StoredRefreshToken:
    """Un refresh token persistido, tal como se guardó."""

    user_id: int
    token_hash: str
    expires_at: datetime
