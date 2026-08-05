"""Tests del parser del parámetro `sort`."""

from __future__ import annotations

import pytest

from app.api.v1.schemas.transactions import parsear_sort
from app.application.dtos import ORDEN_POR_DEFECTO, SortDirection, SortField
from app.core.errors import ValidationError


@pytest.mark.parametrize("crudo", [None, "", "   ", ","])
def test_sin_sort_usa_el_orden_por_defecto(crudo: str | None) -> None:
    # Arrange / Act / Assert
    assert parsear_sort(crudo) == ORDEN_POR_DEFECTO


def test_el_prefijo_menos_indica_descendente() -> None:
    # Arrange / Act
    criterios = parsear_sort("-occurred_on")

    # Assert
    assert criterios[0].field is SortField.OCCURRED_ON
    assert criterios[0].direction is SortDirection.DESC


def test_sin_prefijo_es_ascendente() -> None:
    # Arrange / Act
    criterios = parsear_sort("amount")

    # Assert
    assert criterios[0].direction is SortDirection.ASC


def test_acepta_varios_criterios_en_orden() -> None:
    # Arrange / Act
    criterios = parsear_sort("-occurred_on,amount")

    # Assert
    assert [(c.field, c.direction) for c in criterios] == [
        (SortField.OCCURRED_ON, SortDirection.DESC),
        (SortField.AMOUNT, SortDirection.ASC),
    ]


def test_tolera_espacios_y_el_prefijo_mas() -> None:
    # Arrange / Act
    criterios = parsear_sort("  +amount ,  -created_at ")

    # Assert
    assert [(c.field, c.direction) for c in criterios] == [
        (SortField.AMOUNT, SortDirection.ASC),
        (SortField.CREATED_AT, SortDirection.DESC),
    ]


@pytest.mark.parametrize(
    "crudo",
    [
        "password_hash",
        "users.email",
        "amount; DROP TABLE transactions",
        "1",
        "-",
    ],
)
def test_rechaza_campos_fuera_de_la_lista_blanca(crudo: str) -> None:
    """Aceptar un nombre de columna arbitrario sería inyección por la puerta de atrás."""
    # Arrange / Act / Assert
    with pytest.raises(ValidationError, match="No se puede ordenar"):
        parsear_sort(crudo)


def test_el_mensaje_de_error_enumera_los_campos_validos() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValidationError) as error:
        parsear_sort("inventado")
    assert "occurred_on" in error.value.message
    assert "amount" in error.value.message
