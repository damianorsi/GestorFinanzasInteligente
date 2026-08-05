"""Tests de los casos de uso de movimientos.

Cubren las reglas de negocio: validación de moneda, coherencia entre la
categoría y el tipo, y el salteo de ocurrencias al borrar. Los filtros, el
orden y la paginación se prueban contra MySQL en los tests de integración,
porque son responsabilidad del repositorio.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.application.exceptions import (
    InvalidReferenceError,
    ResourceNotFoundError,
    UnsupportedCurrencyError,
)
from app.application.use_cases.transactions import (
    CreateTransaction,
    DeleteTransaction,
    GetTransaction,
    UpdateTransaction,
)
from app.domain.entities import Category, Transaction
from app.domain.enums import TransactionType
from app.domain.exceptions import InvalidTransactionError
from app.domain.value_objects import Money
from tests.fakes import (
    FakeCategoryRepository,
    FakeRecurringOccurrenceRepository,
    FakeTransactionRepository,
)

USUARIO = 1
OTRO_USUARIO = 2
MONEDAS = frozenset({"ARS"})
UN_DIA = date(2026, 8, 5)


@pytest.fixture
def categorias() -> FakeCategoryRepository:
    return FakeCategoryRepository()


@pytest.fixture
def movimientos() -> FakeTransactionRepository:
    return FakeTransactionRepository()


@pytest.fixture
def ocurrencias() -> FakeRecurringOccurrenceRepository:
    return FakeRecurringOccurrenceRepository()


async def _categoria(
    repo: FakeCategoryRepository,
    user_id: int = USUARIO,
    tipo: TransactionType = TransactionType.EXPENSE,
    nombre: str = "Alimentación",
) -> Category:
    return await repo.create(Category(user_id=user_id, name=nombre, type=tipo))


class TestCreateTransaction:
    @pytest.fixture
    def caso(
        self, movimientos: FakeTransactionRepository, categorias: FakeCategoryRepository
    ) -> CreateTransaction:
        return CreateTransaction(movimientos, categorias, MONEDAS, "ARS")

    async def test_crea_el_movimiento(
        self, caso: CreateTransaction, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        categoria = await _categoria(categorias)

        # Act
        creado = await caso.execute(
            user_id=USUARIO,
            type=TransactionType.EXPENSE,
            amount=Decimal("1234.56"),
            occurred_on=UN_DIA,
            category_id=categoria.id or 0,
            description="Supermercado",
        )

        # Assert
        assert creado.id is not None
        assert creado.money == Money.of("1234.56", "ARS")

    async def test_usa_la_moneda_por_defecto_si_no_se_indica(
        self, caso: CreateTransaction, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        categoria = await _categoria(categorias)

        # Act
        creado = await caso.execute(
            user_id=USUARIO,
            type=TransactionType.EXPENSE,
            amount=Decimal("100"),
            occurred_on=UN_DIA,
            category_id=categoria.id or 0,
        )

        # Assert
        assert creado.money.currency == "ARS"

    async def test_rechaza_una_moneda_no_habilitada(
        self, caso: CreateTransaction, categorias: FakeCategoryRepository
    ) -> None:
        """USD no está habilitado en v1 aunque el esquema lo soporte."""
        # Arrange
        categoria = await _categoria(categorias)

        # Act / Assert
        with pytest.raises(UnsupportedCurrencyError, match="USD"):
            await caso.execute(
                user_id=USUARIO,
                type=TransactionType.EXPENSE,
                amount=Decimal("100"),
                occurred_on=UN_DIA,
                category_id=categoria.id or 0,
                currency="USD",
            )

    async def test_rechaza_una_categoria_ajena(
        self, caso: CreateTransaction, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        ajena = await _categoria(categorias, user_id=OTRO_USUARIO)

        # Act / Assert
        with pytest.raises(InvalidReferenceError, match="no existe o no es tuya"):
            await caso.execute(
                user_id=USUARIO,
                type=TransactionType.EXPENSE,
                amount=Decimal("100"),
                occurred_on=UN_DIA,
                category_id=ajena.id or 0,
            )

    async def test_rechaza_una_categoria_del_tipo_equivocado(
        self, caso: CreateTransaction, categorias: FakeCategoryRepository
    ) -> None:
        """Un gasto en una categoría de ingreso rompería todos los agregados."""
        # Arrange
        de_ingreso = await _categoria(categorias, tipo=TransactionType.INCOME, nombre="Sueldo")

        # Act / Assert
        with pytest.raises(InvalidReferenceError, match="ingreso"):
            await caso.execute(
                user_id=USUARIO,
                type=TransactionType.EXPENSE,
                amount=Decimal("100"),
                occurred_on=UN_DIA,
                category_id=de_ingreso.id or 0,
            )

    @pytest.mark.parametrize("monto", ["0", "-50"])
    async def test_rechaza_montos_no_positivos(
        self, caso: CreateTransaction, categorias: FakeCategoryRepository, monto: str
    ) -> None:
        # Arrange
        categoria = await _categoria(categorias)

        # Act / Assert
        with pytest.raises(InvalidTransactionError, match="mayor a cero"):
            await caso.execute(
                user_id=USUARIO,
                type=TransactionType.EXPENSE,
                amount=Decimal(monto),
                occurred_on=UN_DIA,
                category_id=categoria.id or 0,
            )


class TestUpdateTransaction:
    @pytest.fixture
    def caso(
        self, movimientos: FakeTransactionRepository, categorias: FakeCategoryRepository
    ) -> UpdateTransaction:
        return UpdateTransaction(movimientos, categorias, MONEDAS, "ARS")

    @pytest.fixture
    async def existente(
        self, movimientos: FakeTransactionRepository, categorias: FakeCategoryRepository
    ) -> Transaction:
        categoria = await _categoria(categorias)
        return await movimientos.create(
            Transaction(
                user_id=USUARIO,
                category_id=categoria.id or 0,
                type=TransactionType.EXPENSE,
                money=Money.of("100", "ARS"),
                occurred_on=UN_DIA,
            )
        )

    async def test_cambia_el_monto_conservando_la_moneda(
        self, caso: UpdateTransaction, existente: Transaction
    ) -> None:
        # Arrange / Act
        actualizado = await caso.execute(USUARIO, existente.id or 0, amount=Decimal("250.75"))

        # Assert
        assert actualizado.money == Money.of("250.75", "ARS")

    async def test_cambiar_el_tipo_revalida_la_categoria(
        self, caso: UpdateTransaction, existente: Transaction
    ) -> None:
        """La categoría que servía para un gasto no sirve para un ingreso."""
        # Arrange / Act / Assert
        with pytest.raises(InvalidReferenceError):
            await caso.execute(USUARIO, existente.id or 0, type=TransactionType.INCOME)

    async def test_rechaza_un_monto_no_positivo(
        self, caso: UpdateTransaction, existente: Transaction
    ) -> None:
        # Arrange / Act / Assert
        with pytest.raises(InvalidTransactionError):
            await caso.execute(USUARIO, existente.id or 0, amount=Decimal("0"))

    async def test_no_se_puede_editar_uno_ajeno(
        self, caso: UpdateTransaction, existente: Transaction
    ) -> None:
        # Arrange / Act / Assert
        with pytest.raises(ResourceNotFoundError):
            await caso.execute(OTRO_USUARIO, existente.id or 0, amount=Decimal("999"))


class TestDeleteTransaction:
    @pytest.fixture
    def caso(
        self,
        movimientos: FakeTransactionRepository,
        ocurrencias: FakeRecurringOccurrenceRepository,
    ) -> DeleteTransaction:
        return DeleteTransaction(movimientos, ocurrencias)

    async def test_borra_un_movimiento_suelto(
        self, caso: DeleteTransaction, movimientos: FakeTransactionRepository
    ) -> None:
        # Arrange
        creado = await movimientos.create(
            Transaction(
                user_id=USUARIO,
                category_id=1,
                type=TransactionType.EXPENSE,
                money=Money.of("100", "ARS"),
                occurred_on=UN_DIA,
            )
        )

        # Act
        await caso.execute(USUARIO, creado.id or 0)

        # Assert
        assert await movimientos.get_for_user(USUARIO, creado.id or 0) is None

    async def test_no_toca_las_ocurrencias_si_no_era_recurrente(
        self,
        caso: DeleteTransaction,
        movimientos: FakeTransactionRepository,
        ocurrencias: FakeRecurringOccurrenceRepository,
    ) -> None:
        # Arrange
        creado = await movimientos.create(
            Transaction(
                user_id=USUARIO,
                category_id=1,
                type=TransactionType.EXPENSE,
                money=Money.of("100", "ARS"),
                occurred_on=UN_DIA,
            )
        )

        # Act
        await caso.execute(USUARIO, creado.id or 0)

        # Assert
        assert ocurrencias.salteadas == []

    async def test_saltea_la_ocurrencia_si_lo_genero_una_regla(
        self,
        caso: DeleteTransaction,
        movimientos: FakeTransactionRepository,
        ocurrencias: FakeRecurringOccurrenceRepository,
    ) -> None:
        """Sin esto, el job lo vuelve a crear al día siguiente."""
        # Arrange
        creado = await movimientos.create(
            Transaction(
                user_id=USUARIO,
                category_id=1,
                type=TransactionType.EXPENSE,
                money=Money.of("100", "ARS"),
                occurred_on=UN_DIA,
                recurring_rule_id=7,
            )
        )

        # Act
        await caso.execute(USUARIO, creado.id or 0)

        # Assert
        assert ocurrencias.salteadas == [creado.id]

    async def test_no_se_puede_borrar_uno_ajeno(
        self, caso: DeleteTransaction, movimientos: FakeTransactionRepository
    ) -> None:
        # Arrange
        creado = await movimientos.create(
            Transaction(
                user_id=USUARIO,
                category_id=1,
                type=TransactionType.EXPENSE,
                money=Money.of("100", "ARS"),
                occurred_on=UN_DIA,
            )
        )

        # Act / Assert
        with pytest.raises(ResourceNotFoundError):
            await caso.execute(OTRO_USUARIO, creado.id or 0)
        assert await movimientos.get_for_user(USUARIO, creado.id or 0) is not None


class TestGetTransaction:
    async def test_un_movimiento_ajeno_es_un_404(
        self, movimientos: FakeTransactionRepository
    ) -> None:
        # Arrange
        creado = await movimientos.create(
            Transaction(
                user_id=OTRO_USUARIO,
                category_id=1,
                type=TransactionType.EXPENSE,
                money=Money.of("100", "ARS"),
                occurred_on=UN_DIA,
            )
        )
        caso = GetTransaction(movimientos)

        # Act / Assert
        with pytest.raises(ResourceNotFoundError):
            await caso.execute(USUARIO, creado.id or 0)
