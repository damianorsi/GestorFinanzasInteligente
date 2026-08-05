"""Schemas de request y response de movimientos."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.application.dtos import ORDEN_POR_DEFECTO, SortCriterion, SortDirection, SortField
from app.core.errors import ValidationError
from app.domain.entities import Transaction
from app.domain.enums import TransactionType

_CONFIG_REQUEST = ConfigDict(extra="forbid")

PRECISION_MONTO = 14
DECIMALES_MONTO = 2
LARGO_MAXIMO_DESCRIPCION = 255


class TransactionCreateRequest(BaseModel):
    model_config = _CONFIG_REQUEST

    type: TransactionType
    # `decimal_places=2` corta acá los montos con más precisión de la que la
    # base puede guardar, en vez de dejar que MySQL los redondee en silencio.
    amount: Decimal = Field(gt=0, max_digits=PRECISION_MONTO, decimal_places=DECIMALES_MONTO)
    occurred_on: date
    category_id: int = Field(gt=0)
    description: str = Field(default="", max_length=LARGO_MAXIMO_DESCRIPCION)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class TransactionUpdateRequest(BaseModel):
    """La moneda no está: en v1 hay una sola y cambiarla no es editar un campo
    sino convertir un importe, que necesita cotización y política."""

    model_config = _CONFIG_REQUEST

    type: TransactionType | None = None
    amount: Decimal | None = Field(
        default=None, gt=0, max_digits=PRECISION_MONTO, decimal_places=DECIMALES_MONTO
    )
    occurred_on: date | None = None
    category_id: int | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=LARGO_MAXIMO_DESCRIPCION)

    @model_validator(mode="after")
    def _exigir_algun_cambio(self) -> Self:
        if all(
            valor is None
            for valor in (
                self.type,
                self.amount,
                self.occurred_on,
                self.category_id,
                self.description,
            )
        ):
            raise ValueError("Indicá al menos un campo a modificar.")
        return self


class TransactionResponse(BaseModel):
    id: int
    type: TransactionType
    # El monto viaja como string: un número JSON lo parsea el cliente como
    # float de doble precisión y 1234.56 deja de ser exactamente 1234.56.
    amount: str
    currency: str
    occurred_on: date
    category_id: int
    description: str
    is_recurring: bool

    @classmethod
    def desde(cls, movimiento: Transaction) -> TransactionResponse:
        return cls(
            id=movimiento.id or 0,
            type=movimiento.type,
            amount=str(movimiento.money.amount),
            currency=movimiento.money.currency,
            occurred_on=movimiento.occurred_on,
            category_id=movimiento.category_id,
            description=movimiento.description,
            is_recurring=movimiento.is_recurring,
        )


class PaginatedTransactions(BaseModel):
    entries: list[TransactionResponse]
    offset: int
    limit: int
    totalCount: int  # noqa: N815 - el contrato de paginación lo define así


def parsear_sort(crudo: str | None) -> tuple[SortCriterion, ...]:
    """Traduce `?sort=-occurred_on,amount` a criterios tipados.

    El nombre del campo se valida contra una lista blanca antes de llegar al
    repositorio: aceptar un nombre de columna arbitrario desde la query string
    sería inyección de SQL por la puerta de atrás, incluso pasando por el ORM.
    """
    if not crudo or not crudo.strip():
        return ORDEN_POR_DEFECTO

    criterios: list[SortCriterion] = []
    for parte in crudo.split(","):
        expresion = parte.strip()
        if not expresion:
            continue
        direccion = SortDirection.DESC if expresion.startswith("-") else SortDirection.ASC
        nombre = expresion.lstrip("+-")
        try:
            campo = SortField(nombre)
        except ValueError as exc:
            permitidos = ", ".join(sorted(f.value for f in SortField))
            raise ValidationError(
                f"No se puede ordenar por «{nombre}». Campos válidos: {permitidos}."
            ) from exc
        criterios.append(SortCriterion(campo, direccion))

    return tuple(criterios) or ORDEN_POR_DEFECTO
