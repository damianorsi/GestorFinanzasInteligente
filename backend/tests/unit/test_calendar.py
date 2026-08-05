"""Tests de la aritmética de calendario."""

from __future__ import annotations

from datetime import date

import pytest

from app.domain.calendar import (
    etiqueta_de_periodo,
    meses_entre,
    primer_dia_del_mes,
    sumar_meses,
    ultimo_dia_del_mes,
)


def test_primer_dia_del_mes() -> None:
    # Arrange / Act / Assert
    assert primer_dia_del_mes(date(2026, 8, 17)) == date(2026, 8, 1)


@pytest.mark.parametrize(
    ("dia", "esperado"),
    [
        (date(2026, 1, 5), date(2026, 1, 31)),
        (date(2026, 2, 5), date(2026, 2, 28)),
        (date(2028, 2, 5), date(2028, 2, 29)),  # bisiesto
        (date(2026, 4, 5), date(2026, 4, 30)),
    ],
)
def test_ultimo_dia_del_mes(dia: date, esperado: date) -> None:
    # Arrange / Act / Assert
    assert ultimo_dia_del_mes(dia) == esperado


def test_sumar_meses_avanza_de_anio() -> None:
    # Arrange / Act / Assert
    assert sumar_meses(date(2026, 11, 15), 3) == date(2027, 2, 15)


def test_restar_meses_retrocede_de_anio() -> None:
    # Arrange / Act / Assert
    assert sumar_meses(date(2026, 2, 15), -3) == date(2025, 11, 15)


def test_sumar_un_mes_al_31_ajusta_al_ultimo_dia() -> None:
    """El 31 de enero más un mes es el 28 de febrero, no un error."""
    # Arrange / Act / Assert
    assert sumar_meses(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert sumar_meses(date(2028, 1, 31), 1) == date(2028, 2, 29)


def test_sumar_cero_meses_no_cambia_nada() -> None:
    # Arrange / Act / Assert
    assert sumar_meses(date(2026, 8, 5), 0) == date(2026, 8, 5)


def test_meses_entre_incluye_los_dos_extremos() -> None:
    # Arrange / Act
    periodos = meses_entre(date(2026, 6, 15), date(2026, 9, 3))

    # Assert
    assert periodos == [
        date(2026, 6, 1),
        date(2026, 7, 1),
        date(2026, 8, 1),
        date(2026, 9, 1),
    ]


def test_meses_entre_dentro_del_mismo_mes_devuelve_uno() -> None:
    # Arrange / Act / Assert
    assert meses_entre(date(2026, 8, 3), date(2026, 8, 27)) == [date(2026, 8, 1)]


def test_meses_entre_cruza_el_cambio_de_anio() -> None:
    # Arrange / Act
    periodos = meses_entre(date(2025, 12, 1), date(2026, 2, 1))

    # Assert
    assert periodos == [date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1)]


def test_etiqueta_de_periodo_rellena_con_cero() -> None:
    # Arrange / Act / Assert
    assert etiqueta_de_periodo(date(2026, 8, 1)) == "2026-08"
    assert etiqueta_de_periodo(date(2026, 12, 1)) == "2026-12"
