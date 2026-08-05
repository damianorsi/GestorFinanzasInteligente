"""Entidad `Budget`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.domain.exceptions import InvalidBudgetError
from app.domain.value_objects import Money


@dataclass(slots=True)
class Budget:
    """Tope mensual de gasto para una categoría, en una moneda.

    Solo aplica a categorías de tipo EXPENSE. Esa validación necesita conocer
    la categoría, así que vive en el caso de uso y no acá: la entidad no tiene
    forma de resolver `category_id` sin salir del dominio.
    """

    user_id: int
    category_id: int
    period_month: date
    limit: Money
    id: int | None = None

    def __post_init__(self) -> None:
        if self.period_month.day != 1:
            raise InvalidBudgetError(
                f"El período debe ser el día 1 del mes, se recibió {self.period_month.isoformat()}."
            )
        if not self.limit.is_positive:
            raise InvalidBudgetError(
                f"El tope del presupuesto debe ser mayor a cero, se recibió {self.limit}."
            )

    @property
    def currency(self) -> str:
        return self.limit.currency

    @staticmethod
    def periodo(anio: int, mes: int) -> date:
        """Construye el `period_month` canónico de un año y mes dados."""
        return date(anio, mes, 1)

    def cubre(self, dia: date) -> bool:
        """Si una fecha cae dentro del mes presupuestado."""
        return (dia.year, dia.month) == (self.period_month.year, self.period_month.month)
