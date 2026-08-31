"""Repositorio de alertas de presupuesto sobre SQLAlchemy."""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import BudgetAlert
from app.domain.enums import AlertStatus
from app.infrastructure.db.mappers import alerta_a_dominio, alerta_a_modelo
from app.infrastructure.db.models import BudgetAlertModel

logger = logging.getLogger(__name__)

_VIGENTES = (AlertStatus.OPEN, AlertStatus.READ)


class SqlAlchemyBudgetAlertRepository:
    """Implementación del puerto `BudgetAlertRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(
        self, user_id: int, status: AlertStatus | None = None
    ) -> list[BudgetAlert]:
        consulta = select(BudgetAlertModel).where(BudgetAlertModel.user_id == user_id)
        if status is not None:
            consulta = consulta.where(BudgetAlertModel.status == status)

        modelos = (
            await self._session.scalars(
                # `id` como desempate: dos alertas creadas en la misma corrida
                # comparten `created_at` al segundo y saldrían en orden
                # distinto entre llamadas.
                consulta.order_by(BudgetAlertModel.created_at.desc(), BudgetAlertModel.id.desc())
            )
        ).all()
        return [alerta_a_dominio(modelo) for modelo in modelos]

    async def get_for_user(self, user_id: int, alert_id: int) -> BudgetAlert | None:
        modelo = await self._session.scalar(
            select(BudgetAlertModel).where(
                BudgetAlertModel.id == alert_id,
                BudgetAlertModel.user_id == user_id,
            )
        )
        return None if modelo is None else alerta_a_dominio(modelo)

    async def update(self, alert: BudgetAlert) -> BudgetAlert:
        modelo = await self._session.get(BudgetAlertModel, alert.id)
        if modelo is None:
            raise ValueError(f"La alerta {alert.id} no existe.")

        modelo.status = alert.status
        modelo.message = alert.message
        modelo.recommendation = alert.recommendation
        modelo.projected_percentage = alert.projected_percentage
        await self._session.flush()
        return alerta_a_dominio(modelo)

    async def create_if_absent(self, alert: BudgetAlert) -> BudgetAlert | None:
        """Inserta dentro de un savepoint y deja que decida la UNIQUE.

        Se intenta insertar en vez de consultar primero: con dos corridas
        simultáneas, entre el `SELECT` y el `INSERT` hay una ventana en la que
        las dos creerían que no existe. La constraint no tiene esa ventana.
        """
        try:
            async with self._session.begin_nested():
                modelo = alerta_a_modelo(alert)
                self._session.add(modelo)
                await self._session.flush()
        except IntegrityError:
            return None
        return alerta_a_dominio(modelo)

    async def resolve_stale(self, user_id: int, period_month: date, vigentes: set[int]) -> int:
        consulta = (
            update(BudgetAlertModel)
            .where(
                BudgetAlertModel.user_id == user_id,
                BudgetAlertModel.period_month == period_month,
                BudgetAlertModel.status.in_(_VIGENTES),
            )
            .values(status=AlertStatus.RESOLVED)
        )
        if vigentes:
            consulta = consulta.where(BudgetAlertModel.id.notin_(vigentes))

        resultado = await self._session.execute(consulta)
        # `rowcount` existe en el resultado de un UPDATE pero no está en el tipo
        # genérico `Result`, así que hay que sacarlo por `getattr`.
        return int(getattr(resultado, "rowcount", 0) or 0)

    async def list_open_period_ids(self, user_id: int, period_month: date) -> set[int]:
        ids = await self._session.scalars(
            select(BudgetAlertModel.id).where(
                BudgetAlertModel.user_id == user_id,
                BudgetAlertModel.period_month == period_month,
                BudgetAlertModel.status.in_(_VIGENTES),
            )
        )
        return set(ids.all())
