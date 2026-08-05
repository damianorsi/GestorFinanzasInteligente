"""DTOs de filtrado y ordenamiento de movimientos."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum

from app.domain.enums import TransactionType


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class SortField(StrEnum):
    """Campos por los que se puede ordenar.

    Es una lista blanca cerrada a propósito: aceptar un nombre de columna
    arbitrario desde la query string sería inyección de SQL por la puerta de
    atrás, incluso pasando por el ORM.
    """

    OCCURRED_ON = "occurred_on"
    AMOUNT = "amount"
    CREATED_AT = "created_at"
    DESCRIPTION = "description"


@dataclass(frozen=True, slots=True)
class SortCriterion:
    field: SortField
    direction: SortDirection


# Los más recientes primero, que es lo que espera ver alguien al abrir la lista.
ORDEN_POR_DEFECTO: tuple[SortCriterion, ...] = (
    SortCriterion(SortField.OCCURRED_ON, SortDirection.DESC),
    SortCriterion(SortField.CREATED_AT, SortDirection.DESC),
)


@dataclass(frozen=True, slots=True)
class TransactionExportRow:
    """Una fila del export, con la categoría ya resuelta a su nombre.

    El CSV lo lee una persona, no la API: por eso lleva el nombre y no el id.
    """

    id: int
    occurred_on: date
    type: TransactionType
    category_name: str
    description: str
    amount: Decimal
    currency: str
    is_recurring: bool


@dataclass(frozen=True, slots=True)
class TransactionFilters:
    """Filtros del listado de movimientos.

    `currency` no es opcional: toda agregación y todo listado se acota a una
    moneda. Es la regla que hace seguro habilitar USD más adelante.
    """

    currency: str
    date_from: date | None = None
    date_to: date | None = None
    category_id: int | None = None
    type: TransactionType | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    q: str | None = None
    is_recurring: bool | None = None
    sort: tuple[SortCriterion, ...] = field(default=ORDEN_POR_DEFECTO)

    def __post_init__(self) -> None:
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from no puede ser posterior a date_to.")
        if (
            self.min_amount is not None
            and self.max_amount is not None
            and self.min_amount > self.max_amount
        ):
            raise ValueError("min_amount no puede ser mayor que max_amount.")
