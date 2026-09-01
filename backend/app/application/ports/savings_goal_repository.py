"""Puerto de persistencia de metas de ahorro."""

from __future__ import annotations

from typing import Protocol

from app.domain.entities import SavingsGoal


class SavingsGoalRepository(Protocol):
    """Como el resto de los repositorios, `user_id` va en todas las firmas."""

    async def create(self, goal: SavingsGoal) -> SavingsGoal: ...

    async def update(self, goal: SavingsGoal) -> SavingsGoal: ...

    async def delete(self, user_id: int, goal_id: int) -> None: ...

    async def get_for_user(self, user_id: int, goal_id: int) -> SavingsGoal | None: ...

    async def list_for_user(
        self, user_id: int, currency: str, only_active: bool = True
    ) -> list[SavingsGoal]:
        """Metas del usuario en esa moneda, de la más reciente a la más vieja."""
        ...

    async def exists_with_name(
        self, user_id: int, name: str, exclude_id: int | None = None
    ) -> bool:
        """Si ya hay una meta con ese nombre.

        Dos metas homónimas no son un problema de integridad, pero sí de
        lectura: la pantalla y el asistente las nombran por el nombre, y
        «¿cuánto me falta para Viaje?» dejaría de tener una respuesta.
        """
        ...
