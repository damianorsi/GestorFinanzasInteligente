"""Schemas de request y response de reglas recurrentes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.application.dtos import UpcomingSummary
from app.domain.entities import RecurringOccurrence, RecurringRule
from app.domain.enums import (
    OccurrenceStatus,
    RecurrenceFrequency,
    TransactionType,
)

_CONFIG_REQUEST = ConfigDict(extra="forbid")

PRECISION_MONTO = 14
DECIMALES_MONTO = 2
LARGO_MAXIMO_DESCRIPCION = 255
DIA_DEL_MES_MAXIMO = 31
DIA_DE_LA_SEMANA_MAXIMO = 6

_DESCRIPCION_DIA_DEL_MES = "Solo para MONTHLY. Si el mes no lo tiene, se ajusta al último día."
_DESCRIPCION_DIA_SEMANA = "Solo para WEEKLY. 0 es lunes y 6 es domingo."


def _validar_parametros_de_frecuencia(
    frecuencia: RecurrenceFrequency, day_of_month: int | None, day_of_week: int | None
) -> None:
    """Cada frecuencia exige exactamente los parámetros que usa.

    Se valida acá además de en la entidad para que el error salga como un 422
    con el campo señalado, en vez de un error de dominio genérico.
    """
    if frecuencia is RecurrenceFrequency.MONTHLY and day_of_month is None:
        raise ValueError("Una regla mensual necesita day_of_month.")
    if frecuencia is RecurrenceFrequency.WEEKLY and day_of_week is None:
        raise ValueError("Una regla semanal necesita day_of_week.")
    if frecuencia is not RecurrenceFrequency.MONTHLY and day_of_month is not None:
        raise ValueError(f"La frecuencia {frecuencia} no usa day_of_month.")
    if frecuencia is not RecurrenceFrequency.WEEKLY and day_of_week is not None:
        raise ValueError(f"La frecuencia {frecuencia} no usa day_of_week.")


class RecurringRuleCreateRequest(BaseModel):
    model_config = _CONFIG_REQUEST

    category_id: int = Field(gt=0)
    type: TransactionType
    amount: Decimal = Field(gt=0, max_digits=PRECISION_MONTO, decimal_places=DECIMALES_MONTO)
    frequency: RecurrenceFrequency
    starts_on: date
    description: str = Field(default="", max_length=LARGO_MAXIMO_DESCRIPCION)
    day_of_month: int | None = Field(
        default=None, ge=1, le=DIA_DEL_MES_MAXIMO, description=_DESCRIPCION_DIA_DEL_MES
    )
    day_of_week: int | None = Field(
        default=None, ge=0, le=DIA_DE_LA_SEMANA_MAXIMO, description=_DESCRIPCION_DIA_SEMANA
    )
    ends_on: date | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)

    @model_validator(mode="after")
    def _coherente(self) -> RecurringRuleCreateRequest:
        _validar_parametros_de_frecuencia(self.frequency, self.day_of_month, self.day_of_week)
        if self.ends_on is not None and self.ends_on < self.starts_on:
            raise ValueError("ends_on no puede ser anterior a starts_on.")
        return self


class RecurringRuleUpdateRequest(BaseModel):
    """Edición parcial.

    No se puede cambiar el `type` ni la moneda: cambiarlos dejaría las
    ocurrencias ya generadas describiendo algo distinto de lo que la regla dice
    ahora. Para eso conviene borrar la regla y crear otra.
    """

    model_config = _CONFIG_REQUEST

    category_id: int | None = Field(default=None, gt=0)
    amount: Decimal | None = Field(
        default=None, gt=0, max_digits=PRECISION_MONTO, decimal_places=DECIMALES_MONTO
    )
    frequency: RecurrenceFrequency | None = None
    starts_on: date | None = None
    description: str | None = Field(default=None, max_length=LARGO_MAXIMO_DESCRIPCION)
    day_of_month: int | None = Field(default=None, ge=1, le=DIA_DEL_MES_MAXIMO)
    day_of_week: int | None = Field(default=None, ge=0, le=DIA_DE_LA_SEMANA_MAXIMO)
    ends_on: date | None = None
    is_active: bool | None = None
    # Los `null` no se distinguen de "no lo mandé" en un PATCH, así que sacar
    # una fecha de fin necesita un campo propio.
    clear_ends_on: bool = False


class RecurringRuleResponse(BaseModel):
    id: int
    category_id: int
    type: TransactionType
    amount: str
    currency: str
    description: str
    frequency: RecurrenceFrequency
    day_of_month: int | None
    day_of_week: int | None
    starts_on: date
    ends_on: date | None
    is_active: bool
    # Las próximas fechas que la regla va a generar. Es el feedback inmediato
    # de que quedó bien configurada.
    next_dates: list[date] = Field(default_factory=list)

    @classmethod
    def desde(
        cls, regla: RecurringRule, next_dates: list[date] | None = None
    ) -> RecurringRuleResponse:
        return cls(
            id=regla.id or 0,
            category_id=regla.category_id,
            type=regla.type,
            amount=str(regla.money.amount),
            currency=regla.money.currency,
            description=regla.description,
            frequency=regla.frequency,
            day_of_month=regla.day_of_month,
            day_of_week=regla.day_of_week,
            starts_on=regla.starts_on,
            ends_on=regla.ends_on,
            is_active=regla.is_active,
            next_dates=next_dates or [],
        )


class OccurrenceResponse(BaseModel):
    id: int
    occurred_on: date
    status: OccurrenceStatus
    # Null en una GENERATED significa que el movimiento se borró después.
    transaction_id: int | None

    @classmethod
    def desde(cls, ocurrencia: RecurringOccurrence) -> OccurrenceResponse:
        return cls(
            id=ocurrencia.id or 0,
            occurred_on=ocurrencia.occurred_on,
            status=ocurrencia.status,
            transaction_id=ocurrencia.transaction_id,
        )


class UpcomingEntryResponse(BaseModel):
    rule_id: int
    category_id: int
    description: str
    amount: str
    currency: str
    type: TransactionType
    due_on: date


class UpcomingResponse(BaseModel):
    """Vencimientos **proyectados**.

    No son movimientos: no entran en el balance, ni en los reportes, ni en el
    export CSV (docs/PROMPT.md §9).
    """

    date_from: date
    date_to: date
    currency: str
    entries: list[UpcomingEntryResponse]
    projected_income: str
    projected_expense: str

    @classmethod
    def desde(cls, resumen: UpcomingSummary) -> UpcomingResponse:
        return cls(
            date_from=resumen.date_from,
            date_to=resumen.date_to,
            currency=resumen.currency,
            entries=[
                UpcomingEntryResponse(
                    rule_id=entrada.rule_id,
                    category_id=entrada.category_id,
                    description=entrada.description,
                    amount=str(entrada.money.amount),
                    currency=entrada.money.currency,
                    type=TransactionType.INCOME
                    if entrada.type_is_income
                    else TransactionType.EXPENSE,
                    due_on=entrada.due_on,
                )
                for entrada in resumen.entries
            ],
            projected_income=str(resumen.projected_income.amount),
            projected_expense=str(resumen.projected_expense.amount),
        )
