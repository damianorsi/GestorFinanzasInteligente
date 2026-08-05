"""Tests de los casos de uso de presupuestos."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.application.dtos import CategoryTotal
from app.application.exceptions import (
    DuplicateResourceError,
    InvalidReferenceError,
    ResourceNotFoundError,
    UnsupportedCurrencyError,
)
from app.application.use_cases.budgets import (
    CopyBudgets,
    CreateBudget,
    DeleteBudget,
    GetBudgetProgress,
    UpdateBudget,
)
from app.domain.entities import Budget, Category
from app.domain.enums import BudgetStatus, TransactionType
from app.domain.exceptions import InvalidBudgetError
from app.domain.value_objects import Money
from tests.fakes import FakeBudgetRepository, FakeCategoryRepository, FakeReportRepository

USUARIO = 1
OTRO_USUARIO = 2
MONEDAS = frozenset({"ARS"})
AGOSTO = date(2026, 8, 1)
JULIO = date(2026, 7, 1)


@pytest.fixture
def budgets() -> FakeBudgetRepository:
    return FakeBudgetRepository()


@pytest.fixture
def categorias() -> FakeCategoryRepository:
    return FakeCategoryRepository()


@pytest.fixture
def reports() -> FakeReportRepository:
    return FakeReportRepository()


async def _categoria(
    repo: FakeCategoryRepository,
    nombre: str = "Alimentación",
    tipo: TransactionType = TransactionType.EXPENSE,
    user_id: int = USUARIO,
) -> Category:
    return await repo.create(Category(user_id=user_id, name=nombre, type=tipo))


class TestCreateBudget:
    @pytest.fixture
    def caso(
        self, budgets: FakeBudgetRepository, categorias: FakeCategoryRepository
    ) -> CreateBudget:
        return CreateBudget(budgets, categorias, MONEDAS, "ARS")

    async def test_crea_el_presupuesto(
        self, caso: CreateBudget, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        categoria = await _categoria(categorias)

        # Act
        creado = await caso.execute(USUARIO, categoria.id or 0, AGOSTO, Decimal("200000.00"))

        # Assert
        assert creado.id is not None
        assert creado.limit == Money.of("200000.00", "ARS")

    async def test_rechaza_una_categoria_de_ingreso(
        self, caso: CreateBudget, categorias: FakeCategoryRepository
    ) -> None:
        """Un presupuesto es un tope de gasto: "gastar de menos" en el sueldo no es un desvío."""
        # Arrange
        sueldo = await _categoria(categorias, "Sueldo", TransactionType.INCOME)

        # Act / Assert
        with pytest.raises(InvalidReferenceError, match="topes de gasto"):
            await caso.execute(USUARIO, sueldo.id or 0, AGOSTO, Decimal("1000"))

    async def test_rechaza_una_categoria_ajena(
        self, caso: CreateBudget, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        ajena = await _categoria(categorias, user_id=OTRO_USUARIO)

        # Act / Assert
        with pytest.raises(InvalidReferenceError, match="no existe o no es tuya"):
            await caso.execute(USUARIO, ajena.id or 0, AGOSTO, Decimal("1000"))

    async def test_rechaza_un_duplicado_del_mismo_mes(
        self, caso: CreateBudget, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        categoria = await _categoria(categorias)
        await caso.execute(USUARIO, categoria.id or 0, AGOSTO, Decimal("1000"))

        # Act / Assert
        with pytest.raises(DuplicateResourceError):
            await caso.execute(USUARIO, categoria.id or 0, AGOSTO, Decimal("2000"))

    async def test_permite_la_misma_categoria_en_otro_mes(
        self, caso: CreateBudget, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        categoria = await _categoria(categorias)
        await caso.execute(USUARIO, categoria.id or 0, JULIO, Decimal("1000"))

        # Act
        creado = await caso.execute(USUARIO, categoria.id or 0, AGOSTO, Decimal("2000"))

        # Assert
        assert creado.period_month == AGOSTO

    async def test_rechaza_un_tope_no_positivo(
        self, caso: CreateBudget, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        categoria = await _categoria(categorias)

        # Act / Assert
        with pytest.raises(InvalidBudgetError, match="mayor a cero"):
            await caso.execute(USUARIO, categoria.id or 0, AGOSTO, Decimal("0"))

    async def test_rechaza_una_moneda_no_habilitada(
        self, caso: CreateBudget, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        categoria = await _categoria(categorias)

        # Act / Assert
        with pytest.raises(UnsupportedCurrencyError):
            await caso.execute(USUARIO, categoria.id or 0, AGOSTO, Decimal("1000"), currency="USD")


class TestUpdateYDelete:
    @pytest.fixture
    def existente(self, budgets: FakeBudgetRepository) -> Budget:
        presupuesto = Budget(
            user_id=USUARIO,
            category_id=1,
            period_month=AGOSTO,
            limit=Money.of("1000", "ARS"),
        )
        presupuesto.id = 1
        budgets.presupuestos[1] = presupuesto
        return presupuesto

    async def test_edita_el_tope(
        self,
        budgets: FakeBudgetRepository,
        categorias: FakeCategoryRepository,
        existente: Budget,
    ) -> None:
        # Arrange
        caso = UpdateBudget(budgets, categorias, MONEDAS, "ARS")

        # Act
        actualizado = await caso.execute(USUARIO, 1, Decimal("2500.50"))

        # Assert
        assert actualizado.limit == Money.of("2500.50", "ARS")

    async def test_editar_uno_ajeno_es_un_404(
        self,
        budgets: FakeBudgetRepository,
        categorias: FakeCategoryRepository,
        existente: Budget,
    ) -> None:
        # Arrange
        caso = UpdateBudget(budgets, categorias, MONEDAS, "ARS")

        # Act / Assert
        with pytest.raises(ResourceNotFoundError):
            await caso.execute(OTRO_USUARIO, 1, Decimal("1"))

    async def test_borrar_uno_ajeno_es_un_404(
        self,
        budgets: FakeBudgetRepository,
        categorias: FakeCategoryRepository,
        existente: Budget,
    ) -> None:
        # Arrange
        caso = DeleteBudget(budgets, categorias, MONEDAS, "ARS")

        # Act / Assert
        with pytest.raises(ResourceNotFoundError):
            await caso.execute(OTRO_USUARIO, 1)
        assert await budgets.get_for_user(USUARIO, 1) is not None


class TestCopyBudgets:
    @pytest.fixture
    def caso(
        self, budgets: FakeBudgetRepository, categorias: FakeCategoryRepository
    ) -> CopyBudgets:
        return CopyBudgets(budgets, categorias, MONEDAS, "ARS")

    async def _sembrar(
        self,
        budgets: FakeBudgetRepository,
        categorias: FakeCategoryRepository,
        nombre: str,
        periodo: date,
        monto: str,
    ) -> Category:
        categoria = next(
            (c for c in categorias.categorias if c.name == nombre),
            None,
        ) or await _categoria(categorias, nombre)
        await budgets.create(
            Budget(
                user_id=USUARIO,
                category_id=categoria.id or 0,
                period_month=periodo,
                limit=Money.of(monto, "ARS"),
            )
        )
        return categoria

    async def test_copia_los_presupuestos_al_mes_destino(
        self,
        caso: CopyBudgets,
        budgets: FakeBudgetRepository,
        categorias: FakeCategoryRepository,
    ) -> None:
        # Arrange
        await self._sembrar(budgets, categorias, "Alimentación", JULIO, "100000")
        await self._sembrar(budgets, categorias, "Ocio", JULIO, "50000")

        # Act
        resultado = await caso.execute(USUARIO, JULIO, AGOSTO)

        # Assert
        assert resultado.created == 2
        assert resultado.skipped == []
        assert len(await budgets.list_for_period(USUARIO, AGOSTO, "ARS")) == 2

    async def test_no_pisa_los_que_ya_existen_en_el_destino(
        self,
        caso: CopyBudgets,
        budgets: FakeBudgetRepository,
        categorias: FakeCategoryRepository,
    ) -> None:
        """Sobrescribir destruiría un tope ya ajustado a mano para ese mes."""
        # Arrange
        alimentacion = await self._sembrar(budgets, categorias, "Alimentación", JULIO, "100000")
        await self._sembrar(budgets, categorias, "Ocio", JULIO, "50000")
        await self._sembrar(budgets, categorias, "Alimentación", AGOSTO, "999999")

        # Act
        resultado = await caso.execute(USUARIO, JULIO, AGOSTO)

        # Assert
        assert resultado.created == 1
        assert [s.category_id for s in resultado.skipped] == [alimentacion.id]
        de_agosto = await budgets.list_for_period(USUARIO, AGOSTO, "ARS")
        conservado = next(b for b in de_agosto if b.category_id == alimentacion.id)
        assert conservado.limit == Money.of("999999", "ARS")

    async def test_el_salteado_informa_el_nombre_de_la_categoria(
        self,
        caso: CopyBudgets,
        budgets: FakeBudgetRepository,
        categorias: FakeCategoryRepository,
    ) -> None:
        # Arrange
        await self._sembrar(budgets, categorias, "Alimentación", JULIO, "100000")
        await self._sembrar(budgets, categorias, "Alimentación", AGOSTO, "1")

        # Act
        resultado = await caso.execute(USUARIO, JULIO, AGOSTO)

        # Assert
        assert resultado.skipped[0].category_name == "Alimentación"

    async def test_copiar_desde_un_mes_vacio_no_crea_nada(self, caso: CopyBudgets) -> None:
        # Arrange / Act
        resultado = await caso.execute(USUARIO, JULIO, AGOSTO)

        # Assert
        assert resultado.created == 0
        assert resultado.skipped == []

    async def test_rechaza_copiar_un_mes_sobre_si_mismo(self, caso: CopyBudgets) -> None:
        # Arrange / Act / Assert
        with pytest.raises(InvalidReferenceError, match="el mismo"):
            await caso.execute(USUARIO, AGOSTO, AGOSTO)


class TestGetBudgetProgress:
    @pytest.fixture
    def caso(
        self,
        budgets: FakeBudgetRepository,
        categorias: FakeCategoryRepository,
        reports: FakeReportRepository,
    ) -> GetBudgetProgress:
        return GetBudgetProgress(budgets, categorias, reports, MONEDAS, "ARS")

    async def test_cruza_el_tope_con_lo_gastado(
        self,
        caso: GetBudgetProgress,
        budgets: FakeBudgetRepository,
        categorias: FakeCategoryRepository,
        reports: FakeReportRepository,
    ) -> None:
        # Arrange
        categoria = await _categoria(categorias)
        await budgets.create(
            Budget(
                user_id=USUARIO,
                category_id=categoria.id or 0,
                period_month=AGOSTO,
                limit=Money.of("1000", "ARS"),
            )
        )
        reports.por_categoria = [
            CategoryTotal(
                categoria.id or 0,
                "Alimentación",
                TransactionType.EXPENSE,
                Money.of("850", "ARS"),
                4,
            )
        ]

        # Act
        reporte = await caso.execute(USUARIO, AGOSTO)

        # Assert
        entrada = reporte.entries[0]
        assert entrada.spent == Money.of("850", "ARS")
        assert entrada.remaining == Money.of("150", "ARS")
        assert entrada.status is BudgetStatus.WARNING

    async def test_un_presupuesto_sin_gasto_da_cero(
        self,
        caso: GetBudgetProgress,
        budgets: FakeBudgetRepository,
        categorias: FakeCategoryRepository,
    ) -> None:
        """Sin movimientos no aparece en el agregado; igual tiene que listarse."""
        # Arrange
        categoria = await _categoria(categorias)
        await budgets.create(
            Budget(
                user_id=USUARIO,
                category_id=categoria.id or 0,
                period_month=AGOSTO,
                limit=Money.of("1000", "ARS"),
            )
        )

        # Act
        reporte = await caso.execute(USUARIO, AGOSTO)

        # Assert
        assert len(reporte.entries) == 1
        assert reporte.entries[0].spent.is_zero
        assert reporte.entries[0].status is BudgetStatus.OK

    async def test_el_gasto_sin_presupuesto_va_aparte(
        self,
        caso: GetBudgetProgress,
        categorias: FakeCategoryRepository,
        reports: FakeReportRepository,
    ) -> None:
        """Si no se listara, el mes parecería controlado con el grueso del gasto sin tope."""
        # Arrange
        ocio = await _categoria(categorias, "Ocio")
        reports.por_categoria = [
            CategoryTotal(ocio.id or 0, "Ocio", TransactionType.EXPENSE, Money.of("5000", "ARS"), 2)
        ]

        # Act
        reporte = await caso.execute(USUARIO, AGOSTO)

        # Assert
        assert reporte.entries == []
        assert len(reporte.unbudgeted) == 1
        assert reporte.unbudgeted[0].spent == Money.of("5000", "ARS")

    async def test_ordena_lo_mas_comprometido_primero(
        self,
        caso: GetBudgetProgress,
        budgets: FakeBudgetRepository,
        categorias: FakeCategoryRepository,
        reports: FakeReportRepository,
    ) -> None:
        # Arrange
        holgada = await _categoria(categorias, "Holgada")
        apretada = await _categoria(categorias, "Apretada")
        for categoria in (holgada, apretada):
            await budgets.create(
                Budget(
                    user_id=USUARIO,
                    category_id=categoria.id or 0,
                    period_month=AGOSTO,
                    limit=Money.of("1000", "ARS"),
                )
            )
        reports.por_categoria = [
            CategoryTotal(
                holgada.id or 0, "Holgada", TransactionType.EXPENSE, Money.of("100", "ARS"), 1
            ),
            CategoryTotal(
                apretada.id or 0, "Apretada", TransactionType.EXPENSE, Money.of("1200", "ARS"), 1
            ),
        ]

        # Act
        reporte = await caso.execute(USUARIO, AGOSTO)

        # Assert
        assert [e.category_name for e in reporte.entries] == ["Apretada", "Holgada"]
        assert reporte.excedidos == 1

    async def test_un_mes_sin_presupuestos_ni_gastos_no_es_un_error(
        self, caso: GetBudgetProgress
    ) -> None:
        # Arrange / Act
        reporte = await caso.execute(USUARIO, AGOSTO)

        # Assert
        assert reporte.entries == []
        assert reporte.unbudgeted == []
        assert reporte.excedidos == 0

    async def test_consulta_el_mes_completo(
        self, caso: GetBudgetProgress, reports: FakeReportRepository
    ) -> None:
        """El gasto del mes va del día 1 al último, no del 1 al 1."""
        # Arrange / Act
        await caso.execute(USUARIO, AGOSTO)

        # Assert
        assert reports.periodos_pedidos == [(date(2026, 8, 1), date(2026, 8, 31))]
