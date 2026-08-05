"""Repositorio de categorías sobre SQLAlchemy."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Category
from app.infrastructure.db.mappers import categoria_a_modelo
from app.infrastructure.db.models import CategoryModel


class SqlAlchemyCategoryRepository:
    """Implementación del puerto `CategoryRepository`.

    Expone por ahora solo lo que necesita el registro. El ABM completo llega en
    la fase 4.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_many(self, categories: Sequence[Category]) -> None:
        self._session.add_all([categoria_a_modelo(categoria) for categoria in categories])
        await self._session.flush()

    async def count_for_user(self, user_id: int) -> int:
        total = await self._session.scalar(
            select(func.count()).select_from(CategoryModel).where(CategoryModel.user_id == user_id)
        )
        return int(total or 0)
