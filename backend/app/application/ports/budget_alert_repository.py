"""Puerto de persistencia de alertas de presupuesto."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from app.domain.entities import BudgetAlert
from app.domain.enums import AlertStatus


class BudgetAlertRepository(Protocol):
    async def list_for_user(
        self, user_id: int, status: AlertStatus | None = None
    ) -> list[BudgetAlert]:
        """Alertas del usuario, de la más reciente a la más vieja."""
        ...

    async def get_for_user(self, user_id: int, alert_id: int) -> BudgetAlert | None: ...

    async def update(self, alert: BudgetAlert) -> BudgetAlert: ...

    async def create_if_absent(self, alert: BudgetAlert) -> BudgetAlert | None:
        """Crea la alerta, o devuelve `None` si ya existía.

        La UNIQUE `(user_id, category_id, period_month, type)` es la garantía
        de idempotencia del job: correrlo cincuenta veces tiene que dejar las
        mismas alertas que correrlo una. Una ya emitida —abierta, leída o
        resuelta— no se vuelve a crear.
        """
        ...

    async def resolve_stale(self, user_id: int, period_month: date, vigentes: set[int]) -> int:
        """Marca como resueltas las alertas del período que ya no aplican.

        `vigentes` son los ids de alerta que el job volvió a detectar en esta
        corrida. Las que no están ahí dejaron de ser ciertas —bajó el gasto,
        subió el tope— y pasan a `RESOLVED` en vez de borrarse: borrarlas haría
        que el job las volviera a emitir mañana.
        """
        ...

    async def list_open_period_ids(self, user_id: int, period_month: date) -> set[int]:
        """Ids de las alertas del período que siguen abiertas o leídas."""
        ...
