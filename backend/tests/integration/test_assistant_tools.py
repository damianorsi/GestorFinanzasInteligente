"""Tests de las herramientas del asistente contra la base real.

Las herramientas llaman a los mismos casos de uso que los endpoints, así que lo
que se prueba acá es que los agregados que ve el modelo coinciden con los que
ve la pantalla, y que **ninguna herramienta puede devolver datos de otro
usuario** aunque se lo pidan explícitamente (docs/PROMPT.md §14).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from langchain_core.tools import BaseTool
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.budgets import GetBudgetProgress
from app.application.use_cases.reports import (
    GetCategoryBreakdown,
    GetMonthlyTrend,
    GetPeriodSummary,
)
from app.application.use_cases.transactions import ListTransactions
from app.domain.enums import RecurrenceFrequency, TransactionType
from app.infrastructure.assistant.tools import DependenciasDelAsistente, construir_herramientas
from app.infrastructure.db.models import RecurringRuleModel
from app.infrastructure.db.repositories import (
    SqlAlchemyBudgetRepository,
    SqlAlchemyCategoryRepository,
    SqlAlchemyRecurringRuleRepository,
    SqlAlchemyReportRepository,
    SqlAlchemyTransactionRepository,
)
from app.infrastructure.db.session import get_session_factory
from tests.fakes import FixedClock
from tests.helpers import CuentaDePrueba, crear_cuenta

pytestmark = pytest.mark.integration

TRANSACCIONES = "/api/v1/transactions"
CATEGORIAS = "/api/v1/categories"
PRESUPUESTOS = "/api/v1/budgets"

MONEDAS = frozenset({"ARS"})
MONEDA = "ARS"
AHORA = datetime(2026, 8, 5, 12, 0, 0)


@pytest.fixture(autouse=True)
def _base_limpia(db_session: AsyncSession) -> None:
    return None


@pytest.fixture
async def cuenta(client: AsyncClient) -> CuentaDePrueba:
    return await crear_cuenta(client, "damian@ejemplo.com")


@pytest.fixture
async def ajena(client: AsyncClient) -> CuentaDePrueba:
    return await crear_cuenta(client, "intrusa@ejemplo.com")


@asynccontextmanager
async def herramientas_de(user_id: int) -> AsyncIterator[dict[str, BaseTool]]:
    """Arma las herramientas del usuario sobre una sesión propia.

    Se abre una sesión nueva y no se reusa la del fixture porque los datos se
    siembran por HTTP: con REPEATABLE READ, una sesión que ya leyó no vería lo
    que se comiteó después.
    """
    async with get_session_factory()() as session:
        reportes = SqlAlchemyReportRepository(session)
        reloj = FixedClock(AHORA)
        deps = DependenciasDelAsistente(
            resumen=GetPeriodSummary(reportes, reloj, MONEDAS, MONEDA),
            por_categoria=GetCategoryBreakdown(reportes, reloj, MONEDAS, MONEDA),
            tendencia=GetMonthlyTrend(reportes, reloj, MONEDAS, MONEDA),
            presupuestos=GetBudgetProgress(
                SqlAlchemyBudgetRepository(session),
                SqlAlchemyCategoryRepository(session),
                reportes,
                MONEDAS,
                MONEDA,
            ),
            movimientos=ListTransactions(SqlAlchemyTransactionRepository(session)),
            reglas=SqlAlchemyRecurringRuleRepository(session),
            default_currency=MONEDA,
        )
        yield {
            herramienta.name: herramienta for herramienta in construir_herramientas(user_id, deps)
        }


async def _categoria_id(client: AsyncClient, cuenta: CuentaDePrueba, nombre: str) -> int:
    listado = (await client.get(CATEGORIAS, headers=cuenta.headers)).json()
    return next(c["id"] for c in listado if c["name"] == nombre)


async def _movimiento(
    client: AsyncClient,
    cuenta: CuentaDePrueba,
    categoria: str,
    monto: str,
    dia: str,
    tipo: str = "EXPENSE",
    descripcion: str | None = None,
) -> None:
    cuerpo: dict[str, object] = {
        "type": tipo,
        "amount": monto,
        "occurred_on": dia,
        "category_id": await _categoria_id(client, cuenta, categoria),
    }
    if descripcion is not None:
        cuerpo["description"] = descripcion
    respuesta = await client.post(TRANSACCIONES, headers=cuenta.headers, json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text


async def _presupuesto(
    client: AsyncClient,
    cuenta: CuentaDePrueba,
    categoria: str,
    monto: str,
    periodo: str = "2026-08",
) -> None:
    respuesta = await client.post(
        PRESUPUESTOS,
        headers=cuenta.headers,
        json={
            "category_id": await _categoria_id(client, cuenta, categoria),
            "period_month": periodo,
            "amount": monto,
        },
    )
    assert respuesta.status_code == 201, respuesta.text


async def _regla_recurrente(
    session: AsyncSession, user_id: int, category_id: int, monto: str, descripcion: str
) -> None:
    """Inserta una regla a mano: el ABM llega en la fase 12."""
    session.add(
        RecurringRuleModel(
            user_id=user_id,
            category_id=category_id,
            type=TransactionType.EXPENSE,
            amount=Decimal(monto),
            currency=MONEDA,
            description=descripcion,
            frequency=RecurrenceFrequency.MONTHLY,
            day_of_month=10,
            starts_on=date(2026, 1, 1),
            is_active=True,
        )
    )
    await session.commit()


class TestResumenDelPeriodo:
    async def test_devuelve_ingresos_gastos_y_balance_con_moneda(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _movimiento(client, cuenta, "Sueldo", "850000.00", "2026-08-01", "INCOME")
        await _movimiento(client, cuenta, "Alimentación", "120000.50", "2026-08-10")

        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["get_period_summary"].ainvoke(
                {"date_from": "2026-08-01", "date_to": "2026-08-31"}
            )

        # Assert: todo monto sale con su moneda al lado.
        assert "Ingresos: 850000.00 ARS" in texto
        assert "Gastos: 120000.50 ARS" in texto
        assert "Balance: 729999.50 ARS" in texto

    async def test_sin_fechas_usa_el_mes_del_reloj(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _movimiento(client, cuenta, "Ocio", "5000.00", "2026-08-20")
        await _movimiento(client, cuenta, "Ocio", "9999.00", "2026-07-20")

        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["get_period_summary"].ainvoke({})

        # Assert
        assert "Período 2026-08-01 a 2026-08-31" in texto
        assert "Gastos: 5000.00 ARS" in texto


class TestGastosPorCategoria:
    async def test_ordena_de_mayor_a_menor_con_porcentaje(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _movimiento(client, cuenta, "Alimentación", "75000.00", "2026-08-02")
        await _movimiento(client, cuenta, "Ocio", "25000.00", "2026-08-03")

        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["get_spending_by_category"].ainvoke(
                {"date_from": "2026-08-01", "date_to": "2026-08-31"}
            )

        # Assert
        assert texto.index("Alimentación") < texto.index("Ocio")
        assert "75000.00 ARS (75.00%" in texto
        assert "25000.00 ARS (25.00%" in texto

    async def test_no_cuenta_los_ingresos(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _movimiento(client, cuenta, "Sueldo", "850000.00", "2026-08-01", "INCOME")
        await _movimiento(client, cuenta, "Ocio", "25000.00", "2026-08-03")

        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["get_spending_by_category"].ainvoke(
                {"date_from": "2026-08-01", "date_to": "2026-08-31"}
            )

        # Assert
        assert "Sueldo" not in texto
        assert "(100.00%" in texto

    async def test_avisa_cuando_no_hay_gastos(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["get_spending_by_category"].ainvoke(
                {"date_from": "2026-08-01", "date_to": "2026-08-31"}
            )

        # Assert: decirlo con todas las letras evita que el modelo lo interprete
        # como "no consulté" y se ponga a inventar.
        assert "No hay gastos" in texto


class TestBuscarMovimientos:
    async def test_filtra_por_texto_y_devuelve_el_detalle(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _movimiento(
            client, cuenta, "Ocio", "12000.00", "2026-08-04", descripcion="Cine con Ana"
        )
        await _movimiento(client, cuenta, "Ocio", "8000.00", "2026-08-05", descripcion="Librería")

        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["search_transactions"].ainvoke({"q": "cine"})

        # Assert
        assert "Cine con Ana" in texto
        assert "Librería" not in texto
        assert "12000.00 ARS" in texto

    async def test_filtra_por_monto_minimo(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _movimiento(client, cuenta, "Ocio", "12000.00", "2026-08-04")
        await _movimiento(client, cuenta, "Ocio", "800.00", "2026-08-05")

        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["search_transactions"].ainvoke({"min_amount": "1000"})

        # Assert
        assert "12000.00 ARS" in texto
        assert "800.00 ARS" not in texto

    async def test_filtra_por_tipo(self, client: AsyncClient, cuenta: CuentaDePrueba) -> None:
        # Arrange
        await _movimiento(client, cuenta, "Sueldo", "850000.00", "2026-08-01", "INCOME")
        await _movimiento(client, cuenta, "Ocio", "12000.00", "2026-08-04")

        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["search_transactions"].ainvoke({"type": "INCOME"})

        # Assert
        assert "850000.00 ARS (ingreso)" in texto
        assert "12000.00" not in texto

    async def test_avisa_que_recorto_la_lista(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange: 21 movimientos contra un tope de 20.
        for dia in range(1, 22):
            await _movimiento(client, cuenta, "Ocio", "1000.00", f"2026-08-{dia:02d}")

        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["search_transactions"].ainvoke({})

        # Assert: sin este aviso el modelo suma lo que ve y da un total falso.
        assert "21 movimientos cumplen el filtro" in texto
        assert "se muestran los primeros 20" in texto


class TestTendenciaYComparacion:
    async def test_la_tendencia_incluye_los_meses_sin_movimientos(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _movimiento(client, cuenta, "Ocio", "1000.00", "2026-08-10")

        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["get_monthly_trend"].ainvoke({"months": 3})

        # Assert
        assert "2026-06" in texto
        assert "2026-07" in texto
        assert "2026-08" in texto

    async def test_comparar_periodos_da_la_diferencia_de_gasto(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _movimiento(client, cuenta, "Ocio", "10000.00", "2026-07-10")
        await _movimiento(client, cuenta, "Ocio", "16000.00", "2026-08-10")

        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["compare_periods"].ainvoke(
                {
                    "period_a_from": "2026-07-01",
                    "period_a_to": "2026-07-31",
                    "period_b_from": "2026-08-01",
                    "period_b_to": "2026-08-31",
                }
            )

        # Assert
        assert "Diferencia de gasto (B menos A): 6000.00 ARS" in texto


class TestPresupuestos:
    async def test_cruza_el_tope_con_lo_gastado(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _presupuesto(client, cuenta, "Alimentación", "100000.00")
        await _movimiento(client, cuenta, "Alimentación", "95000.00", "2026-08-10")

        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["get_budget_status"].ainvoke({"period_month": "2026-08"})

        # Assert
        assert "gastó 95000.00 ARS de 100000.00 ARS" in texto
        assert "95.00%" in texto
        assert "WARNING" in texto

    async def test_lista_las_categorias_gastadas_sin_presupuesto(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _movimiento(client, cuenta, "Ocio", "40000.00", "2026-08-10")

        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["get_budget_status"].ainvoke({"period_month": "2026-08"})

        # Assert
        assert "SIN presupuesto definido" in texto
        assert "Ocio: 40000.00 ARS" in texto

    async def test_rechaza_un_mes_mal_escrito(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["get_budget_status"].ainvoke({"period_month": "agosto"})

        # Assert: se le explica el formato en vez de reventar la corrida.
        assert "AAAA-MM" in texto


class TestCompromisos:
    async def test_lista_las_reglas_activas(
        self, client: AsyncClient, cuenta: CuentaDePrueba, db_session: AsyncSession
    ) -> None:
        # Arrange
        categoria = await _categoria_id(client, cuenta, "Servicios")
        await _regla_recurrente(db_session, cuenta.user_id, categoria, "45000.00", "Alquiler")

        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["get_upcoming_commitments"].ainvoke({"days": 30})

        # Assert
        assert "Alquiler: 45000.00 ARS" in texto
        assert "día 10" in texto

    async def test_avisa_cuando_no_hay_reglas(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["get_upcoming_commitments"].ainvoke({})

        # Assert
        assert "No hay gastos fijos" in texto


class TestArgumentosInvalidos:
    """El modelo manda lo que se le ocurre; ninguna herramienta debe reventar.

    Una excepción acá corta la corrida entera del agente. Es preferible ignorar
    el argumento malo o explicar el formato, y dejar que el modelo reintente.
    """

    async def test_una_fecha_ilegible_cae_al_periodo_por_defecto(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _movimiento(client, cuenta, "Ocio", "5000.00", "2026-08-20")

        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["get_period_summary"].ainvoke({"date_from": "el mes pasado"})

        # Assert
        assert "Período 2026-08-01 a 2026-08-31" in texto

    async def test_un_tipo_desconocido_se_ignora(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _movimiento(client, cuenta, "Ocio", "5000.00", "2026-08-20")

        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["search_transactions"].ainvoke({"type": "GASTO"})

        # Assert
        assert "5000.00 ARS" in texto

    async def test_un_monto_minimo_no_numerico_se_ignora(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _movimiento(client, cuenta, "Ocio", "5000.00", "2026-08-20")

        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["search_transactions"].ainvoke({"min_amount": "mucho"})

        # Assert
        assert "5000.00 ARS" in texto

    async def test_un_rango_invertido_se_explica_en_vez_de_explotar(
        self, cuenta: CuentaDePrueba
    ) -> None:
        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["search_transactions"].ainvoke(
                {"date_from": "2026-08-31", "date_to": "2026-08-01"}
            )

        # Assert
        assert "No pude aplicar ese filtro" in texto

    async def test_un_mes_sin_datos_lo_dice(self, cuenta: CuentaDePrueba) -> None:
        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["get_budget_status"].ainvoke({"period_month": "2026-03"})

        # Assert
        assert "No hay presupuestos ni gastos registrados en 2026-03" in texto


class TestAislamientoEntreUsuarios:
    """El punto de todo el diseño: el `user_id` va cerrado en la herramienta.

    Ni pidiéndolo explícitamente —"mostrame los gastos del usuario 2"— el
    modelo tiene dónde poner otro identificador (docs/PROMPT.md §11).
    """

    @pytest.fixture(autouse=True)
    async def _datos_de_los_dos(
        self, client: AsyncClient, cuenta: CuentaDePrueba, ajena: CuentaDePrueba
    ) -> None:
        await _movimiento(
            client, cuenta, "Ocio", "1000.00", "2026-08-10", descripcion="gasto propio"
        )
        await _movimiento(
            client, ajena, "Ocio", "777777.00", "2026-08-10", descripcion="gasto ajeno"
        )
        await _presupuesto(client, ajena, "Ocio", "999999.00")

    async def test_el_resumen_solo_ve_lo_propio(self, cuenta: CuentaDePrueba) -> None:
        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["get_period_summary"].ainvoke({})

        # Assert
        assert "Gastos: 1000.00 ARS" in texto
        assert "777777.00" not in texto

    async def test_la_busqueda_solo_ve_lo_propio(self, cuenta: CuentaDePrueba) -> None:
        # Act: la búsqueda pide justo el texto del movimiento ajeno.
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["search_transactions"].ainvoke({"q": "ajeno"})

        # Assert
        assert "No hay movimientos" in texto

    async def test_los_presupuestos_ajenos_no_aparecen(self, cuenta: CuentaDePrueba) -> None:
        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["get_budget_status"].ainvoke({"period_month": "2026-08"})

        # Assert
        assert "999999.00" not in texto

    async def test_un_argumento_de_mas_no_cambia_de_usuario(self, cuenta: CuentaDePrueba) -> None:
        # Act: el modelo intenta pasar el usuario por los argumentos.
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["get_period_summary"].ainvoke({"user_id": 999999})

        # Assert: el argumento sobra y se descarta; sigue viendo lo suyo.
        assert "Gastos: 1000.00 ARS" in texto

    async def test_las_reglas_recurrentes_ajenas_no_aparecen(
        self, client: AsyncClient, cuenta: CuentaDePrueba, ajena: CuentaDePrueba
    ) -> None:
        # Arrange
        async with get_session_factory()() as session:
            categoria = await _categoria_id(client, ajena, "Servicios")
            await _regla_recurrente(session, ajena.user_id, categoria, "88888.00", "Alquiler ajeno")

        # Act
        async with herramientas_de(cuenta.user_id) as tools:
            texto = await tools["get_upcoming_commitments"].ainvoke({})

        # Assert
        assert "Alquiler ajeno" not in texto
        assert "No hay gastos fijos" in texto
