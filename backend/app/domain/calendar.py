"""Aritmética de calendario.

Funciones puras, sin dependencias externas. No preguntan qué día es hoy: eso
lo resuelve el puerto `Clock` y se les pasa como argumento (docs/PROMPT.md
§5.2). Acá solo se opera sobre fechas ya dadas.
"""

from __future__ import annotations

import calendar
from datetime import date

MESES_EN_UN_ANIO = 12


def primer_dia_del_mes(dia: date) -> date:
    return dia.replace(day=1)


def ultimo_dia_del_mes(dia: date) -> date:
    return dia.replace(day=calendar.monthrange(dia.year, dia.month)[1])


def sumar_meses(dia: date, meses: int) -> date:
    """Suma meses conservando el día, o ajustando al último si no existe.

    Sumarle un mes al 31 de enero da el 28 (o 29) de febrero, no un error.
    """
    total = dia.month - 1 + meses
    anio = dia.year + total // MESES_EN_UN_ANIO
    mes = total % MESES_EN_UN_ANIO + 1
    ultimo = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, min(dia.day, ultimo))


def meses_entre(desde: date, hasta: date) -> list[date]:
    """Todos los primeros de mes entre dos fechas, inclusive.

    Se usa para rellenar los meses sin movimientos en la serie de tendencia:
    un GROUP BY solo devuelve los meses que tienen filas, y el gráfico
    quedaría con agujeros donde debería haber ceros.
    """
    actual = primer_dia_del_mes(desde)
    fin = primer_dia_del_mes(hasta)
    periodos: list[date] = []
    while actual <= fin:
        periodos.append(actual)
        actual = sumar_meses(actual, 1)
    return periodos


def etiqueta_de_periodo(dia: date) -> str:
    """`2026-08`, que es como viaja el período en la API."""
    return f"{dia.year:04d}-{dia.month:02d}"
