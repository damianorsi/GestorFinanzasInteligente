"""Tests de extremo a extremo de metas de ahorro (docs/PROMPT.md §21.3)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import CuentaDePrueba, crear_cuenta

pytestmark = pytest.mark.integration

RUTA = "/api/v1/savings-goals"
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


async def _crear_meta(
    client: AsyncClient,
    cuenta: CuentaDePrueba,
    nombre: str = "Viaje",
    objetivo: str = "2000000.00",
    starts_on: str | None = "2026-03-01",
    target_date: str | None = None,
) -> dict[str, object]:
    cuerpo: dict[str, object] = {"name": nombre, "target_amount": objetivo}
    if starts_on is not None:
        cuerpo["starts_on"] = starts_on
    if target_date is not None:
        cuerpo["target_date"] = target_date

    respuesta = await client.post(RUTA, headers=cuenta.headers, json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    return dict(respuesta.json())


async def _ingresar(client: AsyncClient, cuenta: CuentaDePrueba, monto: str, cuando: str) -> None:
    respuesta = await client.post(
        TRANSACCIONES,
        headers=cuenta.headers,
        json={
            "category_id": await _categoria_id(client, cuenta, "Sueldo"),
            "type": "INCOME",
            "amount": monto,
            "occurred_on": cuando,
        },
    )
    assert respuesta.status_code == 201, respuesta.text


class TestAbm:
    async def test_crear_devuelve_201_con_location(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange / Act
        respuesta = await client.post(
            RUTA,
            headers=cuenta.headers,
            json={"name": "Viaje", "target_amount": "2000000.00"},
        )

        # Assert
        assert respuesta.status_code == 201
        assert respuesta.headers["Location"].endswith(str(respuesta.json()["id"]))

    async def test_un_objetivo_en_cero_es_422(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange / Act
        respuesta = await client.post(
            RUTA, headers=cuenta.headers, json={"name": "Viaje", "target_amount": "0.00"}
        )

        # Assert
        assert respuesta.status_code == 422

    async def test_el_nombre_repetido_es_409(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear_meta(client, cuenta, nombre="Viaje")

        # Act
        respuesta = await client.post(
            RUTA, headers=cuenta.headers, json={"name": "viaje", "target_amount": "500000.00"}
        )

        # Assert
        assert respuesta.status_code == 409

    async def test_editar_el_objetivo(self, client: AsyncClient, cuenta: CuentaDePrueba) -> None:
        # Arrange
        meta = await _crear_meta(client, cuenta)

        # Act
        respuesta = await client.patch(
            f"{RUTA}/{meta['id']}",
            headers=cuenta.headers,
            json={"target_amount": "3000000.00"},
        )

        # Assert
        assert respuesta.status_code == 200
        assert respuesta.json()["target_amount"] == "3000000.00"

    async def test_sacar_la_fecha_objetivo(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        meta = await _crear_meta(client, cuenta, target_date="2026-12-31")

        # Act
        respuesta = await client.patch(
            f"{RUTA}/{meta['id']}", headers=cuenta.headers, json={"clear_target_date": True}
        )

        # Assert: `target_date: null` significaría "no lo toques".
        assert respuesta.status_code == 200
        assert respuesta.json()["target_date"] is None

    async def test_borrar_devuelve_204(self, client: AsyncClient, cuenta: CuentaDePrueba) -> None:
        # Arrange
        meta = await _crear_meta(client, cuenta)

        # Act
        respuesta = await client.delete(f"{RUTA}/{meta['id']}", headers=cuenta.headers)

        # Assert
        assert respuesta.status_code == 204
        assert (await client.get(RUTA, headers=cuenta.headers)).json() == []

    async def test_una_meta_pausada_no_sale_en_el_avance(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        meta = await _crear_meta(client, cuenta)

        # Act
        await client.patch(
            f"{RUTA}/{meta['id']}", headers=cuenta.headers, json={"is_active": False}
        )

        # Assert
        assert (await client.get(f"{RUTA}/progress", headers=cuenta.headers)).json() == []


class TestAvance:
    async def test_mide_el_acumulado_desde_el_inicio(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange: un ingreso antes de que arranque la meta y otro después.
        await _crear_meta(client, cuenta, objetivo="1000000.00", starts_on="2026-03-01")
        await _ingresar(client, cuenta, "900000.00", "2026-02-15")
        await _ingresar(client, cuenta, "250000.00", "2026-03-10")

        # Act
        avance = (await client.get(f"{RUTA}/progress", headers=cuenta.headers)).json()[0]

        # Assert: el de febrero no cuenta.
        assert avance["saved"] == "250000.00"
        assert avance["remaining"] == "750000.00"
        assert avance["percentage"] == "25.00"

    async def test_sin_historial_suficiente_no_proyecta(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange: un solo mes cerrado con movimientos.
        await _crear_meta(client, cuenta, starts_on="2026-03-01")
        await _ingresar(client, cuenta, "250000.00", "2026-03-10")

        # Act
        avance = (await client.get(f"{RUTA}/progress", headers=cuenta.headers)).json()[0]

        # Assert: lo informa en vez de proyectar, y no se inventa un estado.
        assert avance["projection"] is None
        assert avance["status"] is None

    async def test_proyecta_diciendo_sobre_cuantos_meses(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear_meta(client, cuenta, objetivo="1000000.00", starts_on="2026-03-01")
        await _ingresar(client, cuenta, "200000.00", "2026-03-10")
        await _ingresar(client, cuenta, "200000.00", "2026-04-10")

        # Act
        avance = (await client.get(f"{RUTA}/progress", headers=cuenta.headers)).json()[0]

        # Assert: sin `months_of_history`, la fecha se leería como predicción.
        assert avance["projection"] is not None
        assert avance["projection"]["monthly_rate"] == "200000.00"
        assert avance["projection"]["months_of_history"] == 2

    async def test_una_meta_alcanzada_no_proyecta(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear_meta(client, cuenta, objetivo="300000.00", starts_on="2026-03-01")
        await _ingresar(client, cuenta, "200000.00", "2026-03-10")
        await _ingresar(client, cuenta, "200000.00", "2026-04-10")

        # Act
        avance = (await client.get(f"{RUTA}/progress", headers=cuenta.headers)).json()[0]

        # Assert
        assert avance["status"] == "ACHIEVED"
        assert avance["projection"] is None
        assert avance["remaining"] == "0.00"


class TestAislamiento:
    async def test_la_meta_de_otro_es_404(self, client: AsyncClient) -> None:
        # Arrange
        propia = await crear_cuenta(client, "damian@ejemplo.com")
        ajena = await crear_cuenta(client, "otro@ejemplo.com")
        meta = await _crear_meta(client, propia)

        # Act
        respuesta = await client.patch(
            f"{RUTA}/{meta['id']}", headers=ajena.headers, json={"name": "Mía"}
        )

        # Assert: un recurso ajeno es un 404, no un 403 (§21.5).
        assert respuesta.status_code == 404

    async def test_el_listado_no_mezcla_usuarios(self, client: AsyncClient) -> None:
        # Arrange
        propia = await crear_cuenta(client, "damian@ejemplo.com")
        ajena = await crear_cuenta(client, "otro@ejemplo.com")
        await _crear_meta(client, propia)

        # Act
        respuesta = await client.get(RUTA, headers=ajena.headers)

        # Assert
        assert respuesta.json() == []

    async def test_sin_token_es_401(self, client: AsyncClient) -> None:
        # Arrange / Act / Assert
        assert (await client.get(RUTA)).status_code == 401
