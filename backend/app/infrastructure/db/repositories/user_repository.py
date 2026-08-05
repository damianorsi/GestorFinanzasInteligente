"""Repositorio de usuarios sobre SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos import UserCredentials
from app.domain.entities import User
from app.infrastructure.db.mappers import usuario_a_dominio, usuario_a_modelo
from app.infrastructure.db.models import UserModel


class SqlAlchemyUserRepository:
    """Implementación del puerto `UserRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def exists_with_email(self, email: str) -> bool:
        total = await self._session.scalar(
            select(func.count()).select_from(UserModel).where(UserModel.email == email)
        )
        return bool(total)

    async def get_by_id(self, user_id: int) -> User | None:
        modelo = await self._session.get(UserModel, user_id)
        return usuario_a_dominio(modelo) if modelo is not None else None

    async def get_credentials_by_email(self, email: str) -> UserCredentials | None:
        modelo = await self._session.scalar(select(UserModel).where(UserModel.email == email))
        if modelo is None:
            return None
        return UserCredentials(user=usuario_a_dominio(modelo), password_hash=modelo.password_hash)

    async def create(self, user: User, password_hash: str) -> User:
        modelo = usuario_a_modelo(user, password_hash)
        self._session.add(modelo)
        # El flush asigna el id autoincremental sin cerrar la transacción: el
        # commit lo hace la dependencia de sesión al terminar el request.
        await self._session.flush()
        return usuario_a_dominio(modelo)
