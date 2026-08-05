"""Puerto de emisión y validación de tokens."""

from __future__ import annotations

from typing import Protocol

from app.application.dtos import IssuedToken, TokenClaims


class TokenService(Protocol):
    """Emite y valida los tokens de acceso y de refresco."""

    def create_access_token(self, user_id: int) -> IssuedToken:
        """Emite un token de acceso de vida corta."""
        ...

    def create_refresh_token(self, user_id: int) -> IssuedToken:
        """Emite un token de refresco de vida larga."""
        ...

    def decode(self, token: str) -> TokenClaims:
        """Valida firma y expiración, y devuelve los claims.

        Lanza `InvalidTokenError` ante cualquier problema: firma inválida,
        token expirado, formato roto o claims faltantes. No distingue entre
        ellos hacia afuera.
        """
        ...

    def fingerprint(self, token: str) -> str:
        """Huella determinística del token, para poder guardarlo y revocarlo.

        En la base se guarda esto y nunca el token: si se filtra el dump, lo
        almacenado no sirve para autenticarse.
        """
        ...
