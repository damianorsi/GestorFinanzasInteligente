"""Endpoints de presupuestos."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import (
    CurrentUser,
    get_budget_progress,
    get_copy_budgets,
    get_create_budget,
    get_delete_budget,
    get_list_budgets,
    get_update_budget,
)
from app.api.v1.schemas.budgets import (
    BudgetCopyRequest,
    BudgetCopyResponse,
    BudgetCreateRequest,
    BudgetProgressResponse,
    BudgetResponse,
    BudgetUpdateRequest,
    PeriodoMensual,
)
from app.application.use_cases.budgets import (
    CopyBudgets,
    CreateBudget,
    DeleteBudget,
    GetBudgetProgress,
    ListBudgets,
    UpdateBudget,
)

router = APIRouter(prefix="/budgets", tags=["budgets"])

_DESCRIPCION_PERIODO = "Mes en formato `AAAA-MM`, por ejemplo `2026-08`."


# `/progress` y `/copy-from` van antes que `/{budget_id}`, o el router intentaría
# interpretarlos como identificadores.
@router.get(
    "/progress",
    response_model=BudgetProgressResponse,
    summary="Avance de los presupuestos del mes",
    description=(
        "Cruza cada tope con lo efectivamente gastado. Las categorías con gasto pero "
        "sin presupuesto vienen aparte en `unbudgeted`, para que no parezca que el mes "
        "está controlado cuando el grueso del gasto no tiene tope. Solo cuenta "
        "movimientos reales: las proyecciones futuras no inflan el gasto."
    ),
)
async def progreso(
    usuario: CurrentUser,
    caso: Annotated[GetBudgetProgress, Depends(get_budget_progress)],
    period_month: Annotated[PeriodoMensual, Query(description=_DESCRIPCION_PERIODO)],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
) -> BudgetProgressResponse:
    return BudgetProgressResponse.desde(await caso.execute(usuario.id or 0, period_month, currency))


@router.post(
    "/copy-from",
    status_code=status.HTTP_201_CREATED,
    response_model=BudgetCopyResponse,
    summary="Copiar los presupuestos de un mes a otro",
    description=(
        "Los que ya existen en el destino no se pisan: se informan en `skipped`. "
        "Sobrescribir en silencio destruiría un tope ya ajustado a mano para ese mes."
    ),
)
async def copiar(
    payload: BudgetCopyRequest,
    usuario: CurrentUser,
    caso: Annotated[CopyBudgets, Depends(get_copy_budgets)],
) -> BudgetCopyResponse:
    return BudgetCopyResponse.desde(
        await caso.execute(
            user_id=usuario.id or 0,
            from_period=payload.from_period,
            to_period=payload.to_period,
            currency=payload.currency,
        )
    )


@router.get(
    "",
    response_model=list[BudgetResponse],
    summary="Listar los presupuestos de un mes",
)
async def listar(
    usuario: CurrentUser,
    caso: Annotated[ListBudgets, Depends(get_list_budgets)],
    period_month: Annotated[PeriodoMensual, Query(description=_DESCRIPCION_PERIODO)],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
) -> list[BudgetResponse]:
    presupuestos = await caso.execute(usuario.id or 0, period_month, currency)
    return [BudgetResponse.desde(presupuesto) for presupuesto in presupuestos]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=BudgetResponse,
    summary="Crear un presupuesto",
    description=(
        "Devuelve 409 si ya hay uno para esa categoría, mes y moneda, y 422 si la "
        "categoría es de ingreso: un presupuesto es un tope de gasto."
    ),
)
async def crear(
    payload: BudgetCreateRequest,
    usuario: CurrentUser,
    caso: Annotated[CreateBudget, Depends(get_create_budget)],
    response: Response,
) -> BudgetResponse:
    presupuesto = await caso.execute(
        user_id=usuario.id or 0,
        category_id=payload.category_id,
        period_month=payload.period_month,
        amount=payload.amount,
        currency=payload.currency,
    )
    response.headers["Location"] = f"/api/v1/budgets/{presupuesto.id}"
    return BudgetResponse.desde(presupuesto)


@router.patch(
    "/{budget_id}",
    response_model=BudgetResponse,
    summary="Editar el tope de un presupuesto",
)
async def editar(
    budget_id: int,
    payload: BudgetUpdateRequest,
    usuario: CurrentUser,
    caso: Annotated[UpdateBudget, Depends(get_update_budget)],
) -> BudgetResponse:
    return BudgetResponse.desde(await caso.execute(usuario.id or 0, budget_id, payload.amount))


@router.delete(
    "/{budget_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar un presupuesto",
)
async def borrar(
    budget_id: int,
    usuario: CurrentUser,
    caso: Annotated[DeleteBudget, Depends(get_delete_budget)],
) -> None:
    await caso.execute(usuario.id or 0, budget_id)
