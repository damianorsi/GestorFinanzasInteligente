"""Detección de desvíos presupuestarios.

Funciones puras. No preguntan qué día es hoy ni tocan la base: reciben la fecha
resuelta y deciden. Lo que las hace *proactivas* es la proyección
(docs/PROMPT.md §21.2).
"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from app.domain.enums import AlertType
from app.domain.value_objects import Money

_CIEN = Decimal("100")

# Días del mes que tienen que haber pasado antes de proyectar. Con dos días
# transcurridos, una sola compra grande proyecta un desvío de quince veces el
# tope: la proyección todavía no dice nada sobre el mes y avisar sería ruido
# que enseña a ignorar las alertas.
DIAS_MINIMOS_PARA_PROYECTAR = 5

# Cuánto tiene que superar el tope la proyección para avisar. Terminar 3% por
# encima entra dentro del error del propio método; avisarlo sería alarmismo.
MARGEN_DE_PROYECCION_PORCENTUAL = Decimal("110")


def dias_del_mes(dia: date) -> int:
    return calendar.monthrange(dia.year, dia.month)[1]


def proyectar_gasto_del_mes(gastado: Money, dia: date) -> Money:
    """Extrapola el gasto del mes completo a partir del ritmo actual.

    Regla de tres simple sobre los días transcurridos: si en 10 de 31 días se
    gastaron $60.000, el mes termina en $186.000. **No es un modelo
    predictivo** y la interfaz no lo presenta como tal; es el ritmo actual
    llevado a fin de mes.
    """
    transcurridos = dia.day
    total = dias_del_mes(dia)
    if transcurridos <= 0:
        return gastado
    return Money(
        (gastado.amount * total / transcurridos).quantize(Decimal("0.01")),
        gastado.currency,
    )


def porcentaje_proyectado(gastado: Money, tope: Money, dia: date) -> Decimal:
    """Qué porcentaje del tope proyecta consumir el mes, con dos decimales."""
    if tope.is_zero:
        return Decimal("0.00")
    proyectado = proyectar_gasto_del_mes(gastado, dia)
    return (proyectado.amount / tope.amount * _CIEN).quantize(Decimal("0.01"))


def detectar_desvio(gastado: Money, tope: Money, dia: date) -> AlertType | None:
    """Decide si un presupuesto amerita una alerta, y de qué tipo.

    El orden importa: si ya se pasó, avisa que se pasó y no que va camino a
    pasarse. Son excluyentes, y emitir las dos sería decir dos veces lo mismo
    con distinta urgencia.
    """
    if gastado > tope:
        return AlertType.BUDGET_EXCEEDED

    if dia.day < DIAS_MINIMOS_PARA_PROYECTAR:
        return None

    # Se compara sin dividir, igual que `evaluar_estado`: la división de
    # Decimal redondea y en el borde exacto decidiría mal.
    proyectado = proyectar_gasto_del_mes(gastado, dia)
    if proyectado.amount * _CIEN >= tope.amount * MARGEN_DE_PROYECCION_PORCENTUAL:
        return AlertType.BUDGET_AT_RISK

    return None
