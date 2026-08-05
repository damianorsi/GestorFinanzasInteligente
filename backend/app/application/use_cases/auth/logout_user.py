"""Caso de uso: cierre de sesión."""

from __future__ import annotations

import logging

from app.application.ports import Clock, RefreshTokenRepository, TokenService

logger = logging.getLogger(__name__)


class LogoutUser:
    """Revoca un refresh token.

    Es idempotente y **no falla si el token es inválido o ya estaba revocado**:
    cerrar sesión tiene que funcionar siempre desde el punto de vista de quien
    lo pide. Devolver un error acá solo lograría que el frontend quede sin
    saber si limpiar la sesión local.
    """

    def __init__(
        self,
        refresh_tokens: RefreshTokenRepository,
        tokens: TokenService,
        clock: Clock,
    ) -> None:
        self._refresh_tokens = refresh_tokens
        self._tokens = tokens
        self._clock = clock

    async def execute(self, refresh_token: str) -> None:
        await self._refresh_tokens.revoke(
            self._tokens.fingerprint(refresh_token), self._clock.now()
        )
        logger.info("Sesión cerrada")
