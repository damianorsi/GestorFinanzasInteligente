"""Puerto de lectura de reglas recurrentes.

Por ahora expone solo lo que necesita el asistente para responder "¿qué gastos
fijos tengo?". El ABM completo y la proyección de fechas llegan en la fase 12.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.entities import RecurringRule


class RecurringRuleRepository(Protocol):
    async def list_active_for_user(self, user_id: int, currency: str) -> list[RecurringRule]:
        """Reglas activas del usuario en esa moneda."""
        ...
