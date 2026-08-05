"""DTOs de presupuestos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.enums import BudgetStatus
from app.domain.value_objects import Money


@dataclass(frozen=True, slots=True)
class BudgetProgress:
    """Avance de un presupuesto en su mes."""

    budget_id: int
    category_id: int
    category_name: str
    budgeted: Money
    spent: Money
    remaining: Money
    percentage: Decimal
    status: BudgetStatus


@dataclass(frozen=True, slots=True)
class UnbudgetedSpending:
    """Gasto en una categoría que no tiene presupuesto para el período.

    Se devuelve aparte para que la persona usuaria vea qué le falta
    presupuestar: si solo se listaran las categorías con tope, el mes parecería
    controlado aunque el grueso del gasto esté en categorías sin presupuesto.
    """

    category_id: int
    category_name: str
    spent: Money


@dataclass(frozen=True, slots=True)
class BudgetProgressReport:
    currency: str
    period_month: date
    entries: list[BudgetProgress]
    unbudgeted: list[UnbudgetedSpending]

    @property
    def excedidos(self) -> int:
        return sum(1 for entrada in self.entries if entrada.status is BudgetStatus.EXCEEDED)


@dataclass(frozen=True, slots=True)
class SkippedBudget:
    category_id: int
    category_name: str


@dataclass(frozen=True, slots=True)
class BudgetCopyResult:
    """Resultado de copiar los presupuestos de un período a otro.

    Los que ya existían en el destino se informan en vez de pisarse: sobrescribir
    en silencio destruiría un tope que la persona usuaria ya había ajustado a
    mano para ese mes.
    """

    from_period: date
    to_period: date
    currency: str
    created: int
    skipped: list[SkippedBudget]
