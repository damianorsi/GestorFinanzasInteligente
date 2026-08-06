"""Puerto del libro mayor de ocurrencias recurrentes.

Es lo que hace idempotente al job: antes de generar se consulta qué fechas ya
fueron resueltas para la regla, y la UNIQUE `(rule_id, occurred_on)` es la red
de seguridad a nivel base.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Protocol

from app.domain.entities import RecurringOccurrence, Transaction


class RecurringOccurrenceRepository(Protocol):
    async def mark_skipped_by_transaction(self, transaction_id: int) -> None:
        """Marca como SKIPPED la ocurrencia de un movimiento que se borra.

        No borra la fila: si la borrara, el job volvería a generar el
        movimiento en la siguiente corrida. Es idempotente y no falla si el
        movimiento no vino de una regla.
        """
        ...

    async def resolved_dates(self, rule_id: int) -> set[date]:
        """Fechas de la regla ya resueltas, generadas **o salteadas**.

        Las salteadas entran a propósito: si solo se miraran las generadas, el
        movimiento que alguien borró a mano reaparecería en la corrida
        siguiente. Ese es el bug más probable de toda la feature.
        """
        ...

    async def list_for_rule(self, rule_id: int) -> list[RecurringOccurrence]:
        """Historial de la regla, de la fecha más reciente a la más vieja."""
        ...

    async def mark_skipped(self, rule_id: int, dates: Iterable[date]) -> int:
        """Anota fechas como salteadas, sin movimiento asociado.

        Es lo que se usa al reactivar una regla pausada: las fechas del período
        de pausa se dan por resueltas para que el job no las genere de golpe.
        Sin esto, reactivar una regla pausada tres meses inyectaría tres meses
        de movimientos que nunca ocurrieron (docs/PROMPT.md §9).

        Las que ya estén registradas se ignoran. Devuelve cuántas anotó.
        """
        ...

    async def register_generated(self, transaction: Transaction, occurred_on: date) -> bool:
        """Inserta el movimiento y su ocurrencia como una sola unidad atómica.

        Devuelve `False` si la ocurrencia ya existía —otra corrida ganó la
        carrera— sin haber creado el movimiento. Las dos escrituras van juntas
        acá y no en el caso de uso porque son un solo hecho: un movimiento
        generado sin su ocurrencia se volvería a generar mañana, y una
        ocurrencia sin movimiento dejaría un hueco silencioso.
        """
        ...
