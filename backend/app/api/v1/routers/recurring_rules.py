"""Endpoints de reglas recurrentes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import (
    AppClock,
    CurrentUser,
    get_create_recurring_rule,
    get_delete_recurring_rule,
    get_list_recurring_rules,
    get_rule_occurrences,
    get_upcoming_occurrences,
    get_update_recurring_rule,
)
from app.api.v1.schemas.recurring import (
    OccurrenceResponse,
    RecurringRuleCreateRequest,
    RecurringRuleResponse,
    RecurringRuleUpdateRequest,
    UpcomingResponse,
)
from app.application.use_cases.recurring import (
    DIAS_MAXIMOS,
    DIAS_POR_DEFECTO,
    CreateRecurringRule,
    DeleteRecurringRule,
    GetRuleOccurrences,
    GetUpcomingOccurrences,
    ListRecurringRules,
    UpdateRecurringRule,
)
from app.domain.entities import RecurringRule
from app.domain.recurrence import proximas_fechas

router = APIRouter(prefix="/recurring-rules", tags=["recurring"])

FECHAS_EN_EL_PREVIEW = 3


def _con_preview(regla: RecurringRule, clock: AppClock) -> RecurringRuleResponse:
    """Adjunta las próximas fechas que la regla va a generar.

    Se calculan desde hoy y no desde `starts_on`: lo que interesa es qué va a
    pasar de acá en adelante, no qué hubiera pasado.
    """
    return RecurringRuleResponse.desde(
        regla, proximas_fechas(regla, clock.today(), FECHAS_EN_EL_PREVIEW)
    )


# `/upcoming` va antes que `/{rule_id}`, o el router lo tomaría por un id.
@router.get(
    "/upcoming",
    response_model=UpcomingResponse,
    summary="Vencimientos proyectados",
    description=(
        "Qué van a generar las reglas activas en los próximos días, calculado al vuelo. "
        "**Son una proyección**: no existen como movimientos y no participan del balance, "
        "de los reportes ni del export CSV."
    ),
)
async def proximos(
    usuario: CurrentUser,
    caso: Annotated[GetUpcomingOccurrences, Depends(get_upcoming_occurrences)],
    days: Annotated[int, Query(ge=1, le=DIAS_MAXIMOS)] = DIAS_POR_DEFECTO,
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
) -> UpcomingResponse:
    return UpcomingResponse.desde(await caso.execute(usuario.id or 0, days, currency))


@router.get(
    "",
    response_model=list[RecurringRuleResponse],
    summary="Listar las reglas recurrentes",
)
async def listar(
    usuario: CurrentUser,
    caso: Annotated[ListRecurringRules, Depends(get_list_recurring_rules)],
    clock: AppClock,
    is_active: Annotated[bool | None, Query()] = None,
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
) -> list[RecurringRuleResponse]:
    reglas = await caso.execute(usuario.id or 0, currency, is_active)
    return [_con_preview(regla, clock) for regla in reglas]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=RecurringRuleResponse,
    summary="Crear una regla recurrente",
    description=(
        "La respuesta trae `next_dates` con las próximas fechas que la regla va a generar, "
        "para confirmar de una que quedó bien configurada. La generación de movimientos "
        "la hace el job diario y **nunca materializa fechas futuras**."
    ),
)
async def crear(
    payload: RecurringRuleCreateRequest,
    usuario: CurrentUser,
    caso: Annotated[CreateRecurringRule, Depends(get_create_recurring_rule)],
    clock: AppClock,
    response: Response,
) -> RecurringRuleResponse:
    regla = await caso.execute(
        user_id=usuario.id or 0,
        category_id=payload.category_id,
        type=payload.type,
        amount=payload.amount,
        frequency=payload.frequency,
        starts_on=payload.starts_on,
        description=payload.description,
        day_of_month=payload.day_of_month,
        day_of_week=payload.day_of_week,
        ends_on=payload.ends_on,
        currency=payload.currency,
    )
    response.headers["Location"] = f"/api/v1/recurring-rules/{regla.id}"
    return _con_preview(regla, clock)


@router.patch(
    "/{rule_id}",
    response_model=RecurringRuleResponse,
    summary="Editar una regla (incluye pausar y reactivar)",
    description=(
        "Cambiar el monto afecta **solo a las ocurrencias futuras**: las ya generadas son "
        "movimientos reales y no se tocan. `is_active=false` pausa la generación sin borrar "
        "lo ya creado, y reactivar no dispara backfill del período pausado."
    ),
)
async def editar(
    rule_id: int,
    payload: RecurringRuleUpdateRequest,
    usuario: CurrentUser,
    caso: Annotated[UpdateRecurringRule, Depends(get_update_recurring_rule)],
    clock: AppClock,
) -> RecurringRuleResponse:
    # `model_fields_set` distingue "mandé null" de "no mandé el campo", que es
    # justo lo que hace falta para poder limpiar los días al cambiar de
    # frecuencia sin pisar los que no se tocaron.
    enviados = payload.model_fields_set
    regla = await caso.execute(
        usuario.id or 0,
        rule_id,
        category_id=payload.category_id,
        amount=payload.amount,
        frequency=payload.frequency,
        starts_on=payload.starts_on,
        description=payload.description,
        day_of_month=payload.day_of_month,
        day_of_week=payload.day_of_week,
        ends_on=payload.ends_on,
        is_active=payload.is_active,
        limpiar_ends_on=payload.clear_ends_on,
        limpiar_day_of_month="day_of_month" in enviados and payload.day_of_month is None,
        limpiar_day_of_week="day_of_week" in enviados and payload.day_of_week is None,
    )
    return _con_preview(regla, clock)


@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar una regla",
    description=(
        "**No borra los movimientos ya generados**: quedan como movimientos sueltos. "
        "Borrar una regla es dejar de generar hacia adelante, no reescribir el historial."
    ),
)
async def borrar(
    rule_id: int,
    usuario: CurrentUser,
    caso: Annotated[DeleteRecurringRule, Depends(get_delete_recurring_rule)],
) -> None:
    await caso.execute(usuario.id or 0, rule_id)


@router.get(
    "/{rule_id}/occurrences",
    response_model=list[OccurrenceResponse],
    summary="Historial de una regla",
    description=(
        "Qué generó la regla y qué se salteó. Una ocurrencia `GENERATED` con "
        "`transaction_id` en null es un movimiento que se generó y después se borró."
    ),
)
async def ocurrencias(
    rule_id: int,
    usuario: CurrentUser,
    caso: Annotated[GetRuleOccurrences, Depends(get_rule_occurrences)],
) -> list[OccurrenceResponse]:
    historial = await caso.execute(usuario.id or 0, rule_id)
    return [OccurrenceResponse.desde(ocurrencia) for ocurrencia in historial]
