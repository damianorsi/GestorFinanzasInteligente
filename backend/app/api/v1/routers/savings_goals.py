"""Endpoints de metas de ahorro (docs/PROMPT.md §21.3)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import (
    CurrentUser,
    get_create_savings_goal,
    get_delete_savings_goal,
    get_list_savings_goals,
    get_savings_goals_progress,
    get_update_savings_goal,
)
from app.api.v1.schemas.savings import (
    SavingsGoalCreateRequest,
    SavingsGoalProgressResponse,
    SavingsGoalResponse,
    SavingsGoalUpdateRequest,
)
from app.application.use_cases.savings import (
    CreateSavingsGoal,
    DeleteSavingsGoal,
    GetSavingsGoalsProgress,
    ListSavingsGoals,
    UpdateSavingsGoal,
)

router = APIRouter(prefix="/savings-goals", tags=["savings-goals"])


@router.get(
    "",
    response_model=list[SavingsGoalResponse],
    summary="Listar las metas de ahorro",
)
async def listar(
    usuario: CurrentUser,
    caso: Annotated[ListSavingsGoals, Depends(get_list_savings_goals)],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    only_active: Annotated[bool, Query()] = True,
) -> list[SavingsGoalResponse]:
    metas = await caso.execute(usuario.id or 0, currency, only_active)
    return [SavingsGoalResponse.desde(meta) for meta in metas]


@router.get(
    "/progress",
    response_model=list[SavingsGoalProgressResponse],
    summary="Avance y proyección de cada meta",
    description=(
        "El avance se mide contra el **balance acumulado desde `starts_on`**: el producto "
        "no maneja cuentas, así que no hay un saldo ahorrado que consultar.\n\n"
        "`projection` viene en null cuando hay menos de dos meses cerrados de historial. "
        "**No es un modelo predictivo**: es el balance mensual promedio aplicado a lo que "
        "falta, y por eso `months_of_history` dice sobre cuántos meses se calculó. "
        "`status` también viene en null en ese caso, porque «no sabemos» no es lo mismo "
        "que `AT_RISK`."
    ),
)
async def avance(
    usuario: CurrentUser,
    caso: Annotated[GetSavingsGoalsProgress, Depends(get_savings_goals_progress)],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
) -> list[SavingsGoalProgressResponse]:
    avances = await caso.execute(usuario.id or 0, currency)
    return [SavingsGoalProgressResponse.desde(item) for item in avances]


@router.post(
    "",
    response_model=SavingsGoalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una meta",
    description=(
        "Sin `starts_on`, la meta arranca hoy: contar como ahorro un balance que ya se "
        "gastó inflaría el avance desde el minuto cero."
    ),
)
async def crear(
    payload: SavingsGoalCreateRequest,
    usuario: CurrentUser,
    respuesta: Response,
    caso: Annotated[CreateSavingsGoal, Depends(get_create_savings_goal)],
) -> SavingsGoalResponse:
    meta = await caso.execute(
        usuario.id or 0,
        name=payload.name,
        target_amount=payload.target_amount,
        starts_on=payload.starts_on,
        target_date=payload.target_date,
        currency=payload.currency,
    )
    respuesta.headers["Location"] = f"{router.prefix}/{meta.id}"
    return SavingsGoalResponse.desde(meta)


@router.patch(
    "/{goal_id}",
    response_model=SavingsGoalResponse,
    summary="Editar una meta",
    description=(
        "`is_active=false` la pausa: deja de aparecer en el avance sin borrarla.\n\n"
        "Para sacar la fecha objetivo hay que mandar `clear_target_date: true`, porque "
        "`target_date: null` significa «no lo toques»."
    ),
)
async def editar(
    goal_id: int,
    payload: SavingsGoalUpdateRequest,
    usuario: CurrentUser,
    caso: Annotated[UpdateSavingsGoal, Depends(get_update_savings_goal)],
) -> SavingsGoalResponse:
    meta = await caso.execute(
        usuario.id or 0,
        goal_id,
        name=payload.name,
        target_amount=payload.target_amount,
        starts_on=payload.starts_on,
        target_date=payload.target_date,
        is_active=payload.is_active,
        limpiar_target_date=payload.clear_target_date,
    )
    return SavingsGoalResponse.desde(meta)


@router.delete(
    "/{goal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar una meta",
    description=(
        "**No toca los movimientos**: la meta es una lectura sobre el balance, no una "
        "cuenta con plata adentro. Borrarla es dejar de medir contra ese objetivo."
    ),
)
async def borrar(
    goal_id: int,
    usuario: CurrentUser,
    caso: Annotated[DeleteSavingsGoal, Depends(get_delete_savings_goal)],
) -> None:
    await caso.execute(usuario.id or 0, goal_id)
