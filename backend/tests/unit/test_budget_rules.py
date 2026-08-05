"""Tests de las reglas de negocio de los presupuestos.

Los bordes son lo importante: son el punto donde el color de la barra cambia y
donde una decisión de redondeo puede hacer que la aplicación diga "vas bien"
cuando en realidad se pasó.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.budgets import evaluar_estado, porcentaje_gastado, restante
from app.domain.enums import BudgetStatus
from app.domain.value_objects import Money

TOPE = Money.of("1000.00", "ARS")


def _pesos(monto: str) -> Money:
    return Money.of(monto, "ARS")


@pytest.mark.parametrize(
    ("gastado", "esperado"),
    [
        ("0.00", BudgetStatus.OK),
        ("500.00", BudgetStatus.OK),
        ("799.99", BudgetStatus.OK),
        # 80% exacto ya avisa: el umbral es inclusivo.
        ("800.00", BudgetStatus.WARNING),
        ("999.99", BudgetStatus.WARNING),
        # 100% exacto todavía NO está excedido: se excede al pasarlo.
        ("1000.00", BudgetStatus.WARNING),
        ("1000.01", BudgetStatus.EXCEEDED),
        ("2500.00", BudgetStatus.EXCEEDED),
    ],
)
def test_los_bordes_del_estado(gastado: str, esperado: BudgetStatus) -> None:
    # Arrange / Act / Assert
    assert evaluar_estado(_pesos(gastado), TOPE) is esperado


def test_el_estado_no_depende_del_porcentaje_redondeado() -> None:
    """El caso que justifica decidir por montos y no por el porcentaje.

    Con este tope, gastar un centavo de más da 100.004%, que redondeado a dos
    decimales se muestra como "100.00". Si el estado se decidiera sobre ese
    número, la aplicación diría que todavía no se excedió.
    """
    # Arrange
    tope = _pesos("250.00")
    gastado = _pesos("250.01")

    # Act
    porcentaje = porcentaje_gastado(gastado, tope)
    estado = evaluar_estado(gastado, tope)

    # Assert
    assert porcentaje == Decimal("100.00")
    assert estado is BudgetStatus.EXCEEDED


def test_el_umbral_del_80_no_se_corre_por_redondeo() -> None:
    """Un centavo por debajo del 80% todavía es OK."""
    # Arrange
    tope = _pesos("300.00")

    # Act / Assert
    assert evaluar_estado(_pesos("239.99"), tope) is BudgetStatus.OK
    assert evaluar_estado(_pesos("240.00"), tope) is BudgetStatus.WARNING


@pytest.mark.parametrize(
    ("gastado", "esperado"),
    [("0.00", "0.00"), ("250.00", "25.00"), ("1000.00", "100.00"), ("1500.00", "150.00")],
)
def test_el_porcentaje_puede_pasar_de_cien(gastado: str, esperado: str) -> None:
    # Arrange / Act / Assert
    assert porcentaje_gastado(_pesos(gastado), TOPE) == Decimal(esperado)


def test_el_restante_es_negativo_si_se_excedio() -> None:
    """Decir "0 restante" ocultaría cuánto se pasó."""
    # Arrange / Act
    sobrante = restante(_pesos("1250.00"), TOPE)

    # Assert
    assert sobrante == _pesos("-250.00")
    assert sobrante.is_negative


def test_el_restante_conserva_la_moneda() -> None:
    # Arrange / Act / Assert
    assert restante(_pesos("100.00"), TOPE).currency == "ARS"
