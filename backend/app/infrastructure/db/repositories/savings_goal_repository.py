"""Repositorio de metas de ahorro sobre SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import SavingsGoal
from app.infrastructure.db.mappers import meta_a_dominio, meta_a_modelo
from app.infrastructure.db.models import SavingsGoalModel


class SqlAlchemySavingsGoalRepository:
    """Implementación del puerto `SavingsGoalRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, goal: SavingsGoal) -> SavingsGoal:
        modelo = meta_a_modelo(goal)
        self._session.add(modelo)
        await self._session.flush()
        return meta_a_dominio(modelo)

    async def update(self, goal: SavingsGoal) -> SavingsGoal:
        modelo = await self._session.get(SavingsGoalModel, goal.id)
        if modelo is None:
            raise ValueError(f"La meta {goal.id} no existe.")

        modelo.name = goal.name
        modelo.target_amount = goal.target.amount
        modelo.currency = goal.target.currency
        modelo.starts_on = goal.starts_on
        modelo.target_date = goal.target_date
        modelo.is_active = goal.is_active
        await self._session.flush()
        return meta_a_dominio(modelo)

    async def delete(self, user_id: int, goal_id: int) -> None:
        await self._session.execute(
            delete(SavingsGoalModel).where(
                SavingsGoalModel.id == goal_id,
                SavingsGoalModel.user_id == user_id,
            )
        )

    async def get_for_user(self, user_id: int, goal_id: int) -> SavingsGoal | None:
        modelo = await self._session.scalar(
            select(SavingsGoalModel).where(
                SavingsGoalModel.id == goal_id,
                SavingsGoalModel.user_id == user_id,
            )
        )
        return None if modelo is None else meta_a_dominio(modelo)

    async def list_for_user(
        self, user_id: int, currency: str, only_active: bool = True
    ) -> list[SavingsGoal]:
        consulta = select(SavingsGoalModel).where(
            SavingsGoalModel.user_id == user_id,
            SavingsGoalModel.currency == currency,
        )
        if only_active:
            consulta = consulta.where(SavingsGoalModel.is_active.is_(True))

        modelos = (
            await self._session.scalars(
                # `id` como desempate: dos metas creadas en el mismo segundo
                # comparten `created_at` y saldrían en orden distinto entre
                # llamadas.
                consulta.order_by(SavingsGoalModel.created_at.desc(), SavingsGoalModel.id.desc())
            )
        ).all()
        return [meta_a_dominio(modelo) for modelo in modelos]

    async def exists_with_name(
        self, user_id: int, name: str, exclude_id: int | None = None
    ) -> bool:
        # `lower()` de los dos lados y no del collation: la comparación tiene
        # que dar lo mismo corra donde corra, y el collation de la tabla es un
        # detalle de despliegue.
        consulta = select(SavingsGoalModel.id).where(
            SavingsGoalModel.user_id == user_id,
            func.lower(SavingsGoalModel.name) == name.strip().lower(),
        )
        if exclude_id is not None:
            consulta = consulta.where(SavingsGoalModel.id != exclude_id)
        return await self._session.scalar(consulta.limit(1)) is not None
