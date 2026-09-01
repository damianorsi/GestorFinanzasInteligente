"""Tests de los casos de uso de metas de ahorro (docs/PROMPT.md §21.3)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.application.dtos import MonthlyTotal, PeriodSummary
from app.application.exceptions import DuplicateResourceError, ResourceNotFoundError
from app.application.use_cases.savings import (
    CreateSavingsGoal,
    DeleteSavingsGoal,
    GetSavingsGoalsProgress,
    ListSavingsGoals,
    UpdateSavingsGoal,
)
from app.domain.entities import SavingsGoal
from app.domain.enums import GoalStatus
from app.domain.exceptions import InvalidSavingsGoalError
from app.domain.value_objects import Money
from tests.fakes import FakeReportRepository, FakeSavingsGoalRepository, FixedClock

MONEDAS = frozenset({"ARS"})
MONEDA = "ARS"
USUARIO = 1
# Mitad de mes: hay meses cerrados detrás y el mes en curso va por la mitad.
HOY = datetime(2026, 8, 15, 10, 0)
INICIO = date(2026, 3, 1)


def plata(monto: str) -> Money:
    return Money(Decimal(monto), MONEDA)


class _Escenario:
    def __init__(self) -> None:
        self.metas = FakeSavingsGoalRepository()
        self.reportes = FakeReportRepository()
        self.clock = FixedClock(HOY)
        self.avance = GetSavingsGoalsProgress(
            self.metas, self.reportes, self.clock, MONEDAS, MONEDA
        )
        self.crear = CreateSavingsGoal(self.metas, self.clock, MONEDAS, MONEDA)
        self.editar = UpdateSavingsGoal(self.metas, self.clock, MONEDAS, MONEDA)
        self.borrar = DeleteSavingsGoal(self.metas, self.clock, MONEDAS, MONEDA)
        self.listar = ListSavingsGoals(self.metas, self.clock, MONEDAS, MONEDA)

    def con_meta(
        self,
        objetivo: str = "2000000.00",
        starts_on: date = INICIO,
        target_date: date | None = None,
        nombre: str = "Viaje",
    ) -> SavingsGoal:
        return self.metas.agregar(
            SavingsGoal(
                user_id=USUARIO,
                name=nombre,
                target=plata(objetivo),
                starts_on=starts_on,
                target_date=target_date,
            )
        )

    def con_acumulado(self, balance: str) -> None:
        """Fija el balance entre el inicio de la meta y hoy."""
        self.reportes.resumen = PeriodSummary(
            currency=MONEDA,
            date_from=INICIO,
            date_to=HOY.date(),
            income=Money(Decimal(balance), MONEDA),
            expense=Money.zero(MONEDA),
        )

    def con_meses(self, *balances: str) -> None:
        """Carga meses cerrados con ese balance, desde marzo."""
        self.reportes.mensuales = [
            MonthlyTotal(
                period=date(2026, 3 + indice, 1),
                income=Money(Decimal(balance), MONEDA),
                expense=Money.zero(MONEDA),
            )
            for indice, balance in enumerate(balances)
        ]


@pytest.fixture
def escenario() -> _Escenario:
    return _Escenario()


class TestAvance:
    async def test_mide_el_acumulado_contra_el_objetivo(self, escenario: _Escenario) -> None:
        # Arrange
        escenario.con_meta(objetivo="2000000.00")
        escenario.con_acumulado("500000.00")
        escenario.con_meses("100000.00", "100000.00")

        # Act
        avances = await escenario.avance.execute(USUARIO)

        # Assert
        assert avances[0].saved == plata("500000.00")
        assert avances[0].remaining == plata("1500000.00")
        assert avances[0].percentage == Decimal("25.00")

    async def test_el_acumulado_sale_desde_el_inicio_de_la_meta(
        self, escenario: _Escenario
    ) -> None:
        # Arrange
        escenario.con_meta(starts_on=date(2026, 5, 20))
        escenario.con_meses("100000.00", "100000.00")

        # Act
        await escenario.avance.execute(USUARIO)

        # Assert: la fecha de inicio define qué movimientos cuentan.
        assert escenario.reportes.periodos_pedidos[0] == (date(2026, 5, 20), HOY.date())

    async def test_proyecta_sobre_los_meses_cerrados(self, escenario: _Escenario) -> None:
        # Arrange: faltan 1.500.000 y el ritmo es 300.000 por mes.
        escenario.con_meta(objetivo="2000000.00")
        escenario.con_acumulado("500000.00")
        escenario.con_meses("300000.00", "300000.00", "300000.00")

        # Act
        avance = (await escenario.avance.execute(USUARIO))[0]

        # Assert
        assert avance.projection is not None
        assert avance.projection.monthly_rate == plata("300000.00")
        assert avance.projection.months_to_target == 5
        assert avance.projection.projected_date == date(2027, 1, 1)

    async def test_el_mes_en_curso_no_entra_en_el_ritmo(self, escenario: _Escenario) -> None:
        # Arrange
        escenario.con_meta()
        escenario.con_meses("300000.00", "300000.00")

        # Act
        await escenario.avance.execute(USUARIO)

        # Assert: contarlo a medio andar hundiría el promedio y toda meta se
        # vería peor a principio de mes que a fin de mes.
        assert escenario.reportes.periodos_pedidos[-1][1] == date(2026, 7, 31)

    async def test_informa_sobre_cuantos_meses_calculo(self, escenario: _Escenario) -> None:
        # Arrange
        escenario.con_meta()
        escenario.con_acumulado("500000.00")
        escenario.con_meses("300000.00", "200000.00", "400000.00")

        # Act
        avance = (await escenario.avance.execute(USUARIO))[0]

        # Assert: sin esto, la fecha estimada se leería como una predicción.
        assert avance.projection is not None
        assert avance.projection.months_of_history == 3


class TestHistorialInsuficiente:
    async def test_con_un_solo_mes_no_proyecta(self, escenario: _Escenario) -> None:
        # Arrange
        escenario.con_meta()
        escenario.con_acumulado("500000.00")
        escenario.con_meses("300000.00")

        # Act
        avance = (await escenario.avance.execute(USUARIO))[0]

        # Assert: lo informa en vez de proyectar (§21.3).
        assert avance.projection is None
        assert avance.status is None

    async def test_una_meta_de_este_mes_no_tiene_meses_cerrados(
        self, escenario: _Escenario
    ) -> None:
        # Arrange
        escenario.con_meta(starts_on=date(2026, 8, 1))
        escenario.con_meses("300000.00", "300000.00")

        # Act
        avance = (await escenario.avance.execute(USUARIO))[0]

        # Assert: ni siquiera se le pregunta a la base por meses cerrados.
        assert avance.projection is None

    async def test_alcanzada_se_informa_aunque_falte_historial(self, escenario: _Escenario) -> None:
        # Arrange
        escenario.con_meta(objetivo="500000.00", starts_on=date(2026, 8, 1))
        escenario.con_acumulado("600000.00")

        # Act
        avance = (await escenario.avance.execute(USUARIO))[0]

        # Assert: `ACHIEVED` se mide, no se estima.
        assert avance.status is GoalStatus.ACHIEVED
        assert avance.projection is None


class TestEstados:
    async def test_llegar_despues_de_la_fecha_objetivo_es_riesgo(
        self, escenario: _Escenario
    ) -> None:
        # Arrange: faltan 1.500.000 a 300.000 por mes son 5 meses, y la fecha
        # objetivo es en octubre.
        escenario.con_meta(objetivo="2000000.00", target_date=date(2026, 10, 31))
        escenario.con_acumulado("500000.00")
        escenario.con_meses("300000.00", "300000.00")

        # Act
        avance = (await escenario.avance.execute(USUARIO))[0]

        # Assert
        assert avance.status is GoalStatus.AT_RISK

    async def test_llegar_a_tiempo_va_en_camino(self, escenario: _Escenario) -> None:
        # Arrange
        escenario.con_meta(objetivo="2000000.00", target_date=date(2027, 6, 30))
        escenario.con_acumulado("500000.00")
        escenario.con_meses("300000.00", "300000.00")

        # Act
        avance = (await escenario.avance.execute(USUARIO))[0]

        # Assert
        assert avance.status is GoalStatus.ON_TRACK

    async def test_una_meta_alcanzada_deja_de_proyectar_una_fecha(
        self, escenario: _Escenario
    ) -> None:
        # Arrange
        escenario.con_meta(objetivo="500000.00")
        escenario.con_acumulado("700000.00")
        escenario.con_meses("300000.00", "300000.00")

        # Act
        avance = (await escenario.avance.execute(USUARIO))[0]

        # Assert: ya está; "llegás en 0 meses" no es información.
        assert avance.status is GoalStatus.ACHIEVED
        assert avance.remaining == plata("0.00")
        assert avance.projection is None

    async def test_gastar_mas_de_lo_que_entra_no_da_avance_negativo(
        self, escenario: _Escenario
    ) -> None:
        # Arrange: balance negativo desde que arrancó la meta.
        escenario.con_meta(objetivo="2000000.00")
        escenario.reportes.resumen = PeriodSummary(
            currency=MONEDA,
            date_from=INICIO,
            date_to=HOY.date(),
            income=Money.zero(MONEDA),
            expense=plata("80000.00"),
        )
        escenario.con_meses("-40000.00", "-40000.00")

        # Act
        avance = (await escenario.avance.execute(USUARIO))[0]

        # Assert: a ese ritmo no se llega nunca, y el porcentaje no baja de cero.
        assert avance.percentage == Decimal("0.00")
        assert avance.status is GoalStatus.AT_RISK
        assert avance.projection is not None
        assert avance.projection.months_to_target is None
        assert avance.projection.projected_date is None


class TestAbm:
    async def test_crea_una_meta(self, escenario: _Escenario) -> None:
        # Arrange / Act
        meta = await escenario.crear.execute(
            USUARIO, name="Viaje", target_amount=Decimal("2000000.00")
        )

        # Assert
        assert meta.id is not None
        assert meta.target == plata("2000000.00")

    async def test_sin_fecha_de_inicio_arranca_hoy(self, escenario: _Escenario) -> None:
        # Arrange / Act
        meta = await escenario.crear.execute(
            USUARIO, name="Viaje", target_amount=Decimal("2000000.00")
        )

        # Assert: contar retroactivamente inflaría el avance desde el minuto cero.
        assert meta.starts_on == HOY.date()

    async def test_no_deja_repetir_el_nombre(self, escenario: _Escenario) -> None:
        # Arrange
        escenario.con_meta(nombre="Viaje")

        # Act / Assert: la pantalla y el asistente las nombran por el nombre.
        with pytest.raises(DuplicateResourceError):
            await escenario.crear.execute(USUARIO, name="viaje", target_amount=Decimal("100000.00"))

    async def test_edita_el_objetivo(self, escenario: _Escenario) -> None:
        # Arrange
        meta = escenario.con_meta(objetivo="2000000.00")

        # Act
        actualizada = await escenario.editar.execute(
            USUARIO, meta.id or 0, target_amount=Decimal("3000000.00")
        )

        # Assert
        assert actualizada.target == plata("3000000.00")

    async def test_puede_sacar_la_fecha_objetivo(self, escenario: _Escenario) -> None:
        # Arrange
        meta = escenario.con_meta(target_date=date(2026, 12, 31))

        # Act
        actualizada = await escenario.editar.execute(
            USUARIO, meta.id or 0, limpiar_target_date=True
        )

        # Assert: sin el flag, `None` significaría "no lo toques".
        assert actualizada.target_date is None

    async def test_no_deja_el_inicio_despues_de_la_fecha_objetivo(
        self, escenario: _Escenario
    ) -> None:
        # Arrange
        meta = escenario.con_meta(starts_on=INICIO, target_date=date(2026, 6, 1))

        # Act / Assert: mover un solo campo puede romper la combinación.
        with pytest.raises(InvalidSavingsGoalError):
            await escenario.editar.execute(USUARIO, meta.id or 0, starts_on=date(2026, 9, 1))

    async def test_una_meta_pausada_no_sale_en_el_avance(self, escenario: _Escenario) -> None:
        # Arrange
        meta = escenario.con_meta()
        await escenario.editar.execute(USUARIO, meta.id or 0, is_active=False)

        # Act
        avances = await escenario.avance.execute(USUARIO)

        # Assert
        assert avances == []

    async def test_borra_una_meta(self, escenario: _Escenario) -> None:
        # Arrange
        meta = escenario.con_meta()

        # Act
        await escenario.borrar.execute(USUARIO, meta.id or 0)

        # Assert
        assert await escenario.listar.execute(USUARIO) == []


class TestAislamiento:
    async def test_no_se_puede_tocar_una_meta_ajena(self, escenario: _Escenario) -> None:
        # Arrange
        meta = escenario.con_meta()

        # Act / Assert: un recurso ajeno es un 404, no un 403 (§21.5).
        with pytest.raises(ResourceNotFoundError):
            await escenario.editar.execute(USUARIO + 1, meta.id or 0, name="Otro")

    async def test_el_avance_solo_trae_las_propias(self, escenario: _Escenario) -> None:
        # Arrange
        escenario.con_meta()

        # Act
        avances = await escenario.avance.execute(USUARIO + 1)

        # Assert
        assert avances == []
