"""Entidad `BudgetAlert`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.enums import AlertStatus, AlertType
from app.domain.exceptions import InvalidBudgetError


@dataclass(slots=True)
class BudgetAlert:
    """Un desvío presupuestario detectado por el job.

    `recommendation` es opcional a propósito: la redacta el agente, y si el
    proveedor no responde **la alerta se emite igual**. Saber que te estás
    pasando no depende de que el modelo esté disponible (docs/PROMPT.md §21.2).
    """

    user_id: int
    category_id: int
    period_month: date
    type: AlertType
    message: str
    status: AlertStatus = AlertStatus.OPEN
    recommendation: str | None = None
    projected_percentage: Decimal | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if self.period_month.day != 1:
            raise InvalidBudgetError(
                f"El período debe ser el día 1 del mes, se recibió {self.period_month.isoformat()}."
            )
        if not self.message.strip():
            raise InvalidBudgetError("La alerta necesita un mensaje.")
        self.message = self.message.strip()

    @property
    def esta_abierta(self) -> bool:
        return self.status is AlertStatus.OPEN

    def marcar_leida(self) -> None:
        """Leerla no la resuelve: el desvío sigue ahí hasta que se corrija."""
        if self.status is AlertStatus.OPEN:
            self.status = AlertStatus.READ
