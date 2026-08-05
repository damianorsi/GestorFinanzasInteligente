"""Repositorio de reglas recurrentes sobre SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import RecurringRule
from app.infrastructure.db.mappers import regla_a_dominio
from app.infrastructure.db.models import RecurringRuleModel


class SqlAlchemyRecurringRuleRepository:
    """Implementación del puerto `RecurringRuleRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active_for_user(self, user_id: int, currency: str) -> list[RecurringRule]:
        modelos = (
            await self._session.scalars(
                select(RecurringRuleModel)
                .where(
                    RecurringRuleModel.user_id == user_id,
                    RecurringRuleModel.currency == currency,
                    RecurringRuleModel.is_active.is_(True),
                )
                .order_by(RecurringRuleModel.day_of_month, RecurringRuleModel.id)
            )
        ).all()
        return [regla_a_dominio(modelo) for modelo in modelos]
