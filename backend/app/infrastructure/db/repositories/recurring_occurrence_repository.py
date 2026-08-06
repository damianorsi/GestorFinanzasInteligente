"""Repositorio del libro mayor de ocurrencias recurrentes."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import RecurringOccurrence, Transaction
from app.domain.enums import OccurrenceStatus
from app.infrastructure.db.mappers import movimiento_a_modelo, ocurrencia_a_dominio
from app.infrastructure.db.models import RecurringOccurrenceModel

logger = logging.getLogger(__name__)


class SqlAlchemyRecurringOccurrenceRepository:
    """Implementación del puerto `RecurringOccurrenceRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def mark_skipped_by_transaction(self, transaction_id: int) -> None:
        # Se marca SKIPPED y NO se borra la fila: borrarla haría que el job
        # volviera a generar el movimiento en la corrida siguiente.
        # `transaction_id = NULL` se pone explícito acá y no se deja al ON
        # DELETE SET NULL de la FK, para no depender del orden en que la base
        # aplique las dos operaciones.
        await self._session.execute(
            update(RecurringOccurrenceModel)
            .where(RecurringOccurrenceModel.transaction_id == transaction_id)
            .values(status=OccurrenceStatus.SKIPPED, transaction_id=None)
        )

    async def resolved_dates(self, rule_id: int) -> set[date]:
        fechas = await self._session.scalars(
            # Sin filtrar por estado: una ocurrencia SKIPPED también está
            # resuelta, y omitirla haría reaparecer el movimiento que alguien
            # borró a propósito.
            select(RecurringOccurrenceModel.occurred_on).where(
                RecurringOccurrenceModel.rule_id == rule_id
            )
        )
        return set(fechas.all())

    async def list_for_rule(self, rule_id: int) -> list[RecurringOccurrence]:
        modelos = (
            await self._session.scalars(
                select(RecurringOccurrenceModel)
                .where(RecurringOccurrenceModel.rule_id == rule_id)
                .order_by(
                    RecurringOccurrenceModel.occurred_on.desc(),
                    RecurringOccurrenceModel.id.desc(),
                )
            )
        ).all()
        return [ocurrencia_a_dominio(modelo) for modelo in modelos]

    async def mark_skipped(self, rule_id: int, dates: Iterable[date]) -> int:
        pendientes = set(dates) - await self.resolved_dates(rule_id)
        if not pendientes:
            return 0

        self._session.add_all(
            RecurringOccurrenceModel(
                rule_id=rule_id,
                occurred_on=fecha,
                status=OccurrenceStatus.SKIPPED,
                transaction_id=None,
            )
            for fecha in sorted(pendientes)
        )
        await self._session.flush()
        return len(pendientes)

    async def register_generated(self, transaction: Transaction, occurred_on: date) -> bool:
        """Inserta el movimiento y su ocurrencia, o no inserta nada.

        Van dentro de un savepoint porque la UNIQUE `(rule_id, occurred_on)` es
        la que resuelve la carrera entre dos corridas: sin el savepoint, el
        `IntegrityError` dejaría la sesión abortada y se caería la generación
        de todas las reglas siguientes, además de dejar el movimiento huérfano.
        """
        try:
            async with self._session.begin_nested():
                modelo = movimiento_a_modelo(transaction)
                self._session.add(modelo)
                await self._session.flush()

                self._session.add(
                    RecurringOccurrenceModel(
                        rule_id=transaction.recurring_rule_id,
                        occurred_on=occurred_on,
                        status=OccurrenceStatus.GENERATED,
                        transaction_id=modelo.id,
                    )
                )
                await self._session.flush()
        except IntegrityError:
            # Otra corrida ya la registró. No es un error: es exactamente para
            # esto que existe la constraint.
            logger.info(
                "Ocurrencia ya registrada por otra corrida",
                extra={
                    "rule_id": transaction.recurring_rule_id,
                    "occurred_on": occurred_on.isoformat(),
                },
            )
            return False
        return True
