"""Tests del mapeo entre entidades de dominio y modelos ORM.

Son de ida y vuelta: dominio -> modelo -> dominio tiene que devolver lo mismo.
Un campo que alguien agregue a una entidad y olvide en el mapper se pierde en
silencio al guardar, y eso no lo detecta ningún test de endpoint.
"""

from __future__ import annotations

from datetime import date

from app.domain.entities import (
    Budget,
    Category,
    RecurringOccurrence,
    RecurringRule,
    Transaction,
    User,
)
from app.domain.enums import OccurrenceStatus, RecurrenceFrequency, TransactionType
from app.domain.value_objects import Money
from app.infrastructure.db.mappers import (
    categoria_a_dominio,
    categoria_a_modelo,
    movimiento_a_dominio,
    movimiento_a_modelo,
    ocurrencia_a_dominio,
    ocurrencia_a_modelo,
    presupuesto_a_dominio,
    presupuesto_a_modelo,
    regla_a_dominio,
    regla_a_modelo,
    usuario_a_dominio,
    usuario_a_modelo,
)


def test_usuario_ida_y_vuelta() -> None:
    # Arrange
    original = User(email="damian@ejemplo.com", full_name="Damián Orsi", is_active=False)

    # Act
    recuperado = usuario_a_dominio(usuario_a_modelo(original, password_hash="hash"))

    # Assert
    assert recuperado == original


def test_el_hash_de_contrasena_no_es_parte_del_dominio() -> None:
    """Es un detalle de autenticación, no una regla de negocio."""
    # Arrange
    original = User(email="damian@ejemplo.com", full_name="Damián Orsi")

    # Act
    modelo = usuario_a_modelo(original, password_hash="hash-secreto")

    # Assert
    assert modelo.password_hash == "hash-secreto"
    assert not hasattr(original, "password_hash")


def test_categoria_ida_y_vuelta() -> None:
    # Arrange
    original = Category(
        user_id=7,
        name="Alimentación",
        type=TransactionType.EXPENSE,
        color="#1c9e6f",
        is_default=True,
    )

    # Act
    recuperada = categoria_a_dominio(categoria_a_modelo(original))

    # Assert
    assert recuperada == original


def test_movimiento_ida_y_vuelta_conserva_monto_y_moneda() -> None:
    # Arrange
    original = Transaction(
        user_id=7,
        category_id=3,
        type=TransactionType.EXPENSE,
        money=Money.of("1234.56", "ARS"),
        occurred_on=date(2026, 8, 4),
        description="Supermercado",
        recurring_rule_id=11,
    )

    # Act
    recuperado = movimiento_a_dominio(movimiento_a_modelo(original))

    # Assert
    assert recuperado == original
    assert recuperado.money == Money.of("1234.56", "ARS")
    assert recuperado.currency == "ARS"


def test_el_modelo_guarda_monto_y_moneda_por_separado() -> None:
    """El VO se descompone en dos columnas, pero vuelve a armarse entero."""
    # Arrange
    original = Transaction(
        user_id=1,
        category_id=1,
        type=TransactionType.INCOME,
        money=Money.of("850000.00", "ARS"),
        occurred_on=date(2026, 8, 1),
    )

    # Act
    modelo = movimiento_a_modelo(original)

    # Assert
    assert modelo.amount == Money.of("850000.00", "ARS").amount
    assert modelo.currency == "ARS"


def test_presupuesto_ida_y_vuelta() -> None:
    # Arrange
    original = Budget(
        user_id=7,
        category_id=3,
        period_month=date(2026, 8, 1),
        limit=Money.of("200000.00", "ARS"),
    )

    # Act
    recuperado = presupuesto_a_dominio(presupuesto_a_modelo(original))

    # Assert
    assert recuperado == original


def test_regla_recurrente_ida_y_vuelta() -> None:
    # Arrange
    original = RecurringRule(
        user_id=7,
        category_id=3,
        type=TransactionType.EXPENSE,
        money=Money.of("450000.00", "ARS"),
        frequency=RecurrenceFrequency.MONTHLY,
        starts_on=date(2026, 1, 1),
        description="Alquiler",
        day_of_month=5,
        ends_on=date(2026, 12, 31),
        is_active=False,
    )

    # Act
    recuperada = regla_a_dominio(regla_a_modelo(original))

    # Assert
    assert recuperada == original


def test_ocurrencia_ida_y_vuelta() -> None:
    # Arrange
    original = RecurringOccurrence(
        rule_id=11,
        occurred_on=date(2026, 8, 5),
        status=OccurrenceStatus.SKIPPED,
        transaction_id=None,
    )

    # Act
    recuperada = ocurrencia_a_dominio(ocurrencia_a_modelo(original))

    # Assert
    assert recuperada == original
