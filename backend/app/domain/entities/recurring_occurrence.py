"""Entidad `RecurringOccurrence`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.domain.enums import OccurrenceStatus


@dataclass(slots=True)
class RecurringOccurrence:
    """Registro de que una regla ya fue resuelta para una fecha dada.

    Es el libro mayor que hace idempotente al job de recurrentes. La garantía
    dura no está acá sino en la base: `UNIQUE (rule_id, occurred_on)`.

    `GENERATED` con `transaction_id` en null es un estado válido y esperado:
    ocurre cuando el movimiento generado se borra por el camino del `ON DELETE
    SET NULL`. Lo que nunca hay que hacer es borrar la fila de la ocurrencia,
    porque entonces el job la volvería a crear.
    """

    rule_id: int
    occurred_on: date
    status: OccurrenceStatus
    transaction_id: int | None = None
    id: int | None = None

    @property
    def fue_salteada(self) -> bool:
        return self.status is OccurrenceStatus.SKIPPED

    def saltear(self) -> None:
        """Marca la ocurrencia como salteada y suelta el movimiento borrado."""
        self.status = OccurrenceStatus.SKIPPED
        self.transaction_id = None
