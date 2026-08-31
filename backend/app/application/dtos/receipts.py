"""DTOs de la lectura de tickets (docs/PROMPT.md §21.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

# Debajo de esto, la interfaz marca el campo como dudoso en vez de mostrarlo
# como un dato firme. Esconder la duda es lo que hace que alguien confirme un
# monto equivocado.
UMBRAL_DE_CONFIANZA_BAJA = 0.7


@dataclass(frozen=True, slots=True)
class ExtractedReceipt:
    """Lo que el modelo dice haber leído del ticket.

    Todo es opcional a propósito: un ticket arrugado puede no tener monto
    legible, y es preferible devolver el resto que fallar entero. La confianza
    viaja por campo, no como un único número, porque leer bien el total y mal
    la fecha es el caso común.
    """

    amount: Decimal | None = None
    occurred_on: date | None = None
    merchant: str | None = None
    # Nombre tal como lo devolvió el modelo. La resolución contra las
    # categorías del usuario la hace el caso de uso, no el lector.
    category_name: str | None = None
    confidence: dict[str, float] = field(default_factory=dict)

    def confianza_de(self, campo: str) -> float:
        return self.confidence.get(campo, 0.0)


@dataclass(frozen=True, slots=True)
class ReceiptDraft:
    """Borrador que se le propone a la persona.

    **No es un movimiento.** Precarga el formulario y nada más: la creación
    sigue pasando por `POST /transactions`, con las mismas validaciones de
    siempre (docs/PROMPT.md §21.1).
    """

    scan_id: int
    amount: Decimal | None
    occurred_on: date
    merchant: str | None
    currency: str
    category_id: int | None
    category_name: str | None
    confidence: dict[str, float]
    # Ids de movimientos del mismo monto y fecha que ya existen. No bloquea
    # nada: pagar dos cafés iguales el mismo día es normal, pero escanear dos
    # veces el mismo ticket también.
    possible_duplicates: list[int] = field(default_factory=list)

    @property
    def campos_dudosos(self) -> list[str]:
        return sorted(
            campo for campo, valor in self.confidence.items() if valor < UMBRAL_DE_CONFIANZA_BAJA
        )
