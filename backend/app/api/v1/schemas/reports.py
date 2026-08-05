"""Schemas de respuesta de los reportes."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.application.dtos import CategoryBreakdown, MonthlyTrend, PeriodSummary
from app.domain.calendar import etiqueta_de_periodo
from app.domain.enums import TransactionType


class PeriodSummaryResponse(BaseModel):
    currency: str
    date_from: date
    date_to: date
    # Como en el resto de la API, los montos van como string.
    income: str
    expense: str
    balance: str

    @classmethod
    def desde(cls, resumen: PeriodSummary) -> PeriodSummaryResponse:
        return cls(
            currency=resumen.currency,
            date_from=resumen.date_from,
            date_to=resumen.date_to,
            income=str(resumen.income.amount),
            expense=str(resumen.expense.amount),
            balance=str(resumen.balance.amount),
        )


class CategoryTotalResponse(BaseModel):
    category_id: int
    category_name: str
    type: TransactionType
    total: str
    percentage: str
    transaction_count: int


class CategoryBreakdownResponse(BaseModel):
    currency: str
    date_from: date
    date_to: date
    entries: list[CategoryTotalResponse]

    @classmethod
    def desde(cls, desglose: CategoryBreakdown) -> CategoryBreakdownResponse:
        return cls(
            currency=desglose.currency,
            date_from=desglose.date_from,
            date_to=desglose.date_to,
            entries=[
                CategoryTotalResponse(
                    category_id=entrada.category_id,
                    category_name=entrada.category_name,
                    type=entrada.type,
                    total=str(entrada.total.amount),
                    percentage=str(desglose.porcentaje_de(entrada)),
                    transaction_count=entrada.transaction_count,
                )
                for entrada in desglose.entries
            ],
        )


class MonthlyTotalResponse(BaseModel):
    period: str
    income: str
    expense: str
    balance: str


class MonthlyTrendResponse(BaseModel):
    currency: str
    entries: list[MonthlyTotalResponse]

    @classmethod
    def desde(cls, tendencia: MonthlyTrend) -> MonthlyTrendResponse:
        return cls(
            currency=tendencia.currency,
            entries=[
                MonthlyTotalResponse(
                    period=etiqueta_de_periodo(entrada.period),
                    income=str(entrada.income.amount),
                    expense=str(entrada.expense.amount),
                    balance=str(entrada.balance.amount),
                )
                for entrada in tendencia.entries
            ],
        )
