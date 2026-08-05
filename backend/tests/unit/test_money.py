"""Tests del value object `Money`."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.exceptions import CurrencyMismatchError, InvalidMoneyError
from app.domain.value_objects import Money


# --- Construcción ----------------------------------------------------------
@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("1234.56", Decimal("1234.56")),
        ("0.01", Decimal("0.01")),
        (1500, Decimal("1500.00")),
        (Decimal("99.9"), Decimal("99.90")),
        ("-250.75", Decimal("-250.75")),
    ],
)
def test_se_construye_desde_str_int_y_decimal(
    entrada: str | int | Decimal, esperado: Decimal
) -> None:
    # Arrange / Act
    monto = Money.of(entrada, "ARS")

    # Assert
    assert monto.amount == esperado


def test_rechaza_float() -> None:
    """El flotante binario no representa 0.1 exacto: en dinero eso corrompe."""
    # Arrange / Act / Assert
    with pytest.raises(InvalidMoneyError, match="nunca se construye desde float"):
        Money.of(1234.56, "ARS")


def test_rechaza_mas_de_dos_decimales() -> None:
    # Arrange / Act / Assert
    with pytest.raises(InvalidMoneyError, match="más de 2 decimales"):
        Money.of("10.005", "ARS")


@pytest.mark.parametrize("valor", ["NaN", "Infinity", "-Infinity"])
def test_rechaza_valores_no_finitos(valor: str) -> None:
    # Arrange / Act / Assert
    with pytest.raises(InvalidMoneyError, match="finito"):
        Money.of(valor, "ARS")


def test_rechaza_texto_que_no_es_numero() -> None:
    # Arrange / Act / Assert
    with pytest.raises(InvalidMoneyError):
        Money.of("mil pesos", "ARS")


@pytest.mark.parametrize("codigo", ["AR", "ARSS", "AR1", "", "$$$"])
def test_rechaza_codigos_de_moneda_invalidos(codigo: str) -> None:
    # Arrange / Act / Assert
    with pytest.raises(InvalidMoneyError, match="Código de moneda inválido"):
        Money.of("100", codigo)


def test_normaliza_la_moneda_a_mayusculas() -> None:
    # Arrange / Act
    monto = Money.of("100", "ars")

    # Assert
    assert monto.currency == "ARS"


def test_normaliza_a_dos_decimales() -> None:
    # Arrange / Act
    monto = Money.of("10", "ARS")

    # Assert
    assert str(monto) == "10.00 ARS"


def test_es_inmutable() -> None:
    # Arrange
    monto = Money.of("100", "ARS")

    # Act / Assert
    with pytest.raises(AttributeError):
        monto.amount = Decimal("999")  # type: ignore[misc]


# --- Aritmética ------------------------------------------------------------
def test_suma_montos_de_la_misma_moneda() -> None:
    # Arrange
    a, b = Money.of("100.50", "ARS"), Money.of("49.50", "ARS")

    # Act
    total = a + b

    # Assert
    assert total == Money.of("150.00", "ARS")


def test_la_suma_es_exacta_donde_el_float_falla() -> None:
    """0.1 + 0.2 == 0.3. Con float daría 0.30000000000000004."""
    # Arrange
    a, b = Money.of("0.10", "ARS"), Money.of("0.20", "ARS")

    # Act
    total = a + b

    # Assert
    assert total == Money.of("0.30", "ARS")


def test_resta_puede_dar_negativo() -> None:
    """Un balance es una resta: si se gastó más de lo que entró, da negativo."""
    # Arrange
    ingresos, gastos = Money.of("1000", "ARS"), Money.of("1500", "ARS")

    # Act
    balance = ingresos - gastos

    # Assert
    assert balance == Money.of("-500.00", "ARS")
    assert balance.is_negative


def test_niega_y_toma_valor_absoluto() -> None:
    # Arrange
    monto = Money.of("-300", "ARS")

    # Act / Assert
    assert -monto == Money.of("300", "ARS")
    assert abs(monto) == Money.of("300", "ARS")


# --- Mezcla de monedas -----------------------------------------------------
@pytest.mark.parametrize(
    "operacion",
    [
        lambda a, b: a + b,
        lambda a, b: a - b,
        lambda a, b: a < b,
        lambda a, b: a <= b,
        lambda a, b: a > b,
        lambda a, b: a >= b,
    ],
)
def test_operar_entre_monedas_distintas_falla(operacion) -> None:  # type: ignore[no-untyped-def]
    """La guarda que hace segura la futura habilitación de USD.

    Si algún día se mezclan ARS y USD por error, esto revienta en un test en
    vez de producir un balance silenciosamente incorrecto.
    """
    # Arrange
    pesos, dolares = Money.of("100", "ARS"), Money.of("100", "USD")

    # Act / Assert
    with pytest.raises(CurrencyMismatchError):
        operacion(pesos, dolares)


def test_la_igualdad_entre_monedas_distintas_es_falsa_no_error() -> None:
    """Comparar por igualdad es una pregunta legítima; ordenar no lo es."""
    # Arrange
    pesos, dolares = Money.of("100", "ARS"), Money.of("100", "USD")

    # Act / Assert
    assert pesos != dolares


# --- Comparación -----------------------------------------------------------
def test_ordena_montos_de_la_misma_moneda() -> None:
    # Arrange
    chico, grande = Money.of("100", "ARS"), Money.of("200", "ARS")

    # Act / Assert
    assert chico < grande
    assert grande > chico
    assert chico <= Money.of("100", "ARS")
    assert grande >= Money.of("200", "ARS")


# --- Agregación ------------------------------------------------------------
def test_suma_una_coleccion() -> None:
    # Arrange
    montos = [Money.of("10", "ARS"), Money.of("20.50", "ARS"), Money.of("0.50", "ARS")]

    # Act
    total = Money.sum(montos, "ARS")

    # Assert
    assert total == Money.of("31.00", "ARS")


def test_la_suma_de_una_coleccion_vacia_es_cero_en_la_moneda_pedida() -> None:
    """Por esto la moneda es un parámetro y no se infiere del primer elemento."""
    # Arrange / Act
    total = Money.sum([], "ARS")

    # Assert
    assert total == Money.zero("ARS")
    assert total.currency == "ARS"


def test_sumar_una_coleccion_con_monedas_mezcladas_falla() -> None:
    # Arrange
    montos = [Money.of("10", "ARS"), Money.of("20", "USD")]

    # Act / Assert
    with pytest.raises(CurrencyMismatchError):
        Money.sum(montos, "ARS")


# --- Consultas -------------------------------------------------------------
def test_reconoce_positivo_negativo_y_cero() -> None:
    # Arrange
    positivo, negativo, cero = (
        Money.of("1", "ARS"),
        Money.of("-1", "ARS"),
        Money.zero("ARS"),
    )

    # Act / Assert
    assert positivo.is_positive and not positivo.is_negative and not positivo.is_zero
    assert negativo.is_negative and not negativo.is_positive
    assert cero.is_zero and not cero.is_positive and not cero.is_negative
