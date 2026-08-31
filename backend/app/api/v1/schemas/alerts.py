"""Schemas de las alertas de presupuesto."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.domain.calendar import etiqueta_de_periodo
from app.domain.entities import BudgetAlert
from app.domain.enums import AlertStatus, AlertType


class AlertResponse(BaseModel):
    id: int
    category_id: int
    period_month: str
    type: AlertType
    status: AlertStatus
    message: str
    # Null cuando el proveedor del modelo no respondió: la alerta se emite
    # igual, porque su valor no depende de la recomendación.
    recommendation: str | None
    # Solo en las de riesgo: qué porcentaje del tope proyecta consumir el mes.
    projected_percentage: str | None

    @classmethod
    def desde(cls, alerta: BudgetAlert) -> AlertResponse:
        return cls(
            id=alerta.id or 0,
            category_id=alerta.category_id,
            period_month=etiqueta_de_periodo(alerta.period_month),
            type=alerta.type,
            status=alerta.status,
            message=alerta.message,
            recommendation=alerta.recommendation,
            projected_percentage=(
                None if alerta.projected_percentage is None else str(alerta.projected_percentage)
            ),
        )


class AlertUpdateRequest(BaseModel):
    """Marcar como leída es lo único que se puede hacer desde afuera.

    Resolverla la decide el job cuando el desvío deja de ser cierto: si se
    pudiera resolver a mano, el job la volvería a emitir en la corrida
    siguiente y la persona vería la misma alerta para siempre.
    """

    model_config = {"extra": "forbid"}

    # `Literal[True]`: no existe "desleer" una alerta. Aceptar `false` y no
    # hacer nada sería un endpoint que miente sobre lo que puede hacer.
    read: Literal[True]
