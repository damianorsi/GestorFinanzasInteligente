"""Endpoints de autenticación."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import (
    AppSettings,
    get_login_user,
    get_logout_user,
    get_refresh_tokens,
    get_register_user,
)
from app.api.v1.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.application.dtos import TokenPair
from app.application.use_cases.auth.login_user import LoginUser
from app.application.use_cases.auth.logout_user import LogoutUser
from app.application.use_cases.auth.refresh_tokens import RefreshTokens
from app.application.use_cases.auth.register_user import RegisterUser

router = APIRouter(prefix="/auth", tags=["auth"])


def _respuesta_de_tokens(par: TokenPair, expira_en_minutos: int) -> TokenResponse:
    return TokenResponse(
        access_token=par.access.value,
        refresh_token=par.refresh.value,
        expires_in=expira_en_minutos * 60,
    )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    summary="Registrar una cuenta",
    description=(
        "Crea la cuenta y siembra sus categorías por defecto. "
        "Devuelve 409 si el email ya está registrado."
    ),
)
async def register(
    payload: RegisterRequest,
    caso: Annotated[RegisterUser, Depends(get_register_user)],
    response: Response,
) -> UserResponse:
    usuario = await caso.execute(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )
    response.headers["Location"] = "/api/v1/users/me"
    return UserResponse(
        id=usuario.id or 0,
        email=usuario.email,
        full_name=usuario.full_name,
        is_active=usuario.is_active,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión",
    description=(
        "Devuelve el par de tokens. Ante credenciales inválidas responde 401 con "
        "un mensaje genérico, sin revelar si el email existe."
    ),
)
async def login(
    payload: LoginRequest,
    caso: Annotated[LoginUser, Depends(get_login_user)],
    settings: AppSettings,
) -> TokenResponse:
    _, par = await caso.execute(email=payload.email, password=payload.password)
    return _respuesta_de_tokens(par, settings.access_token_expire_minutes)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar el par de tokens",
    description=(
        "El refresh token rota: el usado queda revocado en el mismo acto, así que "
        "reutilizarlo devuelve 401."
    ),
)
async def refresh(
    payload: RefreshRequest,
    caso: Annotated[RefreshTokens, Depends(get_refresh_tokens)],
    settings: AppSettings,
) -> TokenResponse:
    par = await caso.execute(payload.refresh_token)
    return _respuesta_de_tokens(par, settings.access_token_expire_minutes)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cerrar sesión",
    description=(
        "Revoca el refresh token. Es idempotente: responde 204 incluso si el token "
        "ya estaba revocado o no existe."
    ),
)
async def logout(
    payload: LogoutRequest,
    caso: Annotated[LogoutUser, Depends(get_logout_user)],
) -> None:
    await caso.execute(payload.refresh_token)
