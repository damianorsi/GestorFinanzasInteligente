"""Emisión y validación de JWT."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.application.dtos import IssuedToken, TokenClaims, TokenType
from app.application.exceptions import InvalidTokenError
from app.application.ports import Clock

CLAIM_TIPO = "typ"


class JwtTokenService:
    """Implementación del puerto `TokenService` sobre PyJWT."""

    def __init__(
        self,
        secret_key: str,
        algorithm: str,
        access_ttl: timedelta,
        refresh_ttl: timedelta,
        clock: Clock,
    ) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._access_ttl = access_ttl
        self._refresh_ttl = refresh_ttl
        self._clock = clock

    def create_access_token(self, user_id: int) -> IssuedToken:
        return self._emitir(user_id, TokenType.ACCESS, self._access_ttl)

    def create_refresh_token(self, user_id: int) -> IssuedToken:
        return self._emitir(user_id, TokenType.REFRESH, self._refresh_ttl)

    def _emitir(self, user_id: int, tipo: TokenType, ttl: timedelta) -> IssuedToken:
        ahora = self._clock.now()
        expira = ahora + ttl
        jti = uuid.uuid4().hex
        payload = {
            # `sub` va como string: PyJWT 2.10+ rechaza los enteros porque el
            # RFC 7519 define este claim como StringOrURI.
            "sub": str(user_id),
            "jti": jti,
            CLAIM_TIPO: tipo.value,
            "iat": int(ahora.timestamp()),
            "exp": int(expira.timestamp()),
        }
        token = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        return IssuedToken(value=token, expires_at=expira, jti=jti)

    def decode(self, token: str) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                # `verify_exp: False` no afloja la validación: la expiración se
                # comprueba unas líneas más abajo contra el puerto `Clock`.
                # PyJWT la resolvería con `time.time()`, es decir el reloj del
                # sistema, y entonces el token se emitiría con un reloj y se
                # validaría con otro. Además de ser incoherente, hace imposible
                # testear el vencimiento sin esperar de verdad.
                options={"require": ["exp", "sub", "jti", "iat"], "verify_exp": False},
            )
        except jwt.PyJWTError as exc:
            # Firma inválida, claims faltantes o formato roto colapsan en un
            # solo error: afuera no se distingue por qué falló.
            raise InvalidTokenError("El token no es válido.") from exc

        try:
            user_id = int(payload["sub"])
            tipo = TokenType(payload[CLAIM_TIPO])
            expira = datetime.fromtimestamp(int(payload["exp"]), tz=UTC)
        except (KeyError, ValueError, OverflowError, OSError) as exc:
            raise InvalidTokenError("El token no tiene los claims esperados.") from exc

        if expira <= self._clock.now():
            raise InvalidTokenError("El token expiró.")

        return TokenClaims(
            user_id=user_id,
            jti=str(payload["jti"]),
            token_type=tipo,
            expires_at=expira,
        )

    def fingerprint(self, token: str) -> str:
        """SHA-256 del token.

        Alcanza con un hash rápido y no hace falta Argon2: el token es un valor
        aleatorio de alta entropía, no una contraseña elegida por una persona,
        así que no hay diccionario que se le pueda aplicar por fuerza bruta.
        """
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
