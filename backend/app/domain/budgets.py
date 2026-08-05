"""Reglas de negocio de los presupuestos."""

from __future__ import annotations

from decimal import Decimal

from app.domain.enums import BudgetStatus
from app.domain.value_objects import Money

# A partir de qué porcentaje del tope se avisa. Debajo, todo bien; por encima
# del 100 se considera excedido.
UMBRAL_DE_ALERTA_PORCENTUAL = Decimal("80")
_CIEN = Decimal("100")


def evaluar_estado(gastado: Money, tope: Money) -> BudgetStatus:
    """Clasifica el avance de un presupuesto.

    El estado se decide comparando montos, **no el porcentaje redondeado**.
    Con 100.004% del tope, el porcentaje que se muestra es "100.00" y decidir
    sobre ese número diría que todavía no se excedió, cuando sí. Se prefiere
    que el estado sea correcto aunque no coincida con el redondeo visible.
    """
    if gastado > tope:
        return BudgetStatus.EXCEEDED
    # `gastado / tope >= 0.80` sin dividir: la división de Decimal introduce
    # redondeo y en el borde exacto del 80% decidiría mal.
    if gastado.amount * _CIEN >= tope.amount * UMBRAL_DE_ALERTA_PORCENTUAL:
        return BudgetStatus.WARNING
    return BudgetStatus.OK


def porcentaje_gastado(gastado: Money, tope: Money) -> Decimal:
    """Porcentaje del tope consumido, con dos decimales. Puede pasar de 100."""
    if tope.is_zero:
        # No debería ocurrir —la entidad exige tope positivo—, pero devolver 0
        # es preferible a propagar una división por cero hasta la respuesta.
        return Decimal("0.00")
    return (gastado.amount / tope.amount * _CIEN).quantize(Decimal("0.01"))


def restante(gastado: Money, tope: Money) -> Money:
    """Lo que queda del tope. Negativo si se excedió, no cero."""
    return tope - gastado
