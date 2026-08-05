"""Repositorio de refresh tokens sobre SQLAlchemy."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos import StoredRefreshToken
from app.infrastructure.clock import a_utc_naive
from app.infrastructure.db.models import RefreshTokenModel


class SqlAlchemyRefreshTokenRepository:
    """Implementación del puerto `RefreshTokenRepository`.

    Todas las conversiones de zona horaria pasan por `a_utc_naive`: las
    columnas son `DATETIME` sin zona y la convención es que guardan UTC.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def store(self, user_id: int, token_hash: str, expires_at: datetime) -> None:
        self._session.add(
            RefreshTokenModel(
                user_id=user_id,
                token_hash=token_hash,
                expires_at=a_utc_naive(expires_at),
            )
        )
        await self._session.flush()

    async def find_active(self, token_hash: str, now: datetime) -> StoredRefreshToken | None:
        modelo = await self._session.scalar(
            select(RefreshTokenModel).where(
                RefreshTokenModel.token_hash == token_hash,
                RefreshTokenModel.revoked_at.is_(None),
                RefreshTokenModel.expires_at > a_utc_naive(now),
            )
        )
        if modelo is None:
            return None
        return StoredRefreshToken(
            user_id=modelo.user_id,
            token_hash=modelo.token_hash,
            expires_at=modelo.expires_at,
        )

    async def revoke(self, token_hash: str, now: datetime) -> None:
        # Idempotente: si no existe o ya estaba revocado, el UPDATE afecta cero
        # filas y no pasa nada. Cerrar sesión nunca tiene que fallar.
        await self._session.execute(
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.token_hash == token_hash,
                RefreshTokenModel.revoked_at.is_(None),
            )
            .values(revoked_at=a_utc_naive(now))
        )

    async def revoke_all_for_user(self, user_id: int, now: datetime) -> None:
        await self._session.execute(
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.revoked_at.is_(None),
            )
            .values(revoked_at=a_utc_naive(now))
        )
