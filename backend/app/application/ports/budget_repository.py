"""Puerto de persistencia de presupuestos."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Protocol

from app.domain.entities import Budget


class BudgetRepository(Protocol):
    """Como el resto de los repositorios, `user_id` va en todas las firmas."""

    async def create(self, budget: Budget) -> Budget: ...

    async def create_many(self, budgets: Sequence[Budget]) -> int:
        """Persiste varios de una y devuelve cuántos se crearon."""
        ...

    async def update(self, budget: Budget) -> Budget: ...

    async def delete(self, user_id: int, budget_id: int) -> None: ...

    async def get_for_user(self, user_id: int, budget_id: int) -> Budget | None: ...

    async def list_for_period(
        self, user_id: int, period_month: date, currency: str
    ) -> list[Budget]:
        """Presupuestos del usuario para ese mes y esa moneda."""
        ...

    async def exists_for(
        self,
        user_id: int,
        category_id: int,
        period_month: date,
        currency: str,
        exclude_id: int | None = None,
    ) -> bool:
        """Si ya hay un presupuesto para esa categoría, período y moneda."""
        ...
