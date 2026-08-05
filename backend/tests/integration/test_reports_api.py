"""Tests de extremo a extremo de los reportes.

Las agregaciones las hace MySQL, así que solo valen contra la base real.
"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import CuentaDePrueba, crear_cuenta

pytestmark = pytest.mark.integration

RUTA = "/api/v1/reports"
TRANSACCIONES = "/api/v1/transactions"
CATEGORIAS = "/api/v1/categories"


@pytest.fixture(autouse=True)
def _base_limpia(db_session: AsyncSession) -> None:
    return None


@pytest.fixture
async def cuenta(client: AsyncClient) -> CuentaDePrueba:
    return await crear_cuenta(client, "damian@ejemplo.com")


async def _categoria_id(client: AsyncClient, cuenta: CuentaDePrueba, nombre: str) -> int:
    listado = (await client.get(CATEGORIAS, headers=cuenta.headers)).json()
    return next(c["id"] for c in listado if c["name"] == nombre)


async def _crear(
    client: AsyncClient,
    cuenta: CuentaDePrueba,
    categoria: str,
    monto: str,
    dia: str,
    tipo: str = "EXPENSE",
) -> None:
    respuesta = await client.post(
        TRANSACCIONES,
        headers=cuenta.headers,
        json={
            "type": tipo,
            "amount": monto,
            "occurred_on": dia,
            "category_id": await _categoria_id(client, cuenta, categoria),
        },
    )
    assert respuesta.status_code == 201, respuesta.text


class TestResumen:
    async def test_suma_ingresos_y_gastos_del_periodo(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear(client, cuenta, "Sueldo", "850000.00", "2026-08-01", "INCOME")
        await _crear(client, cuenta, "Alimentación", "120000.50", "2026-08-10")
        await _crear(client, cuenta, "Ocio", "30000.25", "2026-08-20")

        # Act
        cuerpo = (
            await client.get(
                f"{RUTA}/summary?date_from=2026-08-01&date_to=2026-08-31",
                headers=cuenta.headers,
            )
        ).json()

        # Assert
        assert cuerpo["income"] == "850000.00"
        assert cuerpo["expense"] == "150000.75"
        assert cuerpo["balance"] == "699999.25"

    async def test_el_balance_puede_ser_negativo(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear(client, cuenta, "Sueldo", "100000.00", "2026-08-01", "INCOME")
        await _crear(client, cuenta, "Vivienda", "150000.00", "2026-08-05")

        # Act
        cuerpo = (
            await client.get(
                f"{RUTA}/summary?date_from=2026-08-01&date_to=2026-08-31",
                headers=cuenta.headers,
            )
        ).json()

        # Assert
        assert cuerpo["balance"] == "-50000.00"

    async def test_un_periodo_sin_movimientos_devuelve_ceros(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        """Respuesta vacía bien formada, no un error."""
        # Arrange / Act
        respuesta = await client.get(
            f"{RUTA}/summary?date_from=2020-01-01&date_to=2020-01-31", headers=cuenta.headers
        )

        # Assert
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["income"] == "0.00"
        assert cuerpo["expense"] == "0.00"
        assert cuerpo["balance"] == "0.00"

    async def test_excluye_los_movimientos_fuera_del_periodo(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear(client, cuenta, "Alimentación", "100.00", "2026-07-31")
        await _crear(client, cuenta, "Alimentación", "200.00", "2026-08-01")
        await _crear(client, cuenta, "Alimentación", "400.00", "2026-09-01")

        # Act
        cuerpo = (
            await client.get(
                f"{RUTA}/summary?date_from=2026-08-01&date_to=2026-08-31",
                headers=cuenta.headers,
            )
        ).json()

        # Assert
        assert cuerpo["expense"] == "200.00"

    async def test_sin_periodo_usa_el_mes_en_curso(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange / Act
        cuerpo = (await client.get(f"{RUTA}/summary", headers=cuenta.headers)).json()

        # Assert
        desde = date.fromisoformat(cuerpo["date_from"])
        hasta = date.fromisoformat(cuerpo["date_to"])
        assert desde.day == 1
        assert (desde.year, desde.month) == (hasta.year, hasta.month)
        assert hasta.day == calendar.monthrange(hasta.year, hasta.month)[1]

    async def test_no_incluye_movimientos_de_otro_usuario(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        otra = await crear_cuenta(client, "otra@ejemplo.com")
        await _crear(client, otra, "Alimentación", "999999.00", "2026-08-10")

        # Act
        cuerpo = (
            await client.get(
                f"{RUTA}/summary?date_from=2026-08-01&date_to=2026-08-31",
                headers=cuenta.headers,
            )
        ).json()

        # Assert
        assert cuerpo["expense"] == "0.00"


class TestPorCategoria:
    async def test_agrupa_y_ordena_de_mayor_a_menor(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear(client, cuenta, "Alimentación", "500.00", "2026-08-01")
        await _crear(client, cuenta, "Alimentación", "300.00", "2026-08-02")
        await _crear(client, cuenta, "Ocio", "200.00", "2026-08-03")

        # Act
        cuerpo = (
            await client.get(
                f"{RUTA}/by-category?date_from=2026-08-01&date_to=2026-08-31",
                headers=cuenta.headers,
            )
        ).json()

        # Assert
        assert [(e["category_name"], e["total"]) for e in cuerpo["entries"]] == [
            ("Alimentación", "800.00"),
            ("Ocio", "200.00"),
        ]

    async def test_cuenta_los_movimientos_de_cada_categoria(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear(client, cuenta, "Alimentación", "500.00", "2026-08-01")
        await _crear(client, cuenta, "Alimentación", "300.00", "2026-08-02")

        # Act
        cuerpo = (
            await client.get(
                f"{RUTA}/by-category?date_from=2026-08-01&date_to=2026-08-31",
                headers=cuenta.headers,
            )
        ).json()

        # Assert
        assert cuerpo["entries"][0]["transaction_count"] == 2

    async def test_los_porcentajes_suman_cien(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear(client, cuenta, "Alimentación", "750.00", "2026-08-01")
        await _crear(client, cuenta, "Ocio", "250.00", "2026-08-02")

        # Act
        cuerpo = (
            await client.get(
                f"{RUTA}/by-category?date_from=2026-08-01&date_to=2026-08-31",
                headers=cuenta.headers,
            )
        ).json()

        # Assert
        porcentajes = [Decimal(e["percentage"]) for e in cuerpo["entries"]]
        assert porcentajes == [Decimal("75.00"), Decimal("25.00")]
        assert sum(porcentajes) == Decimal("100.00")

    async def test_filtra_por_tipo(self, client: AsyncClient, cuenta: CuentaDePrueba) -> None:
        # Arrange
        await _crear(client, cuenta, "Sueldo", "1000.00", "2026-08-01", "INCOME")
        await _crear(client, cuenta, "Ocio", "200.00", "2026-08-02")

        # Act
        cuerpo = (
            await client.get(
                f"{RUTA}/by-category?date_from=2026-08-01&date_to=2026-08-31&type=INCOME",
                headers=cuenta.headers,
            )
        ).json()

        # Assert
        assert len(cuerpo["entries"]) == 1
        assert cuerpo["entries"][0]["category_name"] == "Sueldo"

    async def test_sin_movimientos_devuelve_lista_vacia(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange / Act
        respuesta = await client.get(
            f"{RUTA}/by-category?date_from=2020-01-01&date_to=2020-01-31",
            headers=cuenta.headers,
        )

        # Assert
        assert respuesta.status_code == 200
        assert respuesta.json()["entries"] == []


class TestTendenciaMensual:
    async def test_devuelve_una_entrada_por_mes_sin_agujeros(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        """Los meses sin movimientos vienen en cero, no se omiten."""
        # Arrange / Act
        cuerpo = (await client.get(f"{RUTA}/monthly-trend?months=6", headers=cuenta.headers)).json()

        # Assert
        assert len(cuerpo["entries"]) == 6
        assert all(e["income"] == "0.00" and e["expense"] == "0.00" for e in cuerpo["entries"])

    async def test_los_periodos_vienen_en_orden_y_sin_repetir(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange / Act
        cuerpo = (
            await client.get(f"{RUTA}/monthly-trend?months=12", headers=cuenta.headers)
        ).json()

        # Assert
        periodos = [e["period"] for e in cuerpo["entries"]]
        assert periodos == sorted(periodos)
        assert len(set(periodos)) == 12

    async def test_el_ultimo_periodo_es_el_mes_en_curso(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        resumen = (await client.get(f"{RUTA}/summary", headers=cuenta.headers)).json()
        mes_actual = resumen["date_from"][:7]

        # Act
        cuerpo = (await client.get(f"{RUTA}/monthly-trend?months=3", headers=cuenta.headers)).json()

        # Assert
        assert cuerpo["entries"][-1]["period"] == mes_actual

    async def test_rechaza_una_ventana_fuera_de_rango(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange / Act / Assert
        assert (
            await client.get(f"{RUTA}/monthly-trend?months=0", headers=cuenta.headers)
        ).status_code == 422
        assert (
            await client.get(f"{RUTA}/monthly-trend?months=100", headers=cuenta.headers)
        ).status_code == 422


class TestSeguridad:
    @pytest.mark.parametrize("ruta", ["summary", "by-category", "monthly-trend"])
    async def test_sin_token_devuelven_401(self, client: AsyncClient, ruta: str) -> None:
        # Arrange / Act / Assert
        assert (await client.get(f"{RUTA}/{ruta}")).status_code == 401

    @pytest.mark.parametrize("ruta", ["summary", "by-category", "monthly-trend"])
    async def test_rechazan_una_moneda_no_habilitada(
        self, client: AsyncClient, cuenta: CuentaDePrueba, ruta: str
    ) -> None:
        # Arrange / Act
        respuesta = await client.get(f"{RUTA}/{ruta}?currency=USD", headers=cuenta.headers)

        # Assert
        assert respuesta.status_code == 422
        assert respuesta.json()["code"] == "unsupported_currency"
