"""Proyección de fechas de una regla recurrente.

Funciones puras. No preguntan qué día es hoy ni tocan la base: reciben la
ventana ya resuelta y devuelven las fechas que caen adentro. Esa separación es
lo que permite testear la aritmética de calendario sin `freezegun` y sin MySQL,
y es también lo que hace que el job y la proyección de vencimientos futuros
compartan exactamente el mismo cálculo (docs/PROMPT.md §9).
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from app.domain.calendar import MESES_EN_UN_ANIO, sumar_meses
from app.domain.entities import RecurringRule
from app.domain.enums import RecurrenceFrequency

DIAS_EN_UNA_SEMANA = 7

# Tope de seguridad para las proyecciones a futuro. Una regla diaria proyectada
# a diez años son miles de fechas: nadie las va a leer y el request se vuelve
# caro por nada.
MAXIMO_DE_FECHAS_PROYECTADAS = 366


def _ajustar_al_mes(anio: int, mes: int, dia_pedido: int) -> date:
    """Devuelve el día del mes, o el último si ese mes no lo tiene.

    Una regla mensual del 31 en febrero cae el 28 (o 29). Nunca se saltea el
    mes: quien configuró "todos los 31" quiere que se genere todos los meses,
    no ocho veces al año.
    """
    ultimo = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, min(dia_pedido, ultimo))


def _fechas_diarias(desde: date, hasta: date) -> list[date]:
    dias = (hasta - desde).days + 1
    return [desde + timedelta(days=numero) for numero in range(dias)]


def _fechas_semanales(inicio: date, dia_de_la_semana: int, hasta: date) -> list[date]:
    # Se avanza desde `inicio` hasta el primer día de la semana pedido. Arrancar
    # desde ahí y sumar de a siete evita tener que evaluar día por día.
    desplazamiento = (dia_de_la_semana - inicio.weekday()) % DIAS_EN_UNA_SEMANA
    actual = inicio + timedelta(days=desplazamiento)
    fechas: list[date] = []
    while actual <= hasta:
        fechas.append(actual)
        actual += timedelta(days=DIAS_EN_UNA_SEMANA)
    return fechas


def _fechas_mensuales(inicio: date, dia_del_mes: int, hasta: date) -> list[date]:
    anio, mes = inicio.year, inicio.month
    fechas: list[date] = []
    while True:
        candidata = _ajustar_al_mes(anio, mes, dia_del_mes)
        if candidata > hasta:
            break
        if candidata >= inicio:
            fechas.append(candidata)
        mes += 1
        if mes > MESES_EN_UN_ANIO:
            anio, mes = anio + 1, 1
    return fechas


def _fechas_anuales(inicio: date, referencia: date, hasta: date) -> list[date]:
    # YEARLY no lleva parámetros: repite el mes y el día de `starts_on`. Un 29
    # de febrero cae el 28 en los años no bisiestos, por la misma razón que el
    # día 31 en los meses cortos.
    fechas: list[date] = []
    anio = inicio.year
    while True:
        candidata = _ajustar_al_mes(anio, referencia.month, referencia.day)
        if candidata > hasta:
            break
        if candidata >= inicio:
            fechas.append(candidata)
        anio += 1
    return fechas


def fechas_de_la_regla(regla: RecurringRule, desde: date, hasta: date) -> list[date]:
    """Fechas en las que la regla toca, dentro de `[desde, hasta]` inclusive.

    No sabe nada de qué se generó ya ni de qué día es hoy: acotar la ventana
    para no materializar el futuro es responsabilidad de quien la llama.
    """
    inicio = max(desde, regla.starts_on)
    fin = hasta if regla.ends_on is None else min(hasta, regla.ends_on)
    if inicio > fin:
        return []

    match regla.frequency:
        case RecurrenceFrequency.DAILY:
            return _fechas_diarias(inicio, fin)
        case RecurrenceFrequency.WEEKLY:
            # `day_of_week` es obligatorio para WEEKLY: la entidad lo valida al
            # construirse, así que acá no puede ser None.
            return _fechas_semanales(inicio, regla.day_of_week or 0, fin)
        case RecurrenceFrequency.MONTHLY:
            return _fechas_mensuales(inicio, regla.day_of_month or 1, fin)
        case RecurrenceFrequency.YEARLY:
            return _fechas_anuales(inicio, regla.starts_on, fin)


def _horizonte(desde: date, frecuencia: RecurrenceFrequency, cantidad: int) -> date:
    """Hasta dónde hay que mirar para juntar `cantidad` fechas.

    Se calcula de una y no ampliando en un bucle: para cada frecuencia se sabe
    exactamente cuánta ventana hace falta, y una vuelta de más sería una
    consulta de calendario que ya se podía evitar.
    """
    match frecuencia:
        case RecurrenceFrequency.DAILY:
            return desde + timedelta(days=cantidad)
        case RecurrenceFrequency.WEEKLY:
            return desde + timedelta(weeks=cantidad)
        case RecurrenceFrequency.MONTHLY:
            return sumar_meses(desde, cantidad + 1)
        case RecurrenceFrequency.YEARLY:
            return sumar_meses(desde, MESES_EN_UN_ANIO * (cantidad + 1))


def proximas_fechas(regla: RecurringRule, desde: date, cantidad: int) -> list[date]:
    """Las próximas `cantidad` fechas de la regla a partir de `desde`.

    Alimenta el preview del formulario: ver las tres fechas que la regla va a
    generar es el feedback inmediato de que quedó bien configurada.
    """
    if cantidad <= 0 or not regla.is_active:
        return []
    return fechas_de_la_regla(regla, desde, _horizonte(desde, regla.frequency, cantidad))[:cantidad]


def fechas_proyectadas_hasta(regla: RecurringRule, desde: date, hasta: date) -> list[date]:
    """Vencimientos futuros de la regla, acotados por seguridad.

    Es lo que alimenta `GET /recurring-rules/upcoming`. **Estas fechas son una
    proyección**: no existen como movimientos y no participan de ningún reporte
    ni del balance (docs/PROMPT.md §9).
    """
    if not regla.is_active:
        return []
    return fechas_de_la_regla(regla, desde, hasta)[:MAXIMO_DE_FECHAS_PROYECTADAS]
