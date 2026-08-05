"""Dependencias compartidas por los endpoints.

Acá se arma el cableado: los casos de uso reciben los puertos y este módulo es
el único que sabe qué implementación concreta va en cada uno.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import timedelta
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos import TokenType
from app.application.exceptions import InvalidTokenError
from app.application.ports import (
    CategoryRepository,
    Clock,
    PasswordHasher,
    RefreshTokenRepository,
    TokenService,
    UserRepository,
)
from app.application.use_cases.auth.login_user import LoginUser
from app.application.use_cases.auth.logout_user import LogoutUser
from app.application.use_cases.auth.refresh_tokens import RefreshTokens
from app.application.use_cases.auth.register_user import RegisterUser
from app.core.config import Settings, get_settings
from app.domain.entities import User
from app.infrastructure.clock import get_clock
from app.infrastructure.db.repositories import (
    SqlAlchemyCategoryRepository,
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemyUserRepository,
)
from app.infrastructure.db.session import session_scope
from app.infrastructure.security import Argon2Hasher, JwtTokenService

# `auto_error=False` para poder devolver el contrato de error propio en vez del
# `{"detail": ...}` que arma FastAPI por su cuenta.
_bearer = HTTPBearer(auto_error=False, description="Token de acceso JWT.")


async def get_db() -> AsyncIterator[AsyncSession]:
    """Sesión de base de datos con alcance de request."""
    async with session_scope() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


# --- Servicios sin estado (una instancia para todo el proceso) --------------
@lru_cache(maxsize=1)
def get_password_hasher() -> PasswordHasher:
    """El hasher se cachea: construirlo calcula el hash descartable, que es caro."""
    return Argon2Hasher()


@lru_cache(maxsize=1)
def get_token_service() -> TokenService:
    settings = get_settings()
    return JwtTokenService(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_ttl=timedelta(minutes=settings.access_token_expire_minutes),
        refresh_ttl=timedelta(days=settings.refresh_token_expire_days),
        clock=get_clock(),
    )


def get_app_clock() -> Clock:
    return get_clock()


# --- Repositorios (uno por request, atados a su sesión) --------------------
def get_user_repository(session: DbSession) -> UserRepository:
    return SqlAlchemyUserRepository(session)


def get_category_repository(session: DbSession) -> CategoryRepository:
    return SqlAlchemyCategoryRepository(session)


def get_refresh_token_repository(session: DbSession) -> RefreshTokenRepository:
    return SqlAlchemyRefreshTokenRepository(session)


Users = Annotated[UserRepository, Depends(get_user_repository)]
Categories = Annotated[CategoryRepository, Depends(get_category_repository)]
RefreshTokens_ = Annotated[RefreshTokenRepository, Depends(get_refresh_token_repository)]
Hasher = Annotated[PasswordHasher, Depends(get_password_hasher)]
Tokens = Annotated[TokenService, Depends(get_token_service)]
AppClock = Annotated[Clock, Depends(get_app_clock)]


# --- Casos de uso ----------------------------------------------------------
def get_register_user(users: Users, categories: Categories, hasher: Hasher) -> RegisterUser:
    return RegisterUser(users=users, categories=categories, hasher=hasher)


def get_login_user(
    users: Users, refresh: RefreshTokens_, hasher: Hasher, tokens: Tokens, clock: AppClock
) -> LoginUser:
    return LoginUser(users=users, refresh_tokens=refresh, hasher=hasher, tokens=tokens, clock=clock)


def get_refresh_tokens(
    users: Users, refresh: RefreshTokens_, tokens: Tokens, clock: AppClock
) -> RefreshTokens:
    return RefreshTokens(users=users, refresh_tokens=refresh, tokens=tokens, clock=clock)


def get_logout_user(refresh: RefreshTokens_, tokens: Tokens, clock: AppClock) -> LogoutUser:
    return LogoutUser(refresh_tokens=refresh, tokens=tokens, clock=clock)


# --- Usuario autenticado ---------------------------------------------------
async def get_current_user(
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    users: Users,
    tokens: Tokens,
) -> User:
    """Resuelve el usuario del token, o corta con 401.

    Es la única fuente del `user_id` para todo el resto de la aplicación: nunca
    se confía en un identificador que venga del body, la query o el prompt del
    chat.
    """
    if credenciales is None or not credenciales.credentials:
        raise InvalidTokenError("Falta el token de acceso.")

    claims = tokens.decode(credenciales.credentials)

    # Un refresh token dura siete días; sin esta comprobación serviría para
    # autenticar requests como si fuera un access token de quince minutos.
    if claims.token_type is not TokenType.ACCESS:
        raise InvalidTokenError("Se requiere un token de acceso.")

    usuario = await users.get_by_id(claims.user_id)
    if usuario is None or not usuario.is_active:
        raise InvalidTokenError("La cuenta ya no está disponible.")

    return usuario


CurrentUser = Annotated[User, Depends(get_current_user)]
