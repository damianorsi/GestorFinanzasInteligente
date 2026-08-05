"""Schemas de request y response de presupuestos."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.application.dtos import (
    BudgetCopyResult,
    BudgetProgressReport,
)
from app.domain.calendar import etiqueta_de_periodo
from app.domain.entities import Budget
from app.domain.enums import BudgetStatus

_CONFIG_REQUEST = ConfigDict(extra="forbid")

PRECISION_MONTO = 14
DECIMALES_MONTO = 2
PARTES_DE_UN_PERIODO = 2


def _a_primer_dia_del_mes(valor: object) -> date:
    """Convierte `2026-08` al primer día de ese mes.

    El período viaja como `AAAA-MM` y no como fecha completa porque un
    presupuesto es de un mes entero: aceptar `2026-08-15` invitaría a creer
    que existen presupuestos que arrancan a mitad de mes.
    """
    if isinstance(valor, date):
        return valor.replace(day=1)
    if not isinstance(valor, str):
        raise ValueError("El período debe tener formato AAAA-MM.")
    partes = valor.split("-")
    if len(partes) != PARTES_DE_UN_PERIODO:
        raise ValueError("El período debe tener formato AAAA-MM.")
    try:
        return date(int(partes[0]), int(partes[1]), 1)
    except ValueError as exc:
        raise ValueError("El período debe tener formato AAAA-MM.") from exc


PeriodoMensual = Annotated[date, BeforeValidator(_a_primer_dia_del_mes)]


class BudgetCreateRequest(BaseModel):
    model_config = _CONFIG_REQUEST

    category_id: int = Field(gt=0)
    period_month: PeriodoMensual
    amount: Decimal = Field(gt=0, max_digits=PRECISION_MONTO, decimal_places=DECIMALES_MONTO)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class BudgetUpdateRequest(BaseModel):
    """Solo el tope.

    Categoría, período y moneda son lo que identifica al presupuesto: cambiarlos
    no sería editarlo sino crear otro, y podría chocar con uno existente.
    """

    model_config = _CONFIG_REQUEST

    amount: Decimal = Field(gt=0, max_digits=PRECISION_MONTO, decimal_places=DECIMALES_MONTO)


class BudgetCopyRequest(BaseModel):
    model_config = _CONFIG_REQUEST

    from_period: PeriodoMensual
    to_period: PeriodoMensual
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class BudgetResponse(BaseModel):
    id: int
    category_id: int
    period_month: str
    amount: str
    currency: str

    @classmethod
    def desde(cls, presupuesto: Budget) -> BudgetResponse:
        return cls(
            id=presupuesto.id or 0,
            category_id=presupuesto.category_id,
            period_month=etiqueta_de_periodo(presupuesto.period_month),
            amount=str(presupuesto.limit.amount),
            currency=presupuesto.limit.currency,
        )


class BudgetProgressEntryResponse(BaseModel):
    budget_id: int
    category_id: int
    category_name: str
    budgeted: str
    spent: str
    # Negativo si se excedió: decir "0 restante" ocultaría cuánto se pasó.
    remaining: str
    percentage: str
    status: BudgetStatus


class UnbudgetedSpendingResponse(BaseModel):
    category_id: int
    category_name: str
    spent: str


class BudgetProgressResponse(BaseModel):
    currency: str
    period_month: str
    entries: list[BudgetProgressEntryResponse]
    unbudgeted: list[UnbudgetedSpendingResponse]
    exceeded_count: int

    @classmethod
    def desde(cls, reporte: BudgetProgressReport) -> BudgetProgressResponse:
        return cls(
            currency=reporte.currency,
            period_month=etiqueta_de_periodo(reporte.period_month),
            entries=[
                BudgetProgressEntryResponse(
                    budget_id=entrada.budget_id,
                    category_id=entrada.category_id,
                    category_name=entrada.category_name,
                    budgeted=str(entrada.budgeted.amount),
                    spent=str(entrada.spent.amount),
                    remaining=str(entrada.remaining.amount),
                    percentage=str(entrada.percentage),
                    status=entrada.status,
                )
                for entrada in reporte.entries
            ],
            unbudgeted=[
                UnbudgetedSpendingResponse(
                    category_id=sin_tope.category_id,
                    category_name=sin_tope.category_name,
                    spent=str(sin_tope.spent.amount),
                )
                for sin_tope in reporte.unbudgeted
            ],
            exceeded_count=reporte.excedidos,
        )


class SkippedBudgetResponse(BaseModel):
    category_id: int
    category_name: str


class BudgetCopyResponse(BaseModel):
    from_period: str
    to_period: str
    currency: str
    created: int
    skipped: list[SkippedBudgetResponse]

    @classmethod
    def desde(cls, resultado: BudgetCopyResult) -> BudgetCopyResponse:
        return cls(
            from_period=etiqueta_de_periodo(resultado.from_period),
            to_period=etiqueta_de_periodo(resultado.to_period),
            currency=resultado.currency,
            created=resultado.created,
            skipped=[
                SkippedBudgetResponse(
                    category_id=salteado.category_id, category_name=salteado.category_name
                )
                for salteado in resultado.skipped
            ],
        )
