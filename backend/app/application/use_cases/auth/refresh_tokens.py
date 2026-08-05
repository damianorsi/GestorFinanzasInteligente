"""Caso de uso: renovación del par de tokens."""

from __future__ import annotations

import logging

from app.application.dtos import TokenPair, TokenType
from app.application.exceptions import InvalidTokenError
from app.application.ports import Clock, RefreshTokenRepository, TokenService, UserRepository

logger = logging.getLogger(__name__)


class RefreshTokens:
    """Canjea un refresh token válido por un par nuevo.

    El refresh **rota**: el token usado se revoca en el mismo acto. Así, si uno
    se filtra, deja de servir en cuanto la persona legítima renueva, y el uso
    de un token ya canjeado es evidencia de robo.
    """

    def __init__(
        self,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        tokens: TokenService,
        clock: Clock,
    ) -> None:
        self._users = users
        self._refresh_tokens = refresh_tokens
        self._tokens = tokens
        self._clock = clock

    async def execute(self, refresh_token: str) -> TokenPair:
        claims = self._tokens.decode(refresh_token)

        # Un access token no sirve para renovar. Sin esta comprobación, el token
        # de quince minutos valdría lo mismo que el de siete días.
        if claims.token_type is not TokenType.REFRESH:
            raise InvalidTokenError("El token no es un refresh token.")

        ahora = self._clock.now()
        huella = self._tokens.fingerprint(refresh_token)

        almacenado = await self._refresh_tokens.find_active(huella, ahora)
        if almacenado is None:
            raise InvalidTokenError("El refresh token fue revocado o ya se usó.")

        usuario = await self._users.get_by_id(claims.user_id)
        if usuario is None or not usuario.is_active or usuario.id is None:
            raise InvalidTokenError("La cuenta ya no está disponible.")

        await self._refresh_tokens.revoke(huella, ahora)

        par = TokenPair(
            access=self._tokens.create_access_token(usuario.id),
            refresh=self._tokens.create_refresh_token(usuario.id),
        )
        await self._refresh_tokens.store(
            user_id=usuario.id,
            token_hash=self._tokens.fingerprint(par.refresh.value),
            expires_at=par.refresh.expires_at,
        )

        logger.info("Tokens renovados", extra={"user_id": usuario.id})
        return par
