"""Tests de extremo a extremo del ABM de categorías."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.default_categories import CATEGORIAS_POR_DEFECTO
from app.domain.enums import TransactionType
from app.infrastructure.db.models import BudgetModel, TransactionModel
from tests.helpers import CuentaDePrueba, crear_cuenta

pytestmark = pytest.mark.integration

RUTA = "/api/v1/categories"

CANTIDAD_INGRESOS_POR_DEFECTO = sum(
    1 for c in CATEGORIAS_POR_DEFECTO if c.type is TransactionType.INCOME
)


@pytest.fixture(autouse=True)
def _base_limpia(db_session: AsyncSession) -> None:
    return None


@pytest.fixture
async def cuenta(client: AsyncClient) -> CuentaDePrueba:
    return await crear_cuenta(client, "damian@ejemplo.com")


async def _id_de(client: AsyncClient, cuenta: CuentaDePrueba, nombre: str) -> int:
    listado = (await client.get(RUTA, headers=cuenta.headers)).json()
    return next(c["id"] for c in listado if c["name"] == nombre)


class TestListar:
    async def test_devuelve_las_categorias_sembradas(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange / Act
        respuesta = await client.get(RUTA, headers=cuenta.headers)

        # Assert
        assert respuesta.status_code == 200
        assert len(respuesta.json()) == len(CATEGORIAS_POR_DEFECTO)

    async def test_devuelve_una_lista_plana_sin_paginar(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        """La colección está acotada por usuario y el front la necesita entera."""
        # Arrange / Act
        cuerpo = (await client.get(RUTA, headers=cuenta.headers)).json()

        # Assert
        assert isinstance(cuerpo, list)

    async def test_filtra_por_tipo(self, client: AsyncClient, cuenta: CuentaDePrueba) -> None:
        # Arrange / Act
        respuesta = await client.get(f"{RUTA}?type=INCOME", headers=cuenta.headers)

        # Assert
        cuerpo = respuesta.json()
        assert len(cuerpo) == CANTIDAD_INGRESOS_POR_DEFECTO
        assert all(c["type"] == "INCOME" for c in cuerpo)

    async def test_los_ingresos_van_antes_que_los_gastos(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        """Es como se lee un resumen financiero, y es explícito en el ORDER BY."""
        # Arrange / Act
        tipos = [c["type"] for c in (await client.get(RUTA, headers=cuenta.headers)).json()]

        # Assert
        assert tipos == sorted(tipos, key=lambda t: 0 if t == "INCOME" else 1)

    async def test_el_orden_no_cambia_entre_requests(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        """Lo que importa del orden es que sea estable, no cuál es.

        No se compara contra el `sorted` de Python a propósito: la collation
        de MySQL es insensible a acentos y "Ñandú" iría antes que "Ocio",
        mientras que Python ordena por punto de código y lo pondría después.
        """
        # Arrange / Act
        primera = [c["id"] for c in (await client.get(RUTA, headers=cuenta.headers)).json()]
        segunda = [c["id"] for c in (await client.get(RUTA, headers=cuenta.headers)).json()]

        # Assert
        assert primera == segunda
        assert len(primera) == len(CATEGORIAS_POR_DEFECTO)

    async def test_sin_token_devuelve_401(self, client: AsyncClient) -> None:
        # Arrange / Act / Assert
        assert (await client.get(RUTA)).status_code == 401


class TestCrear:
    async def test_crea_y_devuelve_location(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange / Act
        respuesta = await client.post(
            RUTA,
            headers=cuenta.headers,
            json={"name": "Mascotas", "type": "EXPENSE", "color": "#aabbcc"},
        )

        # Assert
        assert respuesta.status_code == 201
        cuerpo = respuesta.json()
        assert cuerpo["name"] == "Mascotas"
        assert cuerpo["is_default"] is False
        assert respuesta.headers["Location"] == f"{RUTA}/{cuerpo['id']}"

    async def test_la_categoria_creada_aparece_en_el_listado(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await client.post(
            RUTA, headers=cuenta.headers, json={"name": "Mascotas", "type": "EXPENSE"}
        )

        # Act
        cuerpo = (await client.get(RUTA, headers=cuenta.headers)).json()

        # Assert
        assert len(cuerpo) == len(CATEGORIAS_POR_DEFECTO) + 1

    async def test_rechaza_un_nombre_duplicado(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange / Act
        respuesta = await client.post(
            RUTA, headers=cuenta.headers, json={"name": "Ocio", "type": "EXPENSE"}
        )

        # Assert
        assert respuesta.status_code == 409
        assert respuesta.json()["code"] == "duplicate_resource"
        assert "Ocio" in respuesta.json()["message"]

    async def test_permite_el_mismo_nombre_en_el_otro_tipo(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange / Act
        respuesta = await client.post(
            RUTA, headers=cuenta.headers, json={"name": "Ocio", "type": "INCOME"}
        )

        # Assert
        assert respuesta.status_code == 201

    @pytest.mark.parametrize(
        "payload",
        [
            {"name": "", "type": "EXPENSE"},
            {"name": "x" * 61, "type": "EXPENSE"},
            {"name": "Ok", "type": "OTRO"},
            {"name": "Ok", "type": "EXPENSE", "color": "rojo"},
            {"name": "Ok"},
        ],
    )
    async def test_rechaza_payloads_invalidos(
        self, client: AsyncClient, cuenta: CuentaDePrueba, payload: dict[str, str]
    ) -> None:
        # Arrange / Act
        respuesta = await client.post(RUTA, headers=cuenta.headers, json=payload)

        # Assert
        assert respuesta.status_code == 422


class TestEditar:
    async def test_cambia_el_nombre(self, client: AsyncClient, cuenta: CuentaDePrueba) -> None:
        # Arrange
        category_id = await _id_de(client, cuenta, "Ocio")

        # Act
        respuesta = await client.patch(
            f"{RUTA}/{category_id}", headers=cuenta.headers, json={"name": "Entretenimiento"}
        )

        # Assert
        assert respuesta.status_code == 200
        assert respuesta.json()["name"] == "Entretenimiento"

    async def test_rechaza_un_nombre_ya_usado(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        category_id = await _id_de(client, cuenta, "Ocio")

        # Act
        respuesta = await client.patch(
            f"{RUTA}/{category_id}", headers=cuenta.headers, json={"name": "Salud"}
        )

        # Assert
        assert respuesta.status_code == 409

    async def test_renombrarla_con_su_propio_nombre_no_choca(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        category_id = await _id_de(client, cuenta, "Ocio")

        # Act
        respuesta = await client.patch(
            f"{RUTA}/{category_id}", headers=cuenta.headers, json={"name": "Ocio"}
        )

        # Assert
        assert respuesta.status_code == 200

    async def test_no_acepta_cambiar_el_tipo(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        """Convertiría los movimientos históricos en lo contrario de lo registrado."""
        # Arrange
        category_id = await _id_de(client, cuenta, "Ocio")

        # Act
        respuesta = await client.patch(
            f"{RUTA}/{category_id}", headers=cuenta.headers, json={"type": "INCOME"}
        )

        # Assert
        assert respuesta.status_code == 422

    async def test_un_patch_vacio_es_un_error(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        category_id = await _id_de(client, cuenta, "Ocio")

        # Act
        respuesta = await client.patch(f"{RUTA}/{category_id}", headers=cuenta.headers, json={})

        # Assert
        assert respuesta.status_code == 422


class TestBorrar:
    async def test_borra_una_categoria_sin_uso(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        category_id = await _id_de(client, cuenta, "Ocio")

        # Act
        respuesta = await client.delete(f"{RUTA}/{category_id}", headers=cuenta.headers)

        # Assert
        assert respuesta.status_code == 204
        assert (
            await client.get(f"{RUTA}/{category_id}", headers=cuenta.headers)
        ).status_code == 404

    async def test_no_borra_una_categoria_con_movimientos(
        self, client: AsyncClient, cuenta: CuentaDePrueba, db_session: AsyncSession
    ) -> None:
        # Arrange
        category_id = await _id_de(client, cuenta, "Alimentación")
        db_session.add(
            TransactionModel(
                user_id=cuenta.user_id,
                category_id=category_id,
                type=TransactionType.EXPENSE,
                amount=Decimal("1500.00"),
                occurred_on=date(2026, 8, 5),
            )
        )
        await db_session.commit()

        # Act
        respuesta = await client.delete(f"{RUTA}/{category_id}", headers=cuenta.headers)

        # Assert
        assert respuesta.status_code == 409
        cuerpo = respuesta.json()
        assert cuerpo["code"] == "resource_in_use"
        assert "Alimentación" in cuerpo["message"]
        assert "1 movimiento" in cuerpo["message"]

    async def test_el_mensaje_enumera_todo_lo_que_bloquea(
        self, client: AsyncClient, cuenta: CuentaDePrueba, db_session: AsyncSession
    ) -> None:
        """Un 409 genérico obligaría a adivinar qué hay que borrar antes."""
        # Arrange
        category_id = await _id_de(client, cuenta, "Alimentación")
        db_session.add_all(
            [
                TransactionModel(
                    user_id=cuenta.user_id,
                    category_id=category_id,
                    type=TransactionType.EXPENSE,
                    amount=Decimal("100.00"),
                    occurred_on=date(2026, 8, 5),
                ),
                TransactionModel(
                    user_id=cuenta.user_id,
                    category_id=category_id,
                    type=TransactionType.EXPENSE,
                    amount=Decimal("200.00"),
                    occurred_on=date(2026, 8, 6),
                ),
                BudgetModel(
                    user_id=cuenta.user_id,
                    category_id=category_id,
                    period_month=date(2026, 8, 1),
                    amount=Decimal("50000.00"),
                ),
            ]
        )
        await db_session.commit()

        # Act
        mensaje = (await client.delete(f"{RUTA}/{category_id}", headers=cuenta.headers)).json()[
            "message"
        ]

        # Assert
        assert "2 movimientos" in mensaje
        assert "1 presupuesto" in mensaje


class TestAislamiento:
    @pytest.fixture
    async def otra_cuenta(self, client: AsyncClient) -> CuentaDePrueba:
        return await crear_cuenta(client, "otra@ejemplo.com")

    async def test_el_listado_no_incluye_las_ajenas(
        self, client: AsyncClient, cuenta: CuentaDePrueba, otra_cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await client.post(
            RUTA, headers=otra_cuenta.headers, json={"name": "Secreta", "type": "EXPENSE"}
        )

        # Act
        cuerpo = (await client.get(RUTA, headers=cuenta.headers)).json()

        # Assert
        assert "Secreta" not in [c["name"] for c in cuerpo]

    async def test_no_se_puede_leer_una_ajena(
        self, client: AsyncClient, cuenta: CuentaDePrueba, otra_cuenta: CuentaDePrueba
    ) -> None:
        """404 y no 403: un 403 confirmaría que ese id existe."""
        # Arrange
        ajena = await _id_de(client, otra_cuenta, "Ocio")

        # Act
        respuesta = await client.get(f"{RUTA}/{ajena}", headers=cuenta.headers)

        # Assert
        assert respuesta.status_code == 404

    async def test_no_se_puede_editar_una_ajena(
        self, client: AsyncClient, cuenta: CuentaDePrueba, otra_cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        ajena = await _id_de(client, otra_cuenta, "Ocio")

        # Act
        respuesta = await client.patch(
            f"{RUTA}/{ajena}", headers=cuenta.headers, json={"name": "Robada"}
        )

        # Assert
        assert respuesta.status_code == 404
        sigue = (await client.get(f"{RUTA}/{ajena}", headers=otra_cuenta.headers)).json()
        assert sigue["name"] == "Ocio"

    async def test_no_se_puede_borrar_una_ajena(
        self, client: AsyncClient, cuenta: CuentaDePrueba, otra_cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        ajena = await _id_de(client, otra_cuenta, "Ocio")

        # Act
        respuesta = await client.delete(f"{RUTA}/{ajena}", headers=cuenta.headers)

        # Assert
        assert respuesta.status_code == 404
        assert (await client.get(f"{RUTA}/{ajena}", headers=otra_cuenta.headers)).status_code == 200

    async def test_dos_usuarios_pueden_tener_la_misma_categoria(
        self, client: AsyncClient, cuenta: CuentaDePrueba, otra_cuenta: CuentaDePrueba
    ) -> None:
        """La unicidad es por usuario, no global."""
        # Arrange / Act
        primera = await client.post(
            RUTA, headers=cuenta.headers, json={"name": "Mascotas", "type": "EXPENSE"}
        )
        segunda = await client.post(
            RUTA, headers=otra_cuenta.headers, json={"name": "Mascotas", "type": "EXPENSE"}
        )

        # Assert
        assert primera.status_code == 201
        assert segunda.status_code == 201
        assert primera.json()["id"] != segunda.json()["id"]
