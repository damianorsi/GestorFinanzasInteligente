"""Proyección de metas de ahorro.

Funciones puras: reciben el ritmo ya calculado y la fecha resuelta, y deciden.
No preguntan qué día es hoy ni tocan la base.

**Esto no es un modelo predictivo.** Es el balance mensual promedio de los
últimos meses aplicado a lo que falta, y la interfaz lo dice explícitamente
(docs/PROMPT.md §21.3). Vender una regresión simple como predicción de IA es
exactamente lo que la especificación pide no hacer.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import ROUND_CEILING, Decimal

from app.domain.calendar import primer_dia_del_mes, sumar_meses
from app.domain.enums import GoalStatus
from app.domain.value_objects import Money

# Meses de historial que hacen falta para proyectar. Con uno solo, el "ritmo"
# es un único dato: un mes con aguinaldo diría que la meta se alcanza en la
# mitad de tiempo, y un mes con vacaciones que no se alcanza nunca.
MESES_MINIMOS_DE_HISTORIAL = 2

# Techo del horizonte que se informa. Más allá, el promedio de unos pocos
# meses no dice nada útil y un "faltan 340 meses" se lee como un error.
MESES_MAXIMOS_PROYECTADOS = 600


def ritmo_mensual(balances: Sequence[Money], currency: str) -> Money | None:
    """Promedio de los balances mensuales, o `None` si no alcanza el historial.

    Los meses negativos entran en el promedio: un mes en rojo es parte del
    ritmo real, y excluirlos daría una proyección optimista que la persona no
    pidió.
    """
    if len(balances) < MESES_MINIMOS_DE_HISTORIAL:
        return None
    total = Money.sum(balances, currency)
    return Money(
        (total.amount / Decimal(len(balances))).quantize(Decimal("0.01")),
        currency,
    )


def meses_para_alcanzar(faltante: Money, ritmo: Money) -> int | None:
    """Cuántos meses de ese ritmo cubren lo que falta.

    Devuelve `None` cuando el ritmo no lleva a ningún lado: con un promedio
    de cero o negativo no se alcanza nunca, y un número grande mentiría menos
    que un número chico pero mentiría igual.

    Se redondea hacia arriba: medio mes de ahorro no compra media meta.
    """
    if not faltante.is_positive:
        return 0
    if not ritmo.is_positive:
        return None
    meses = (faltante.amount / ritmo.amount).to_integral_value(rounding=ROUND_CEILING)
    if meses > MESES_MAXIMOS_PROYECTADOS:
        return None
    return int(meses)


def fecha_proyectada(hoy: date, meses: int) -> date:
    """El primer día del mes en que se alcanzaría la meta.

    Se devuelve el mes y no el día exacto porque el ritmo es mensual: dar un
    día preciso sugeriría una precisión que el cálculo no tiene.
    """
    return sumar_meses(primer_dia_del_mes(hoy), meses)


def evaluar_estado(
    ahorrado: Money,
    objetivo: Money,
    meses_necesarios: int | None,
    target_date: date | None,
    hoy: date,
) -> GoalStatus:
    """En qué anda la meta.

    `ACHIEVED` gana sobre todo lo demás: una meta alcanzada no se proyecta,
    aunque el ritmo del último tiempo haya sido malo.

    Sin `target_date` no hay tarde ni temprano, así que el estado es
    `ON_TRACK`, **salvo que al ritmo actual no se llegue nunca**: decir "vas
    bien" cuando el promedio es cero o negativo sería falso, haya o no una
    fecha límite.
    """
    if ahorrado >= objetivo:
        return GoalStatus.ACHIEVED
    if meses_necesarios is None:
        return GoalStatus.AT_RISK
    if target_date is None:
        return GoalStatus.ON_TRACK
    return (
        GoalStatus.AT_RISK
        if fecha_proyectada(hoy, meses_necesarios) > primer_dia_del_mes(target_date)
        else GoalStatus.ON_TRACK
    )


def porcentaje_alcanzado(ahorrado: Money, objetivo: Money) -> Decimal:
    """Cuánto de la meta está cubierto, con dos decimales.

    No se recorta a 100: haber juntado de más es información, y esconderla
    haría que dos metas muy distintas se vieran igual. Sí se recorta por
    abajo, porque un porcentaje negativo de una meta no significa nada.
    """
    if objetivo.is_zero:
        return Decimal("0.00")
    porcentaje = (ahorrado.amount / objetivo.amount * Decimal("100")).quantize(Decimal("0.01"))
    return max(porcentaje, Decimal("0.00"))
