"""Endpoints del usuario autenticado."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.api.v1.schemas import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Datos de la cuenta autenticada",
    description="Resuelve el usuario a partir del token; nunca de un id enviado por el cliente.",
)
async def me(usuario: CurrentUser) -> UserResponse:
    return UserResponse(
        id=usuario.id or 0,
        email=usuario.email,
        full_name=usuario.full_name,
        is_active=usuario.is_active,
    )
