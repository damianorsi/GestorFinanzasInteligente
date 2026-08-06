"""DTOs de movimientos recurrentes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.domain.value_objects import Money


@dataclass(frozen=True, slots=True)
class UpcomingOccurrence:
    """Un vencimiento **proyectado**.

    No existe como movimiento y no participa de ningún reporte, del balance ni
    del export CSV: solo se calcula al vuelo para poder contestar "¿qué me
    queda por pagar?" (docs/PROMPT.md §9).
    """

    rule_id: int
    category_id: int
    description: str
    money: Money
    due_on: date
    type_is_income: bool


@dataclass(frozen=True, slots=True)
class UpcomingSummary:
    date_from: date
    date_to: date
    currency: str
    entries: list[UpcomingOccurrence]
    projected_income: Money
    projected_expense: Money


@dataclass(frozen=True, slots=True)
class GenerationResult:
    """Qué hizo una corrida del job.

    Se devuelve en vez de loguearse y nada más para que los tests puedan
    afirmar sobre el resultado sin leer logs, y para que el endpoint de salud
    pueda informar la última corrida.
    """

    as_of: date
    generated: int = 0
    already_resolved: int = 0
    rules_processed: int = 0
    rules_failed: int = 0
    rules_deactivated: int = 0
    # Reglas cuya ventana de catch-up se recortó por el tope de días.
    rules_truncated: list[int] = field(default_factory=list)
