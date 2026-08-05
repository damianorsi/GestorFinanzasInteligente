"""Caso de uso: inicio de sesión."""

from __future__ import annotations

import logging

from app.application.dtos import TokenPair
from app.application.exceptions import InvalidCredentialsError
from app.application.ports import (
    Clock,
    PasswordHasher,
    RefreshTokenRepository,
    TokenService,
    UserRepository,
)
from app.domain.entities import User

logger = logging.getLogger(__name__)


class LoginUser:
    """Valida credenciales y emite el par de tokens."""

    def __init__(
        self,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        hasher: PasswordHasher,
        tokens: TokenService,
        clock: Clock,
    ) -> None:
        self._users = users
        self._refresh_tokens = refresh_tokens
        self._hasher = hasher
        self._tokens = tokens
        self._clock = clock

    async def execute(self, email: str, password: str) -> tuple[User, TokenPair]:
        credenciales = await self._users.get_credentials_by_email(email.strip().lower())

        if credenciales is None:
            # Se verifica igual contra un hash descartable: sin esto, la
            # respuesta para un email inexistente vuelve mucho más rápido y esa
            # diferencia de tiempo permite enumerar cuentas registradas.
            self._hasher.verify_dummy(password)
            raise InvalidCredentialsError("Email o contraseña incorrectos.")

        if not self._hasher.verify(password, credenciales.password_hash):
            raise InvalidCredentialsError("Email o contraseña incorrectos.")

        # Una cuenta deshabilitada devuelve el mismo error genérico: decir
        # "tu cuenta está deshabilitada" confirmaría que el email existe.
        if not credenciales.user.is_active:
            raise InvalidCredentialsError("Email o contraseña incorrectos.")

        usuario = credenciales.user
        if usuario.id is None:
            raise RuntimeError("El repositorio devolvió un usuario sin id.")

        par = TokenPair(
            access=self._tokens.create_access_token(usuario.id),
            refresh=self._tokens.create_refresh_token(usuario.id),
        )
        await self._refresh_tokens.store(
            user_id=usuario.id,
            token_hash=self._tokens.fingerprint(par.refresh.value),
            expires_at=par.refresh.expires_at,
        )

        logger.info("Sesión iniciada", extra={"user_id": usuario.id})
        return usuario, par
