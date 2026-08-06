"""Puerto de persistencia de reglas recurrentes."""

from __future__ import annotations

from typing import Protocol

from app.domain.entities import RecurringRule


class RecurringRuleRepository(Protocol):
    """Igual que el resto de los repositorios: `user_id` en todas las firmas.

    Las dos excepciones —`list_all_active` y `deactivate`— existen para el job
    y están documentadas abajo.
    """

    async def create(self, rule: RecurringRule) -> RecurringRule: ...

    async def update(self, rule: RecurringRule) -> RecurringRule: ...

    async def delete(self, user_id: int, rule_id: int) -> None:
        """Borra la regla.

        Los movimientos ya generados **no** se borran: la FK es SET NULL, así
        que quedan como movimientos sueltos. Borrar una regla es dejar de
        generar hacia adelante, no reescribir el historial.
        """
        ...

    async def get_for_user(self, user_id: int, rule_id: int) -> RecurringRule | None: ...

    async def list_for_user(
        self, user_id: int, currency: str, is_active: bool | None = None
    ) -> list[RecurringRule]:
        """Reglas del usuario en esa moneda. `is_active=None` trae todas."""
        ...

    async def list_active_for_user(self, user_id: int, currency: str) -> list[RecurringRule]:
        """Atajo de solo lectura que usa el asistente."""
        ...

    async def list_all_active(self) -> list[RecurringRule]:
        """Reglas activas de **todos** los usuarios, para el job.

        Es la única consulta sin `user_id` de la aplicación, y lo es porque el
        job no atiende un request: no hay usuario autenticado del que sacarlo.
        No debe usarse desde ningún endpoint; la regla de aislamiento sigue
        valiendo para todo lo demás (docs/PROMPT.md §8).
        """
        ...

    async def deactivate(self, rule_id: int) -> None:
        """Pausa una regla sin borrarla.

        Sin `user_id` por la misma razón que `list_all_active`: la usa el job
        cuando una regla quedó apuntando a una categoría que ya no existe.
        """
        ...
