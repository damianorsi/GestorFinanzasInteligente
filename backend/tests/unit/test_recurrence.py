"""Tests de la aritmética de calendario de las reglas recurrentes.

Son funciones puras: no hace falta `freezegun` ni base. La ventana se les pasa
resuelta, así que lo único que se prueba acá es el calendario.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.domain.entities import RecurringRule
from app.domain.enums import RecurrenceFrequency, TransactionType
from app.domain.recurrence import (
    MAXIMO_DE_FECHAS_PROYECTADAS,
    fechas_de_la_regla,
    fechas_proyectadas_hasta,
    proximas_fechas,
)
from app.domain.value_objects import Money

MONEDA = "ARS"


def _regla(
    frecuencia: RecurrenceFrequency,
    starts_on: date,
    *,
    day_of_month: int | None = None,
    day_of_week: int | None = None,
    ends_on: date | None = None,
    is_active: bool = True,
) -> RecurringRule:
    return RecurringRule(
        user_id=1,
        category_id=1,
        type=TransactionType.EXPENSE,
        money=Money(Decimal("1000.00"), MONEDA),
        frequency=frecuencia,
        starts_on=starts_on,
        day_of_month=day_of_month,
        day_of_week=day_of_week,
        ends_on=ends_on,
        is_active=is_active,
    )


class TestMensual:
    def test_genera_el_mismo_dia_de_cada_mes(self) -> None:
        # Arrange
        regla = _regla(RecurrenceFrequency.MONTHLY, date(2026, 1, 10), day_of_month=10)

        # Act
        fechas = fechas_de_la_regla(regla, date(2026, 1, 1), date(2026, 4, 30))

        # Assert
        assert fechas == [
            date(2026, 1, 10),
            date(2026, 2, 10),
            date(2026, 3, 10),
            date(2026, 4, 10),
        ]

    def test_el_dia_31_en_febrero_cae_el_28(self) -> None:
        # Arrange: 2026 no es bisiesto.
        regla = _regla(RecurrenceFrequency.MONTHLY, date(2026, 1, 31), day_of_month=31)

        # Act
        fechas = fechas_de_la_regla(regla, date(2026, 1, 1), date(2026, 4, 30))

        # Assert: se ajusta al último día del mes, nunca se saltea el mes.
        assert fechas == [
            date(2026, 1, 31),
            date(2026, 2, 28),
            date(2026, 3, 31),
            date(2026, 4, 30),
        ]

    def test_el_dia_31_en_febrero_bisiesto_cae_el_29(self) -> None:
        # Arrange
        regla = _regla(RecurrenceFrequency.MONTHLY, date(2028, 1, 31), day_of_month=31)

        # Act
        fechas = fechas_de_la_regla(regla, date(2028, 2, 1), date(2028, 2, 29))

        # Assert
        assert fechas == [date(2028, 2, 29)]

    def test_no_genera_antes_de_starts_on(self) -> None:
        # Arrange
        regla = _regla(RecurrenceFrequency.MONTHLY, date(2026, 3, 5), day_of_month=5)

        # Act
        fechas = fechas_de_la_regla(regla, date(2026, 1, 1), date(2026, 4, 30))

        # Assert
        assert fechas == [date(2026, 3, 5), date(2026, 4, 5)]

    def test_ends_on_es_inclusive(self) -> None:
        # Arrange
        regla = _regla(
            RecurrenceFrequency.MONTHLY,
            date(2026, 1, 10),
            day_of_month=10,
            ends_on=date(2026, 3, 10),
        )

        # Act
        fechas = fechas_de_la_regla(regla, date(2026, 1, 1), date(2026, 12, 31))

        # Assert
        assert fechas[-1] == date(2026, 3, 10)

    def test_una_regla_ya_vencida_no_genera_nada(self) -> None:
        # Arrange
        regla = _regla(
            RecurrenceFrequency.MONTHLY,
            date(2025, 1, 10),
            day_of_month=10,
            ends_on=date(2025, 6, 10),
        )

        # Act
        fechas = fechas_de_la_regla(regla, date(2026, 1, 1), date(2026, 12, 31))

        # Assert
        assert fechas == []

    def test_cruza_el_cambio_de_anio(self) -> None:
        # Arrange
        regla = _regla(RecurrenceFrequency.MONTHLY, date(2026, 11, 15), day_of_month=15)

        # Act
        fechas = fechas_de_la_regla(regla, date(2026, 11, 1), date(2027, 2, 28))

        # Assert
        assert fechas == [
            date(2026, 11, 15),
            date(2026, 12, 15),
            date(2027, 1, 15),
            date(2027, 2, 15),
        ]


class TestSemanal:
    def test_genera_cada_siete_dias_en_el_dia_pedido(self) -> None:
        # Arrange: 2 = miércoles, y el 1/1/2026 cae jueves.
        regla = _regla(RecurrenceFrequency.WEEKLY, date(2026, 1, 1), day_of_week=2)

        # Act
        fechas = fechas_de_la_regla(regla, date(2026, 1, 1), date(2026, 1, 31))

        # Assert
        assert fechas == [date(2026, 1, 7), date(2026, 1, 14), date(2026, 1, 21), date(2026, 1, 28)]
        assert all(fecha.weekday() == 2 for fecha in fechas)

    def test_arranca_el_mismo_dia_si_starts_on_ya_es_el_dia_pedido(self) -> None:
        # Arrange: el 1/1/2026 es jueves (weekday 3).
        regla = _regla(RecurrenceFrequency.WEEKLY, date(2026, 1, 1), day_of_week=3)

        # Act
        fechas = fechas_de_la_regla(regla, date(2026, 1, 1), date(2026, 1, 15))

        # Assert
        assert fechas[0] == date(2026, 1, 1)


class TestDiaria:
    def test_genera_todos_los_dias_del_rango(self) -> None:
        # Arrange
        regla = _regla(RecurrenceFrequency.DAILY, date(2026, 8, 1))

        # Act
        fechas = fechas_de_la_regla(regla, date(2026, 8, 1), date(2026, 8, 5))

        # Assert
        assert len(fechas) == 5
        assert fechas[0] == date(2026, 8, 1)
        assert fechas[-1] == date(2026, 8, 5)

    def test_una_ventana_de_un_solo_dia_devuelve_ese_dia(self) -> None:
        # Arrange
        regla = _regla(RecurrenceFrequency.DAILY, date(2026, 8, 1))

        # Act
        fechas = fechas_de_la_regla(regla, date(2026, 8, 3), date(2026, 8, 3))

        # Assert
        assert fechas == [date(2026, 8, 3)]


class TestAnual:
    def test_repite_el_mes_y_el_dia_de_starts_on(self) -> None:
        # Arrange
        regla = _regla(RecurrenceFrequency.YEARLY, date(2026, 7, 9))

        # Act
        fechas = fechas_de_la_regla(regla, date(2026, 1, 1), date(2029, 12, 31))

        # Assert
        assert fechas == [date(2026, 7, 9), date(2027, 7, 9), date(2028, 7, 9), date(2029, 7, 9)]

    def test_un_29_de_febrero_cae_el_28_en_los_anios_no_bisiestos(self) -> None:
        # Arrange
        regla = _regla(RecurrenceFrequency.YEARLY, date(2028, 2, 29))

        # Act
        fechas = fechas_de_la_regla(regla, date(2028, 1, 1), date(2030, 12, 31))

        # Assert
        assert fechas == [date(2028, 2, 29), date(2029, 2, 28), date(2030, 2, 28)]


class TestVentana:
    def test_una_ventana_invertida_no_devuelve_nada(self) -> None:
        # Arrange
        regla = _regla(RecurrenceFrequency.DAILY, date(2026, 1, 1))

        # Act
        fechas = fechas_de_la_regla(regla, date(2026, 8, 10), date(2026, 8, 1))

        # Assert
        assert fechas == []


class TestProximasFechas:
    @pytest.mark.parametrize(
        ("frecuencia", "argumentos", "esperadas"),
        [
            (
                RecurrenceFrequency.MONTHLY,
                {"day_of_month": 10},
                [date(2026, 8, 10), date(2026, 9, 10), date(2026, 10, 10)],
            ),
            (
                RecurrenceFrequency.WEEKLY,
                {"day_of_week": 0},
                [date(2026, 8, 10), date(2026, 8, 17), date(2026, 8, 24)],
            ),
            (
                RecurrenceFrequency.DAILY,
                {},
                [date(2026, 8, 5), date(2026, 8, 6), date(2026, 8, 7)],
            ),
            (
                RecurrenceFrequency.YEARLY,
                {},
                [date(2026, 8, 5), date(2027, 8, 5), date(2028, 8, 5)],
            ),
        ],
    )
    def test_devuelve_exactamente_las_pedidas(
        self,
        frecuencia: RecurrenceFrequency,
        argumentos: dict[str, int],
        esperadas: list[date],
    ) -> None:
        # Arrange
        regla = _regla(frecuencia, date(2026, 8, 5), **argumentos)  # type: ignore[arg-type]

        # Act
        fechas = proximas_fechas(regla, date(2026, 8, 5), 3)

        # Assert: el preview del formulario muestra tres, así que tienen que
        # salir tres para cualquier frecuencia.
        assert fechas == esperadas

    def test_una_regla_pausada_no_proyecta(self) -> None:
        # Arrange
        regla = _regla(
            RecurrenceFrequency.MONTHLY, date(2026, 1, 10), day_of_month=10, is_active=False
        )

        # Act
        fechas = proximas_fechas(regla, date(2026, 8, 1), 3)

        # Assert
        assert fechas == []

    def test_devuelve_menos_si_la_regla_termina_antes(self) -> None:
        # Arrange
        regla = _regla(
            RecurrenceFrequency.MONTHLY,
            date(2026, 1, 10),
            day_of_month=10,
            ends_on=date(2026, 9, 30),
        )

        # Act
        fechas = proximas_fechas(regla, date(2026, 8, 1), 3)

        # Assert
        assert fechas == [date(2026, 8, 10), date(2026, 9, 10)]

    def test_pedir_cero_no_devuelve_nada(self) -> None:
        # Arrange
        regla = _regla(RecurrenceFrequency.MONTHLY, date(2026, 1, 10), day_of_month=10)

        # Act / Assert
        assert proximas_fechas(regla, date(2026, 8, 1), 0) == []


class TestProyeccion:
    def test_una_regla_pausada_no_tiene_vencimientos(self) -> None:
        # Arrange
        regla = _regla(RecurrenceFrequency.DAILY, date(2026, 1, 1), is_active=False)

        # Act
        fechas = fechas_proyectadas_hasta(regla, date(2026, 8, 1), date(2026, 8, 31))

        # Assert
        assert fechas == []

    def test_acota_las_proyecciones_de_una_regla_diaria(self) -> None:
        # Arrange: cinco años de una regla diaria son casi dos mil fechas.
        regla = _regla(RecurrenceFrequency.DAILY, date(2026, 1, 1))

        # Act
        fechas = fechas_proyectadas_hasta(regla, date(2026, 1, 1), date(2031, 1, 1))

        # Assert: nadie va a leer esa lista y el request se encarece por nada.
        assert len(fechas) == MAXIMO_DE_FECHAS_PROYECTADAS
