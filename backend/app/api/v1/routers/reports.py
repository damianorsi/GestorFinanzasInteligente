"""Endpoints de reportes."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    CurrentUser,
    get_category_breakdown,
    get_monthly_trend,
    get_period_summary,
)
from app.api.v1.schemas.reports import (
    CategoryBreakdownResponse,
    MonthlyTrendResponse,
    PeriodSummaryResponse,
)
from app.application.use_cases.reports import (
    MESES_MAXIMOS_EN_TENDENCIA,
    MESES_POR_DEFECTO_EN_TENDENCIA,
    GetCategoryBreakdown,
    GetMonthlyTrend,
    GetPeriodSummary,
)
from app.core.errors import ValidationError
from app.domain.enums import TransactionType

router = APIRouter(prefix="/reports", tags=["reports"])

_DESCRIPCION_PERIODO = (
    "Sin `date_from`/`date_to` se usa el mes en curso, resuelto en la zona horaria "
    "de la aplicación."
)


@router.get(
    "/summary",
    response_model=PeriodSummaryResponse,
    summary="Totales del período",
    description=f"Ingresos, gastos y balance. {_DESCRIPCION_PERIODO} "
    "Un período sin movimientos devuelve ceros, no un error.",
)
async def resumen(
    usuario: CurrentUser,
    caso: Annotated[GetPeriodSummary, Depends(get_period_summary)],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> PeriodSummaryResponse:
    try:
        resultado = await caso.execute(usuario.id or 0, currency, date_from, date_to)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return PeriodSummaryResponse.desde(resultado)


@router.get(
    "/by-category",
    response_model=CategoryBreakdownResponse,
    summary="Agregado por categoría",
    description=f"Ordenado de mayor a menor, con el porcentaje sobre el total de su "
    f"tipo ya calculado. {_DESCRIPCION_PERIODO}",
)
async def por_categoria(
    usuario: CurrentUser,
    caso: Annotated[GetCategoryBreakdown, Depends(get_category_breakdown)],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    type: Annotated[TransactionType | None, Query()] = None,
) -> CategoryBreakdownResponse:
    try:
        resultado = await caso.execute(usuario.id or 0, currency, date_from, date_to, type)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return CategoryBreakdownResponse.desde(resultado)


@router.get(
    "/monthly-trend",
    response_model=MonthlyTrendResponse,
    summary="Serie mensual de ingresos y gastos",
    description=(
        "Incluye el mes en curso y los anteriores. Los meses sin movimientos vienen "
        "en cero y no se omiten, para que el gráfico no quede con agujeros."
    ),
)
async def tendencia_mensual(
    usuario: CurrentUser,
    caso: Annotated[GetMonthlyTrend, Depends(get_monthly_trend)],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    months: Annotated[
        int, Query(ge=1, le=MESES_MAXIMOS_EN_TENDENCIA)
    ] = MESES_POR_DEFECTO_EN_TENDENCIA,
) -> MonthlyTrendResponse:
    try:
        resultado = await caso.execute(usuario.id or 0, currency, months)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return MonthlyTrendResponse.desde(resultado)
