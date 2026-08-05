"""Tests de extremo a extremo del CRUD de movimientos.

Acá viven las pruebas de filtros, orden y paginación: son responsabilidad del
repositorio y del SQL que genera, así que solo valen contra MySQL real.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import OccurrenceStatus, RecurrenceFrequency, TransactionType
from app.infrastructure.db.models import (
    RecurringOccurrenceModel,
    RecurringRuleModel,
    TransactionModel,
)
from tests.helpers import CuentaDePrueba, crear_cuenta

pytestmark = pytest.mark.integration

RUTA = "/api/v1/transactions"
CATEGORIAS = "/api/v1/categories"


@pytest.fixture(autouse=True)
def _base_limpia(db_session: AsyncSession) -> None:
    return None


@pytest.fixture
async def cuenta(client: AsyncClient) -> CuentaDePrueba:
    return await crear_cuenta(client, "damian@ejemplo.com")


async def _categoria_id(
    client: AsyncClient, cuenta: CuentaDePrueba, nombre: str = "Alimentación"
) -> int:
    listado = (await client.get(CATEGORIAS, headers=cuenta.headers)).json()
    return next(c["id"] for c in listado if c["name"] == nombre)


async def _crear(
    client: AsyncClient,
    cuenta: CuentaDePrueba,
    category_id: int,
    monto: Any = "100.00",
    dia: str = "2026-08-05",
    tipo: str = "EXPENSE",
    descripcion: str = "",
) -> Any:
    return await client.post(
        RUTA,
        headers=cuenta.headers,
        json={
            "type": tipo,
            "amount": monto,
            "occurred_on": dia,
            "category_id": category_id,
            "description": descripcion,
        },
    )


# ---------------------------------------------------------------------------
# Alta
# ---------------------------------------------------------------------------
class TestCrear:
    async def test_registra_un_gasto(self, client: AsyncClient, cuenta: CuentaDePrueba) -> None:
        # Arrange
        category_id = await _categoria_id(client, cuenta)

        # Act
        respuesta = await _crear(client, cuenta, category_id, "1234.56", descripcion="Super")

        # Assert
        assert respuesta.status_code == 201, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo["amount"] == "1234.56"
        assert cuerpo["currency"] == "ARS"
        assert cuerpo["is_recurring"] is False
        assert respuesta.headers["Location"] == f"{RUTA}/{cuerpo['id']}"

    async def test_el_monto_viaja_como_string(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        """Un número JSON lo parsea el cliente como float y pierde exactitud."""
        # Arrange
        category_id = await _categoria_id(client, cuenta)

        # Act
        respuesta = await _crear(client, cuenta, category_id, "1234.56")

        # Assert
        assert '"amount":"1234.56"' in respuesta.text.replace(" ", "")

    @pytest.mark.parametrize("monto", ["0.01", "99999999999.99", "1234.56", "1000"])
    async def test_los_montos_vuelven_exactos(
        self, client: AsyncClient, cuenta: CuentaDePrueba, monto: str
    ) -> None:
        # Arrange
        category_id = await _categoria_id(client, cuenta)

        # Act
        creado = (await _crear(client, cuenta, category_id, monto)).json()
        leido = (await client.get(f"{RUTA}/{creado['id']}", headers=cuenta.headers)).json()

        # Assert
        assert Decimal(leido["amount"]) == Decimal(monto)

    async def test_acepta_el_monto_como_numero_sin_perder_precision(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        """Pydantic parsea el decimal desde el texto del JSON, sin pasar por float."""
        # Arrange
        category_id = await _categoria_id(client, cuenta)

        # Act
        respuesta = await _crear(client, cuenta, category_id, 1234.56)

        # Assert
        assert respuesta.status_code == 201, respuesta.text
        assert Decimal(respuesta.json()["amount"]) == Decimal("1234.56")

    @pytest.mark.parametrize("monto", ["0", "-100", "10.005", "0.001"])
    async def test_rechaza_montos_invalidos(
        self, client: AsyncClient, cuenta: CuentaDePrueba, monto: str
    ) -> None:
        # Arrange
        category_id = await _categoria_id(client, cuenta)

        # Act
        respuesta = await _crear(client, cuenta, category_id, monto)

        # Assert
        assert respuesta.status_code == 422

    async def test_rechaza_una_categoria_del_tipo_equivocado(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        de_ingreso = await _categoria_id(client, cuenta, "Sueldo")

        # Act
        respuesta = await _crear(client, cuenta, de_ingreso, tipo="EXPENSE")

        # Assert
        assert respuesta.status_code == 422
        assert respuesta.json()["code"] == "invalid_reference"

    async def test_rechaza_una_moneda_no_habilitada(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        category_id = await _categoria_id(client, cuenta)

        # Act
        respuesta = await client.post(
            RUTA,
            headers=cuenta.headers,
            json={
                "type": "EXPENSE",
                "amount": "100.00",
                "occurred_on": "2026-08-05",
                "category_id": category_id,
                "currency": "USD",
            },
        )

        # Assert
        assert respuesta.status_code == 422
        assert respuesta.json()["code"] == "unsupported_currency"


# ---------------------------------------------------------------------------
# Listado, filtros y orden
# ---------------------------------------------------------------------------
class TestListar:
    @pytest.fixture
    async def con_datos(self, client: AsyncClient, cuenta: CuentaDePrueba) -> dict[str, int]:
        alimentacion = await _categoria_id(client, cuenta, "Alimentación")
        ocio = await _categoria_id(client, cuenta, "Ocio")
        sueldo = await _categoria_id(client, cuenta, "Sueldo")
        await _crear(client, cuenta, alimentacion, "500.00", "2026-07-10", descripcion="Verdulería")
        await _crear(client, cuenta, alimentacion, "1500.00", "2026-08-01", descripcion="Super")
        await _crear(client, cuenta, ocio, "3000.00", "2026-08-15", descripcion="Cine")
        await _crear(client, cuenta, sueldo, "850000.00", "2026-08-01", tipo="INCOME")
        return {"alimentacion": alimentacion, "ocio": ocio, "sueldo": sueldo}

    async def test_devuelve_el_sobre_de_paginacion(
        self, client: AsyncClient, cuenta: CuentaDePrueba, con_datos: dict[str, int]
    ) -> None:
        # Arrange / Act
        cuerpo = (await client.get(RUTA, headers=cuenta.headers)).json()

        # Assert
        assert set(cuerpo) == {"entries", "offset", "limit", "totalCount"}
        assert cuerpo["totalCount"] == 4
        assert len(cuerpo["entries"]) == 4

    async def test_total_count_cuenta_los_filtrados_no_los_devueltos(
        self, client: AsyncClient, cuenta: CuentaDePrueba, con_datos: dict[str, int]
    ) -> None:
        """Sin esto el frontend no puede dibujar el paginador."""
        # Arrange / Act
        cuerpo = (await client.get(f"{RUTA}?limit=2", headers=cuenta.headers)).json()

        # Assert
        assert cuerpo["totalCount"] == 4
        assert len(cuerpo["entries"]) == 2

    async def test_filtra_por_rango_de_fechas(
        self, client: AsyncClient, cuenta: CuentaDePrueba, con_datos: dict[str, int]
    ) -> None:
        # Arrange / Act
        cuerpo = (
            await client.get(
                f"{RUTA}?date_from=2026-08-01&date_to=2026-08-01", headers=cuenta.headers
            )
        ).json()

        # Assert
        assert cuerpo["totalCount"] == 2

    async def test_filtra_por_categoria(
        self, client: AsyncClient, cuenta: CuentaDePrueba, con_datos: dict[str, int]
    ) -> None:
        # Arrange / Act
        cuerpo = (
            await client.get(
                f"{RUTA}?category_id={con_datos['alimentacion']}", headers=cuenta.headers
            )
        ).json()

        # Assert
        assert cuerpo["totalCount"] == 2

    async def test_filtra_por_tipo(
        self, client: AsyncClient, cuenta: CuentaDePrueba, con_datos: dict[str, int]
    ) -> None:
        # Arrange / Act
        cuerpo = (await client.get(f"{RUTA}?type=INCOME", headers=cuenta.headers)).json()

        # Assert
        assert cuerpo["totalCount"] == 1

    async def test_filtra_por_rango_de_monto(
        self, client: AsyncClient, cuenta: CuentaDePrueba, con_datos: dict[str, int]
    ) -> None:
        # Arrange / Act
        cuerpo = (
            await client.get(f"{RUTA}?min_amount=1000&max_amount=5000", headers=cuenta.headers)
        ).json()

        # Assert
        assert cuerpo["totalCount"] == 2

    async def test_busca_en_la_descripcion(
        self, client: AsyncClient, cuenta: CuentaDePrueba, con_datos: dict[str, int]
    ) -> None:
        # Arrange / Act
        cuerpo = (await client.get(f"{RUTA}?q=Super", headers=cuenta.headers)).json()

        # Assert
        assert cuerpo["totalCount"] == 1
        assert cuerpo["entries"][0]["description"] == "Super"

    async def test_el_comodin_de_like_no_devuelve_todo(
        self, client: AsyncClient, cuenta: CuentaDePrueba, con_datos: dict[str, int]
    ) -> None:
        """Sin autoescape, buscar "%" haría match con cualquier descripción."""
        # Arrange / Act
        cuerpo = (await client.get(f"{RUTA}?q=%25", headers=cuenta.headers)).json()

        # Assert
        assert cuerpo["totalCount"] == 0

    async def test_combina_varios_filtros(
        self, client: AsyncClient, cuenta: CuentaDePrueba, con_datos: dict[str, int]
    ) -> None:
        # Arrange / Act
        cuerpo = (
            await client.get(
                f"{RUTA}?type=EXPENSE&date_from=2026-08-01&min_amount=1000",
                headers=cuenta.headers,
            )
        ).json()

        # Assert
        assert cuerpo["totalCount"] == 2

    async def test_ordena_por_monto_ascendente(
        self, client: AsyncClient, cuenta: CuentaDePrueba, con_datos: dict[str, int]
    ) -> None:
        # Arrange / Act
        cuerpo = (await client.get(f"{RUTA}?sort=amount", headers=cuenta.headers)).json()

        # Assert
        montos = [Decimal(e["amount"]) for e in cuerpo["entries"]]
        assert montos == sorted(montos)

    async def test_ordena_por_monto_descendente(
        self, client: AsyncClient, cuenta: CuentaDePrueba, con_datos: dict[str, int]
    ) -> None:
        # Arrange / Act
        cuerpo = (await client.get(f"{RUTA}?sort=-amount", headers=cuenta.headers)).json()

        # Assert
        montos = [Decimal(e["amount"]) for e in cuerpo["entries"]]
        assert montos == sorted(montos, reverse=True)

    async def test_por_defecto_los_mas_recientes_primero(
        self, client: AsyncClient, cuenta: CuentaDePrueba, con_datos: dict[str, int]
    ) -> None:
        # Arrange / Act
        cuerpo = (await client.get(RUTA, headers=cuenta.headers)).json()

        # Assert
        fechas = [e["occurred_on"] for e in cuerpo["entries"]]
        assert fechas == sorted(fechas, reverse=True)

    async def test_rechaza_un_campo_de_orden_desconocido(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange / Act
        respuesta = await client.get(f"{RUTA}?sort=password_hash", headers=cuenta.headers)

        # Assert
        assert respuesta.status_code == 422

    async def test_rechaza_un_rango_de_fechas_invertido(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange / Act
        respuesta = await client.get(
            f"{RUTA}?date_from=2026-09-01&date_to=2026-08-01", headers=cuenta.headers
        )

        # Assert
        assert respuesta.status_code == 422

    async def test_rechaza_un_limit_fuera_de_rango(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange / Act / Assert
        assert (await client.get(f"{RUTA}?limit=101", headers=cuenta.headers)).status_code == 422
        assert (await client.get(f"{RUTA}?limit=0", headers=cuenta.headers)).status_code == 422


class TestPaginacion:
    async def test_recorrer_las_paginas_no_repite_ni_saltea(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        """Todos con la misma fecha: sin desempate por id el orden es arbitrario
        entre consultas y la paginación repetiría filas y se saltearía otras."""
        # Arrange
        category_id = await _categoria_id(client, cuenta)
        for _ in range(7):
            await _crear(client, cuenta, category_id, "100.00", "2026-08-05")

        # Act
        vistos: list[int] = []
        for offset in (0, 2, 4, 6):
            pagina = (
                await client.get(f"{RUTA}?offset={offset}&limit=2", headers=cuenta.headers)
            ).json()
            vistos.extend(e["id"] for e in pagina["entries"])

        # Assert
        assert len(vistos) == 7
        assert len(set(vistos)) == 7


# ---------------------------------------------------------------------------
# Edición y borrado
# ---------------------------------------------------------------------------
class TestEditar:
    async def test_cambia_el_monto(self, client: AsyncClient, cuenta: CuentaDePrueba) -> None:
        # Arrange
        category_id = await _categoria_id(client, cuenta)
        creado = (await _crear(client, cuenta, category_id, "100.00")).json()

        # Act
        respuesta = await client.patch(
            f"{RUTA}/{creado['id']}", headers=cuenta.headers, json={"amount": "250.75"}
        )

        # Assert
        assert respuesta.status_code == 200
        assert respuesta.json()["amount"] == "250.75"

    async def test_cambiar_el_tipo_exige_una_categoria_compatible(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        gasto = await _categoria_id(client, cuenta, "Alimentación")
        creado = (await _crear(client, cuenta, gasto)).json()

        # Act
        respuesta = await client.patch(
            f"{RUTA}/{creado['id']}", headers=cuenta.headers, json={"type": "INCOME"}
        )

        # Assert
        assert respuesta.status_code == 422

    async def test_cambiar_tipo_y_categoria_juntos_funciona(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        gasto = await _categoria_id(client, cuenta, "Alimentación")
        sueldo = await _categoria_id(client, cuenta, "Sueldo")
        creado = (await _crear(client, cuenta, gasto)).json()

        # Act
        respuesta = await client.patch(
            f"{RUTA}/{creado['id']}",
            headers=cuenta.headers,
            json={"type": "INCOME", "category_id": sueldo},
        )

        # Assert
        assert respuesta.status_code == 200
        assert respuesta.json()["type"] == "INCOME"

    async def test_no_acepta_cambiar_la_moneda(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        category_id = await _categoria_id(client, cuenta)
        creado = (await _crear(client, cuenta, category_id)).json()

        # Act
        respuesta = await client.patch(
            f"{RUTA}/{creado['id']}", headers=cuenta.headers, json={"currency": "USD"}
        )

        # Assert
        assert respuesta.status_code == 422

    async def test_un_patch_vacio_es_un_error(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        category_id = await _categoria_id(client, cuenta)
        creado = (await _crear(client, cuenta, category_id)).json()

        # Act / Assert
        assert (
            await client.patch(f"{RUTA}/{creado['id']}", headers=cuenta.headers, json={})
        ).status_code == 422


class TestBorrar:
    async def test_borra_el_movimiento(self, client: AsyncClient, cuenta: CuentaDePrueba) -> None:
        # Arrange
        category_id = await _categoria_id(client, cuenta)
        creado = (await _crear(client, cuenta, category_id)).json()

        # Act
        respuesta = await client.delete(f"{RUTA}/{creado['id']}", headers=cuenta.headers)

        # Assert
        assert respuesta.status_code == 204
        assert (
            await client.get(f"{RUTA}/{creado['id']}", headers=cuenta.headers)
        ).status_code == 404

    async def test_borrar_uno_recurrente_saltea_su_ocurrencia_sin_borrarla(
        self, client: AsyncClient, cuenta: CuentaDePrueba, db_session: AsyncSession
    ) -> None:
        """El bug más probable de toda la feature de recurrentes.

        Si la ocurrencia se borrara junto al movimiento, el job la volvería a
        generar y el gasto que la persona usuaria borró reaparecería al otro día.
        """
        # Arrange
        category_id = await _categoria_id(client, cuenta)
        regla = RecurringRuleModel(
            user_id=cuenta.user_id,
            category_id=category_id,
            type=TransactionType.EXPENSE,
            amount=Decimal("450000.00"),
            frequency=RecurrenceFrequency.MONTHLY,
            day_of_month=5,
            starts_on=date(2026, 1, 1),
        )
        db_session.add(regla)
        await db_session.flush()
        movimiento = TransactionModel(
            user_id=cuenta.user_id,
            category_id=category_id,
            type=TransactionType.EXPENSE,
            amount=Decimal("450000.00"),
            occurred_on=date(2026, 8, 5),
            recurring_rule_id=regla.id,
        )
        db_session.add(movimiento)
        await db_session.flush()
        db_session.add(
            RecurringOccurrenceModel(
                rule_id=regla.id,
                occurred_on=date(2026, 8, 5),
                status=OccurrenceStatus.GENERATED,
                transaction_id=movimiento.id,
            )
        )
        await db_session.commit()

        # Act
        respuesta = await client.delete(f"{RUTA}/{movimiento.id}", headers=cuenta.headers)

        # Assert
        assert respuesta.status_code == 204
        await db_session.rollback()
        ocurrencia = (
            await db_session.scalars(
                select(RecurringOccurrenceModel).where(RecurringOccurrenceModel.rule_id == regla.id)
            )
        ).one()
        assert ocurrencia.status is OccurrenceStatus.SKIPPED
        assert ocurrencia.transaction_id is None


# ---------------------------------------------------------------------------
# Aislamiento
# ---------------------------------------------------------------------------
class TestAislamiento:
    @pytest.fixture
    async def otra_cuenta(self, client: AsyncClient) -> CuentaDePrueba:
        return await crear_cuenta(client, "otra@ejemplo.com")

    async def test_el_listado_no_incluye_los_ajenos(
        self, client: AsyncClient, cuenta: CuentaDePrueba, otra_cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        ajena = await _categoria_id(client, otra_cuenta)
        await _crear(client, otra_cuenta, ajena, "999.00", descripcion="Secreto")

        # Act
        cuerpo = (await client.get(RUTA, headers=cuenta.headers)).json()

        # Assert
        assert cuerpo["totalCount"] == 0

    async def test_no_se_puede_leer_uno_ajeno(
        self, client: AsyncClient, cuenta: CuentaDePrueba, otra_cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        ajena = await _categoria_id(client, otra_cuenta)
        creado = (await _crear(client, otra_cuenta, ajena)).json()

        # Act / Assert
        assert (
            await client.get(f"{RUTA}/{creado['id']}", headers=cuenta.headers)
        ).status_code == 404

    async def test_no_se_puede_editar_ni_borrar_uno_ajeno(
        self, client: AsyncClient, cuenta: CuentaDePrueba, otra_cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        ajena = await _categoria_id(client, otra_cuenta)
        creado = (await _crear(client, otra_cuenta, ajena)).json()

        # Act
        edicion = await client.patch(
            f"{RUTA}/{creado['id']}", headers=cuenta.headers, json={"amount": "1.00"}
        )
        borrado = await client.delete(f"{RUTA}/{creado['id']}", headers=cuenta.headers)

        # Assert
        assert edicion.status_code == 404
        assert borrado.status_code == 404
        sigue = await client.get(f"{RUTA}/{creado['id']}", headers=otra_cuenta.headers)
        assert sigue.status_code == 200
        assert sigue.json()["amount"] == "100.00"

    async def test_no_se_puede_usar_una_categoria_ajena(
        self, client: AsyncClient, cuenta: CuentaDePrueba, otra_cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        ajena = await _categoria_id(client, otra_cuenta)

        # Act
        respuesta = await _crear(client, cuenta, ajena)

        # Assert
        assert respuesta.status_code == 422
        assert respuesta.json()["code"] == "invalid_reference"
