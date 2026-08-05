"""Tests de extremo a extremo de presupuestos."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import CuentaDePrueba, crear_cuenta

pytestmark = pytest.mark.integration

RUTA = "/api/v1/budgets"
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


async def _crear_presupuesto(
    client: AsyncClient,
    cuenta: CuentaDePrueba,
    categoria: str = "Alimentación",
    monto: str = "100000.00",
    periodo: str = "2026-08",
) -> dict[str, object]:
    respuesta = await client.post(
        RUTA,
        headers=cuenta.headers,
        json={
            "category_id": await _categoria_id(client, cuenta, categoria),
            "period_month": periodo,
            "amount": monto,
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    return dict(respuesta.json())


async def _gastar(
    client: AsyncClient,
    cuenta: CuentaDePrueba,
    categoria: str,
    monto: str,
    dia: str = "2026-08-10",
) -> None:
    respuesta = await client.post(
        TRANSACCIONES,
        headers=cuenta.headers,
        json={
            "type": "EXPENSE",
            "amount": monto,
            "occurred_on": dia,
            "category_id": await _categoria_id(client, cuenta, categoria),
        },
    )
    assert respuesta.status_code == 201, respuesta.text


class TestAbm:
    async def test_crea_un_presupuesto(self, client: AsyncClient, cuenta: CuentaDePrueba) -> None:
        # Arrange / Act
        creado = await _crear_presupuesto(client, cuenta)

        # Assert
        assert creado["period_month"] == "2026-08"
        assert creado["amount"] == "100000.00"
        assert creado["currency"] == "ARS"

    async def test_rechaza_una_categoria_de_ingreso(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange / Act
        respuesta = await client.post(
            RUTA,
            headers=cuenta.headers,
            json={
                "category_id": await _categoria_id(client, cuenta, "Sueldo"),
                "period_month": "2026-08",
                "amount": "100000.00",
            },
        )

        # Assert
        assert respuesta.status_code == 422
        assert respuesta.json()["code"] == "invalid_reference"

    async def test_rechaza_un_duplicado(self, client: AsyncClient, cuenta: CuentaDePrueba) -> None:
        # Arrange
        await _crear_presupuesto(client, cuenta)

        # Act
        respuesta = await client.post(
            RUTA,
            headers=cuenta.headers,
            json={
                "category_id": await _categoria_id(client, cuenta, "Alimentación"),
                "period_month": "2026-08",
                "amount": "200000.00",
            },
        )

        # Assert
        assert respuesta.status_code == 409

    @pytest.mark.parametrize("periodo", ["2026-8-1", "agosto", "2026", "2026-13", ""])
    async def test_rechaza_periodos_mal_formados(
        self, client: AsyncClient, cuenta: CuentaDePrueba, periodo: str
    ) -> None:
        # Arrange / Act
        respuesta = await client.post(
            RUTA,
            headers=cuenta.headers,
            json={
                "category_id": await _categoria_id(client, cuenta, "Alimentación"),
                "period_month": periodo,
                "amount": "1000.00",
            },
        )

        # Assert
        assert respuesta.status_code == 422

    async def test_lista_los_del_mes_pedido(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear_presupuesto(client, cuenta, "Alimentación", periodo="2026-08")
        await _crear_presupuesto(client, cuenta, "Ocio", periodo="2026-09")

        # Act
        cuerpo = (await client.get(f"{RUTA}?period_month=2026-08", headers=cuenta.headers)).json()

        # Assert
        assert len(cuerpo) == 1

    async def test_edita_solo_el_tope(self, client: AsyncClient, cuenta: CuentaDePrueba) -> None:
        # Arrange
        creado = await _crear_presupuesto(client, cuenta)

        # Act
        respuesta = await client.patch(
            f"{RUTA}/{creado['id']}", headers=cuenta.headers, json={"amount": "150000.00"}
        )

        # Assert
        assert respuesta.status_code == 200
        assert respuesta.json()["amount"] == "150000.00"

    async def test_no_acepta_cambiar_la_categoria_ni_el_periodo(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        """Son lo que identifica al presupuesto; cambiarlos sería crear otro."""
        # Arrange
        creado = await _crear_presupuesto(client, cuenta)

        # Act
        respuesta = await client.patch(
            f"{RUTA}/{creado['id']}",
            headers=cuenta.headers,
            json={"amount": "1000.00", "period_month": "2026-09"},
        )

        # Assert
        assert respuesta.status_code == 422

    async def test_borra_el_presupuesto(self, client: AsyncClient, cuenta: CuentaDePrueba) -> None:
        # Arrange
        creado = await _crear_presupuesto(client, cuenta)

        # Act
        respuesta = await client.delete(f"{RUTA}/{creado['id']}", headers=cuenta.headers)

        # Assert
        assert respuesta.status_code == 204
        assert (
            await client.get(f"{RUTA}?period_month=2026-08", headers=cuenta.headers)
        ).json() == []


class TestProgreso:
    async def test_cruza_el_tope_con_el_gasto_real(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear_presupuesto(client, cuenta, "Alimentación", "100000.00")
        await _gastar(client, cuenta, "Alimentación", "85000.00")

        # Act
        cuerpo = (
            await client.get(f"{RUTA}/progress?period_month=2026-08", headers=cuenta.headers)
        ).json()

        # Assert
        entrada = cuerpo["entries"][0]
        assert entrada["budgeted"] == "100000.00"
        assert entrada["spent"] == "85000.00"
        assert entrada["remaining"] == "15000.00"
        assert entrada["percentage"] == "85.00"
        assert entrada["status"] == "WARNING"

    async def test_el_restante_es_negativo_al_excederse(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear_presupuesto(client, cuenta, "Ocio", "10000.00")
        await _gastar(client, cuenta, "Ocio", "13000.00")

        # Act
        cuerpo = (
            await client.get(f"{RUTA}/progress?period_month=2026-08", headers=cuenta.headers)
        ).json()

        # Assert
        entrada = cuerpo["entries"][0]
        assert entrada["remaining"] == "-3000.00"
        assert entrada["status"] == "EXCEEDED"
        assert cuerpo["exceeded_count"] == 1

    async def test_solo_cuenta_los_gastos_del_mes(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear_presupuesto(client, cuenta, "Alimentación", "100000.00", "2026-08")
        await _gastar(client, cuenta, "Alimentación", "1000.00", "2026-07-31")
        await _gastar(client, cuenta, "Alimentación", "2000.00", "2026-08-01")
        await _gastar(client, cuenta, "Alimentación", "4000.00", "2026-08-31")
        await _gastar(client, cuenta, "Alimentación", "8000.00", "2026-09-01")

        # Act
        cuerpo = (
            await client.get(f"{RUTA}/progress?period_month=2026-08", headers=cuenta.headers)
        ).json()

        # Assert
        assert cuerpo["entries"][0]["spent"] == "6000.00"

    async def test_el_gasto_sin_presupuesto_va_aparte(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear_presupuesto(client, cuenta, "Alimentación", "100000.00")
        await _gastar(client, cuenta, "Ocio", "30000.00")

        # Act
        cuerpo = (
            await client.get(f"{RUTA}/progress?period_month=2026-08", headers=cuenta.headers)
        ).json()

        # Assert
        assert len(cuerpo["entries"]) == 1
        assert len(cuerpo["unbudgeted"]) == 1
        assert cuerpo["unbudgeted"][0]["category_name"] == "Ocio"
        assert cuerpo["unbudgeted"][0]["spent"] == "30000.00"

    async def test_un_mes_vacio_no_es_un_error(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange / Act
        respuesta = await client.get(
            f"{RUTA}/progress?period_month=2020-01", headers=cuenta.headers
        )

        # Assert
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["entries"] == []
        assert cuerpo["unbudgeted"] == []
        assert cuerpo["exceeded_count"] == 0

    async def test_los_ingresos_no_cuentan_como_gasto(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear_presupuesto(client, cuenta, "Alimentación", "100000.00")
        await client.post(
            TRANSACCIONES,
            headers=cuenta.headers,
            json={
                "type": "INCOME",
                "amount": "500000.00",
                "occurred_on": "2026-08-10",
                "category_id": await _categoria_id(client, cuenta, "Sueldo"),
            },
        )

        # Act
        cuerpo = (
            await client.get(f"{RUTA}/progress?period_month=2026-08", headers=cuenta.headers)
        ).json()

        # Assert
        assert cuerpo["entries"][0]["spent"] == "0.00"
        assert cuerpo["unbudgeted"] == []


class TestCopiar:
    async def test_copia_al_mes_siguiente(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear_presupuesto(client, cuenta, "Alimentación", "100000.00", "2026-07")
        await _crear_presupuesto(client, cuenta, "Ocio", "50000.00", "2026-07")

        # Act
        respuesta = await client.post(
            f"{RUTA}/copy-from",
            headers=cuenta.headers,
            json={"from_period": "2026-07", "to_period": "2026-08"},
        )

        # Assert
        assert respuesta.status_code == 201
        assert respuesta.json()["created"] == 2
        de_agosto = (
            await client.get(f"{RUTA}?period_month=2026-08", headers=cuenta.headers)
        ).json()
        assert len(de_agosto) == 2

    async def test_no_pisa_los_existentes_y_los_informa(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear_presupuesto(client, cuenta, "Alimentación", "100000.00", "2026-07")
        await _crear_presupuesto(client, cuenta, "Ocio", "50000.00", "2026-07")
        await _crear_presupuesto(client, cuenta, "Alimentación", "999999.00", "2026-08")

        # Act
        cuerpo = (
            await client.post(
                f"{RUTA}/copy-from",
                headers=cuenta.headers,
                json={"from_period": "2026-07", "to_period": "2026-08"},
            )
        ).json()

        # Assert
        assert cuerpo["created"] == 1
        assert [s["category_name"] for s in cuerpo["skipped"]] == ["Alimentación"]
        de_agosto = (
            await client.get(f"{RUTA}?period_month=2026-08", headers=cuenta.headers)
        ).json()
        # El id se resuelve antes: un `await` dentro de la comprensión la
        # convierte en un generador asíncrono y `next()` no lo acepta.
        id_alimentacion = await _categoria_id(client, cuenta, "Alimentación")
        alimentacion = next(b for b in de_agosto if b["category_id"] == id_alimentacion)
        assert alimentacion["amount"] == "999999.00"

    async def test_rechaza_copiar_sobre_el_mismo_mes(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange / Act
        respuesta = await client.post(
            f"{RUTA}/copy-from",
            headers=cuenta.headers,
            json={"from_period": "2026-08", "to_period": "2026-08"},
        )

        # Assert
        assert respuesta.status_code == 422


class TestAislamiento:
    @pytest.fixture
    async def otra_cuenta(self, client: AsyncClient) -> CuentaDePrueba:
        return await crear_cuenta(client, "otra@ejemplo.com")

    async def test_el_listado_no_incluye_los_ajenos(
        self, client: AsyncClient, cuenta: CuentaDePrueba, otra_cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear_presupuesto(client, otra_cuenta)

        # Act
        cuerpo = (await client.get(f"{RUTA}?period_month=2026-08", headers=cuenta.headers)).json()

        # Assert
        assert cuerpo == []

    async def test_no_se_puede_editar_ni_borrar_uno_ajeno(
        self, client: AsyncClient, cuenta: CuentaDePrueba, otra_cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        ajeno = await _crear_presupuesto(client, otra_cuenta)

        # Act
        edicion = await client.patch(
            f"{RUTA}/{ajeno['id']}", headers=cuenta.headers, json={"amount": "1.00"}
        )
        borrado = await client.delete(f"{RUTA}/{ajeno['id']}", headers=cuenta.headers)

        # Assert
        assert edicion.status_code == 404
        assert borrado.status_code == 404
        sigue = (
            await client.get(f"{RUTA}?period_month=2026-08", headers=otra_cuenta.headers)
        ).json()
        assert sigue[0]["amount"] == "100000.00"

    async def test_el_progreso_no_mezcla_gastos_de_otro_usuario(
        self, client: AsyncClient, cuenta: CuentaDePrueba, otra_cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear_presupuesto(client, cuenta, "Alimentación", "100000.00")
        await _gastar(client, otra_cuenta, "Alimentación", "999999.00")

        # Act
        cuerpo = (
            await client.get(f"{RUTA}/progress?period_month=2026-08", headers=cuenta.headers)
        ).json()

        # Assert
        assert cuerpo["entries"][0]["spent"] == "0.00"

    @pytest.mark.parametrize("ruta", ["", "/progress"])
    async def test_sin_token_devuelve_401(self, client: AsyncClient, ruta: str) -> None:
        # Arrange / Act / Assert
        assert (await client.get(f"{RUTA}{ruta}?period_month=2026-08")).status_code == 401
