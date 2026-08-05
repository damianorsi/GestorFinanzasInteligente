"""DTOs de los reportes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.enums import TransactionType
from app.domain.value_objects import Money


@dataclass(frozen=True, slots=True)
class PeriodSummary:
    """Totales de un período en una moneda."""

    currency: str
    date_from: date
    date_to: date
    income: Money
    expense: Money

    @property
    def balance(self) -> Money:
        """Puede ser negativo: es una resta, no un total."""
        return self.income - self.expense


@dataclass(frozen=True, slots=True)
class CategoryTotal:
    category_id: int
    category_name: str
    type: TransactionType
    total: Money
    transaction_count: int


@dataclass(frozen=True, slots=True)
class CategoryBreakdown:
    """Agregado por categoría, con el porcentaje ya calculado.

    El porcentaje se calcula acá y no en el frontend para que el gráfico de
    torta y cualquier otro consumidor usen exactamente el mismo número.
    """

    currency: str
    date_from: date
    date_to: date
    entries: list[CategoryTotal]

    def porcentaje_de(self, entrada: CategoryTotal) -> Decimal:
        total_del_tipo = sum(
            (e.total.amount for e in self.entries if e.type is entrada.type),
            start=Decimal("0"),
        )
        if total_del_tipo == 0:
            return Decimal("0.00")
        return (entrada.total.amount / total_del_tipo * 100).quantize(Decimal("0.01"))


@dataclass(frozen=True, slots=True)
class MonthlyTotal:
    """Totales de un mes. `period` es el primer día del mes."""

    period: date
    income: Money
    expense: Money

    @property
    def balance(self) -> Money:
        return self.income - self.expense


@dataclass(frozen=True, slots=True)
class MonthlyTrend:
    currency: str
    entries: list[MonthlyTotal]
