"""Endpoints de alertas de presupuesto."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, get_list_alerts, get_mark_alert_read
from app.api.v1.schemas.alerts import AlertResponse, AlertUpdateRequest
from app.application.use_cases.alerts import ListAlerts, MarkAlertRead
from app.domain.enums import AlertStatus

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get(
    "",
    response_model=list[AlertResponse],
    summary="Listar las alertas de desvío",
    description=(
        "Desvíos presupuestarios detectados por el job diario, de la más reciente a la "
        "más vieja. Incluye las que proyectan superar el tope antes de fin de mes, que "
        "es lo que permite corregir a tiempo.\n\n"
        "`recommendation` viene en null cuando el proveedor del modelo no respondió: la "
        "alerta se emite igual, porque saber que te estás pasando no depende de eso."
    ),
)
async def listar(
    usuario: CurrentUser,
    caso: Annotated[ListAlerts, Depends(get_list_alerts)],
    status: Annotated[AlertStatus | None, Query()] = None,
) -> list[AlertResponse]:
    alertas = await caso.execute(usuario.id or 0, status)
    return [AlertResponse.desde(alerta) for alerta in alertas]


@router.patch(
    "/{alert_id}",
    response_model=AlertResponse,
    summary="Marcar una alerta como leída",
    description=(
        "Leerla **no la resuelve**: el desvío sigue existiendo hasta que baje el gasto o "
        "suba el tope, y eso lo detecta el job en su próxima corrida."
    ),
)
async def marcar_leida(
    alert_id: int,
    payload: AlertUpdateRequest,
    usuario: CurrentUser,
    caso: Annotated[MarkAlertRead, Depends(get_mark_alert_read)],
) -> AlertResponse:
    # `payload` solo admite `{"read": true}`: el schema lo valida y no hay nada
    # que ramificar acá.
    _ = payload
    return AlertResponse.desde(await caso.execute(usuario.id or 0, alert_id))
