"""Repositorio de presupuestos sobre SQLAlchemy."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Budget
from app.infrastructure.db.mappers import presupuesto_a_dominio, presupuesto_a_modelo
from app.infrastructure.db.models import BudgetModel, CategoryModel


class SqlAlchemyBudgetRepository:
    """Implementación del puerto `BudgetRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, budget: Budget) -> Budget:
        modelo = presupuesto_a_modelo(budget)
        self._session.add(modelo)
        await self._session.flush()
        return presupuesto_a_dominio(modelo)

    async def create_many(self, budgets: Sequence[Budget]) -> int:
        modelos = [presupuesto_a_modelo(presupuesto) for presupuesto in budgets]
        self._session.add_all(modelos)
        await self._session.flush()
        return len(modelos)

    async def update(self, budget: Budget) -> Budget:
        if budget.id is None:
            raise ValueError("No se puede actualizar un presupuesto sin id.")
        modelo = await self._session.get(BudgetModel, budget.id)
        if modelo is None or modelo.user_id != budget.user_id:
            raise ValueError("El presupuesto no existe o no pertenece al usuario.")
        modelo.amount = budget.limit.amount
        await self._session.flush()
        return presupuesto_a_dominio(modelo)

    async def delete(self, user_id: int, budget_id: int) -> None:
        await self._session.execute(
            delete(BudgetModel).where(BudgetModel.id == budget_id, BudgetModel.user_id == user_id)
        )

    async def get_for_user(self, user_id: int, budget_id: int) -> Budget | None:
        modelo = await self._session.scalar(
            select(BudgetModel).where(BudgetModel.id == budget_id, BudgetModel.user_id == user_id)
        )
        return presupuesto_a_dominio(modelo) if modelo is not None else None

    async def list_for_period(
        self, user_id: int, period_month: date, currency: str
    ) -> list[Budget]:
        modelos = (
            await self._session.scalars(
                select(BudgetModel)
                .join(CategoryModel, CategoryModel.id == BudgetModel.category_id)
                .where(
                    BudgetModel.user_id == user_id,
                    BudgetModel.period_month == period_month,
                    BudgetModel.currency == currency,
                )
                # Orden estable por nombre de categoría; el caso de uso después
                # reordena por criticidad, pero sin esto dos presupuestos con el
                # mismo porcentaje saldrían en orden arbitrario.
                .order_by(CategoryModel.name)
            )
        ).all()
        return [presupuesto_a_dominio(modelo) for modelo in modelos]

    async def exists_for(
        self,
        user_id: int,
        category_id: int,
        period_month: date,
        currency: str,
        exclude_id: int | None = None,
    ) -> bool:
        consulta = (
            select(func.count())
            .select_from(BudgetModel)
            .where(
                BudgetModel.user_id == user_id,
                BudgetModel.category_id == category_id,
                BudgetModel.period_month == period_month,
                BudgetModel.currency == currency,
            )
        )
        if exclude_id is not None:
            consulta = consulta.where(BudgetModel.id != exclude_id)
        return bool(await self._session.scalar(consulta))

    async def list_user_ids_with_budgets(self, period_month: date, currency: str) -> list[int]:
        """Sin `user_id`: la usa el job. Ver el porqué en el puerto."""
        ids = await self._session.scalars(
            select(BudgetModel.user_id)
            .where(
                BudgetModel.period_month == period_month,
                BudgetModel.currency == currency,
            )
            .distinct()
            .order_by(BudgetModel.user_id)
        )
        return list(ids.all())
