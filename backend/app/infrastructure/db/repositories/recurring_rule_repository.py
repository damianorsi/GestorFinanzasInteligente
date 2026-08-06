"""Repositorio de reglas recurrentes sobre SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import RecurringRule
from app.infrastructure.db.mappers import regla_a_dominio, regla_a_modelo
from app.infrastructure.db.models import RecurringRuleModel


class SqlAlchemyRecurringRuleRepository:
    """Implementación del puerto `RecurringRuleRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, rule: RecurringRule) -> RecurringRule:
        modelo = regla_a_modelo(rule)
        self._session.add(modelo)
        await self._session.flush()
        return regla_a_dominio(modelo)

    async def update(self, rule: RecurringRule) -> RecurringRule:
        modelo = await self._session.get(RecurringRuleModel, rule.id)
        if modelo is None:
            raise ValueError(f"La regla {rule.id} no existe.")

        modelo.category_id = rule.category_id
        modelo.type = rule.type
        modelo.amount = rule.money.amount
        modelo.currency = rule.money.currency
        modelo.description = rule.description
        modelo.frequency = rule.frequency
        modelo.day_of_month = rule.day_of_month
        modelo.day_of_week = rule.day_of_week
        modelo.starts_on = rule.starts_on
        modelo.ends_on = rule.ends_on
        modelo.is_active = rule.is_active
        await self._session.flush()
        return regla_a_dominio(modelo)

    async def delete(self, user_id: int, rule_id: int) -> None:
        # El `user_id` va en el WHERE aunque el caso de uso ya haya verificado
        # la pertenencia: es la última barrera y no cuesta nada.
        await self._session.execute(
            delete(RecurringRuleModel).where(
                RecurringRuleModel.id == rule_id,
                RecurringRuleModel.user_id == user_id,
            )
        )

    async def get_for_user(self, user_id: int, rule_id: int) -> RecurringRule | None:
        modelo = await self._session.scalar(
            select(RecurringRuleModel).where(
                RecurringRuleModel.id == rule_id,
                RecurringRuleModel.user_id == user_id,
            )
        )
        return None if modelo is None else regla_a_dominio(modelo)

    async def list_for_user(
        self, user_id: int, currency: str, is_active: bool | None = None
    ) -> list[RecurringRule]:
        consulta = select(RecurringRuleModel).where(
            RecurringRuleModel.user_id == user_id,
            RecurringRuleModel.currency == currency,
        )
        if is_active is not None:
            consulta = consulta.where(RecurringRuleModel.is_active.is_(is_active))

        modelos = (
            await self._session.scalars(
                # `id` como desempate: sin él, dos reglas del mismo día del mes
                # podrían salir en orden distinto entre llamadas.
                consulta.order_by(RecurringRuleModel.day_of_month, RecurringRuleModel.id)
            )
        ).all()
        return [regla_a_dominio(modelo) for modelo in modelos]

    async def list_active_for_user(self, user_id: int, currency: str) -> list[RecurringRule]:
        return await self.list_for_user(user_id, currency, is_active=True)

    async def list_all_active(self) -> list[RecurringRule]:
        """Sin `user_id`: la usa el job, que no atiende un request.

        Ver el puerto para por qué es la única consulta sin dueño de toda la
        aplicación.
        """
        modelos = (
            await self._session.scalars(
                select(RecurringRuleModel)
                .where(RecurringRuleModel.is_active.is_(True))
                .order_by(RecurringRuleModel.id)
            )
        ).all()
        return [regla_a_dominio(modelo) for modelo in modelos]

    async def deactivate(self, rule_id: int) -> None:
        await self._session.execute(
            update(RecurringRuleModel)
            .where(RecurringRuleModel.id == rule_id)
            .values(is_active=False)
        )
