"""Entidad `Transaction`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.domain.enums import TransactionType
from app.domain.exceptions import InvalidTransactionError
from app.domain.value_objects import Money

LARGO_MAXIMO_DESCRIPCION = 255


@dataclass(slots=True)
class Transaction:
    """Un ingreso o un gasto ya ocurrido.

    `occurred_on` es un `date` sin hora: al no tener hora no hay ambigüedad de
    zona horaria (docs/PROMPT.md §5.2).
    """

    user_id: int
    category_id: int
    type: TransactionType
    money: Money
    occurred_on: date
    description: str = ""
    id: int | None = None
    recurring_rule_id: int | None = None

    def __post_init__(self) -> None:
        if not self.money.is_positive:
            raise InvalidTransactionError(
                f"El monto de un movimiento debe ser mayor a cero, se recibió {self.money}. "
                "El signo lo determina el tipo (INCOME/EXPENSE), no el monto."
            )

        descripcion = self.description.strip()
        if len(descripcion) > LARGO_MAXIMO_DESCRIPCION:
            raise InvalidTransactionError(
                f"La descripción no puede superar los {LARGO_MAXIMO_DESCRIPCION} caracteres."
            )
        self.description = descripcion

    @property
    def currency(self) -> str:
        return self.money.currency

    @property
    def is_recurring(self) -> bool:
        """Si el movimiento lo generó una regla recurrente."""
        return self.recurring_rule_id is not None

    @property
    def signed_money(self) -> Money:
        """El monto con signo: positivo si es ingreso, negativo si es gasto.

        Es la forma de sumar ingresos y gastos en un solo agregado sin repartir
        el criterio del signo por toda la aplicación.
        """
        return self.money if self.type is TransactionType.INCOME else -self.money
