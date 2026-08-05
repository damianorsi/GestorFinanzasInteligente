"""Tests de extremo a extremo de la exportación a CSV."""

from __future__ import annotations

import csv
import io

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import CuentaDePrueba, crear_cuenta

pytestmark = pytest.mark.integration

RUTA = "/api/v1/transactions/export"
TRANSACCIONES = "/api/v1/transactions"
CATEGORIAS = "/api/v1/categories"
BOM = b"\xef\xbb\xbf"


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
    categoria: str = "Alimentación",
    monto: str = "1234.56",
    dia: str = "2026-08-05",
    descripcion: str = "",
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
            "description": descripcion,
        },
    )
    assert respuesta.status_code == 201, respuesta.text


def _filas(contenido: bytes, delimitador: str = ",") -> list[list[str]]:
    return list(csv.reader(io.StringIO(contenido.decode("utf-8-sig")), delimiter=delimitador))


class TestExport:
    async def test_devuelve_un_csv_como_adjunto(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear(client, cuenta)

        # Act
        respuesta = await client.get(RUTA, headers=cuenta.headers)

        # Assert
        assert respuesta.status_code == 200
        assert respuesta.headers["content-type"].startswith("text/csv")
        assert "attachment" in respuesta.headers["content-disposition"]
        assert ".csv" in respuesta.headers["content-disposition"]

    async def test_arranca_con_el_bom(self, client: AsyncClient, cuenta: CuentaDePrueba) -> None:
        # Arrange
        await _crear(client, cuenta)

        # Act
        contenido = (await client.get(RUTA, headers=cuenta.headers)).content

        # Assert
        assert contenido.startswith(BOM)

    async def test_incluye_los_movimientos_con_su_categoria_resuelta(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        """El CSV lo lee una persona: lleva el nombre de la categoría, no el id."""
        # Arrange
        await _crear(client, cuenta, "Ocio", "500.00", descripcion="Cine")

        # Act
        filas = _filas((await client.get(RUTA, headers=cuenta.headers)).content)

        # Assert
        assert len(filas) == 2
        assert filas[1][3] == "Ocio"
        assert filas[1][4] == "Cine"
        assert filas[1][5] == "500.00"

    async def test_una_descripcion_con_comas_no_rompe_las_columnas(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear(client, cuenta, descripcion='Pan, leche y "queso"')

        # Act
        filas = _filas((await client.get(RUTA, headers=cuenta.headers)).content)

        # Assert
        assert len(filas[1]) == 8
        assert filas[1][4] == 'Pan, leche y "queso"'

    async def test_respeta_los_mismos_filtros_que_el_listado(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear(client, cuenta, "Alimentación", "100.00", "2026-07-15")
        await _crear(client, cuenta, "Alimentación", "200.00", "2026-08-15")
        await _crear(client, cuenta, "Sueldo", "900.00", "2026-08-20", tipo="INCOME")

        # Act
        filas = _filas(
            (
                await client.get(
                    f"{RUTA}?date_from=2026-08-01&date_to=2026-08-31&type=EXPENSE",
                    headers=cuenta.headers,
                )
            ).content
        )

        # Assert
        assert len(filas) == 2
        assert filas[1][5] == "200.00"

    async def test_un_export_sin_resultados_igual_trae_los_encabezados(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        """Un archivo vacío es indistinguible de una descarga fallida."""
        # Arrange / Act
        respuesta = await client.get(
            f"{RUTA}?date_from=2020-01-01&date_to=2020-01-31", headers=cuenta.headers
        )

        # Assert
        assert respuesta.status_code == 200
        filas = _filas(respuesta.content)
        assert len(filas) == 1
        assert filas[0][0] == "id"

    async def test_el_formato_excel_usa_punto_y_coma_y_coma_decimal(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear(client, cuenta, monto="1234.56")

        # Act
        contenido = (await client.get(f"{RUTA}?format=excel_es", headers=cuenta.headers)).content

        # Assert
        filas = _filas(contenido, delimitador=";")
        assert len(filas[1]) == 8
        assert filas[1][5] == "1234,56"

    async def test_rechaza_un_formato_desconocido(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange / Act / Assert
        assert (
            await client.get(f"{RUTA}?format=inventado", headers=cuenta.headers)
        ).status_code == 422

    async def test_sin_token_devuelve_401(self, client: AsyncClient) -> None:
        # Arrange / Act / Assert
        assert (await client.get(RUTA)).status_code == 401

    async def test_no_exporta_movimientos_ajenos(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        otra = await crear_cuenta(client, "otra@ejemplo.com")
        await _crear(client, otra, descripcion="Secreto")
        await _crear(client, cuenta, descripcion="Propio")

        # Act
        filas = _filas((await client.get(RUTA, headers=cuenta.headers)).content)

        # Assert
        assert len(filas) == 2
        assert filas[1][4] == "Propio"

    async def test_la_ruta_export_no_se_confunde_con_un_id(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        """`/transactions/export` tiene que declararse antes que `/{id}`."""
        # Arrange / Act
        respuesta = await client.get(RUTA, headers=cuenta.headers)

        # Assert
        assert respuesta.status_code == 200
        assert respuesta.headers["content-type"].startswith("text/csv")
