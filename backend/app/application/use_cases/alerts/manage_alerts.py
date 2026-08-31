"""Casos de uso de lectura de alertas."""

from __future__ import annotations

import logging

from app.application.exceptions import ResourceNotFoundError
from app.application.ports import BudgetAlertRepository
from app.domain.entities import BudgetAlert
from app.domain.enums import AlertStatus

logger = logging.getLogger(__name__)


class ListAlerts:
    def __init__(self, alerts: BudgetAlertRepository) -> None:
        self._alerts = alerts

    async def execute(self, user_id: int, status: AlertStatus | None = None) -> list[BudgetAlert]:
        return await self._alerts.list_for_user(user_id, status)


class MarkAlertRead:
    """Marca una alerta como leída.

    Leerla **no la resuelve**: el desvío sigue existiendo hasta que baje el
    gasto o suba el tope, y eso lo decide el job en su próxima corrida. Si
    leerla la resolviera, el job la volvería a emitir al otro día y la persona
    vería la misma alerta para siempre.
    """

    def __init__(self, alerts: BudgetAlertRepository) -> None:
        self._alerts = alerts

    async def execute(self, user_id: int, alert_id: int) -> BudgetAlert:
        alerta = await self._alerts.get_for_user(user_id, alert_id)
        if alerta is None:
            # 404 aunque exista y sea de otro: un 403 confirmaría el id.
            raise ResourceNotFoundError("La alerta no existe.")

        alerta.marcar_leida()
        actualizada = await self._alerts.update(alerta)
        logger.info("Alerta marcada como leída", extra={"user_id": user_id, "alert_id": alert_id})
        return actualizada
