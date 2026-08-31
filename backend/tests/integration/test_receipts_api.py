"""Tests de extremo a extremo de la lectura de tickets, con el modelo mockeado.

Lo que se prueba es el endpoint —contrato, validaciones, aislamiento y que **no
cree movimientos**—, no que el modelo lea bien (docs/PROMPT.md §14 y §21.1).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from datetime import date
from decimal import Decimal

import pytest
from fastapi import Depends
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_app_clock,
    get_category_repository,
    get_receipt_scan_repository,
    get_scan_receipt,
)
from app.application.dtos import ExtractedReceipt
from app.application.exceptions import AssistantUnavailableError, ReceiptUnreadableError
from app.application.ports import CategoryRepository, Clock, ReceiptScanRepository
from app.application.use_cases.receipts import ScanReceipt
from app.core.config import get_settings
from app.domain.entities import Category
from app.infrastructure.db.models import ReceiptScanModel
from app.main import app
from tests.helpers import CuentaDePrueba, crear_cuenta

pytestmark = pytest.mark.integration

RUTA = "/api/v1/receipts/scan"
TRANSACCIONES = "/api/v1/transactions"

# Bytes cualesquiera: el lector va mockeado y nunca los mira.
IMAGEN = b"\xff\xd8\xff" + b"x" * 200


class LectorDoble:
    def __init__(self) -> None:
        self.resultado = ExtractedReceipt(
            amount=Decimal("12345.67"),
            occurred_on=date(2026, 8, 3),
            merchant="Supermercado Día",
            category_name="Alimentación",
            confidence={"amount": 0.95, "occurred_on": 0.4},
        )
        self.error: Exception | None = None
        self.veces_llamado = 0

    async def read(
        self, image: bytes, mime_type: str, categories: Sequence[Category]
    ) -> ExtractedReceipt:
        self.veces_llamado += 1
        if self.error is not None:
            raise self.error
        return self.resultado


@pytest.fixture(autouse=True)
def _base_limpia(db_session: AsyncSession) -> None:
    return None


@pytest.fixture
async def lector() -> AsyncIterator[LectorDoble]:
    """Reemplaza el lector real mientras dure el test.

    Sin esto la suite llamaría a OpenAI: además de costar plata, ataría los
    tests a la red y a lo que el modelo lea en cada corrida.

    Se sustituye el caso de uso entero y no solo el lector porque el puerto se
    inyecta adentro de `get_scan_receipt`. El resto de las dependencias —los
    repositorios, el reloj— siguen siendo las reales, así que lo que se prueba
    es el camino de producción con una sola pieza cambiada.
    """
    doble = LectorDoble()

    def construir(
        scans: ReceiptScanRepository = Depends(get_receipt_scan_repository),
        categories: CategoryRepository = Depends(get_category_repository),
        clock: Clock = Depends(get_app_clock),
    ) -> ScanReceipt:
        settings = get_settings()
        return ScanReceipt(
            reader=doble,
            scans=scans,
            categories=categories,
            clock=clock,
            default_currency=settings.default_currency,
            max_size_mb=settings.receipt_max_size_mb,
            rate_limit_per_hour=settings.receipt_rate_limit_per_hour,
            model="modelo-de-prueba",
        )

    app.dependency_overrides[get_scan_receipt] = construir
    yield doble
    app.dependency_overrides.pop(get_scan_receipt, None)


@pytest.fixture
async def cuenta(client: AsyncClient) -> CuentaDePrueba:
    return await crear_cuenta(client, "damian@ejemplo.com")


def _archivo(nombre: str = "ticket.jpg", tipo: str = "image/jpeg", datos: bytes = IMAGEN):
    return {"file": (nombre, datos, tipo)}


class TestBorrador:
    async def test_devuelve_el_borrador(
        self, client: AsyncClient, cuenta: CuentaDePrueba, lector: LectorDoble
    ) -> None:
        # Act
        respuesta = await client.post(RUTA, headers=cuenta.headers, files=_archivo())

        # Assert
        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo["amount"] == "12345.67"
        assert cuerpo["occurred_on"] == "2026-08-03"
        assert cuerpo["merchant"] == "Supermercado Día"
        assert cuerpo["currency"] == "ARS"

    async def test_no_crea_ningun_movimiento(
        self, client: AsyncClient, cuenta: CuentaDePrueba, lector: LectorDoble
    ) -> None:
        # Arrange
        antes = (await client.get(TRANSACCIONES, headers=cuenta.headers)).json()["totalCount"]

        # Act
        await client.post(RUTA, headers=cuenta.headers, files=_archivo())

        # Assert: la regla de oro. La confirmación pasa por `POST /transactions`.
        despues = (await client.get(TRANSACCIONES, headers=cuenta.headers)).json()["totalCount"]
        assert despues == antes == 0

    async def test_resuelve_la_categoria_del_usuario(
        self, client: AsyncClient, cuenta: CuentaDePrueba, lector: LectorDoble
    ) -> None:
        # Act
        cuerpo = (await client.post(RUTA, headers=cuenta.headers, files=_archivo())).json()

        # Assert: el id sale del catálogo del usuario, no del modelo.
        categorias = (await client.get("/api/v1/categories", headers=cuenta.headers)).json()
        alimentacion = next(c for c in categorias if c["name"] == "Alimentación")
        assert cuerpo["category_id"] == alimentacion["id"]
        assert cuerpo["category_name"] == "Alimentación"

    async def test_una_categoria_inventada_se_descarta(
        self, client: AsyncClient, cuenta: CuentaDePrueba, lector: LectorDoble
    ) -> None:
        # Arrange
        lector.resultado = ExtractedReceipt(amount=Decimal("100.00"), category_name="Criptomonedas")

        # Act
        cuerpo = (await client.post(RUTA, headers=cuenta.headers, files=_archivo())).json()

        # Assert
        assert cuerpo["category_id"] is None

    async def test_informa_los_campos_dudosos(
        self, client: AsyncClient, cuenta: CuentaDePrueba, lector: LectorDoble
    ) -> None:
        # Act
        cuerpo = (await client.post(RUTA, headers=cuenta.headers, files=_archivo())).json()

        # Assert: la fecha vino con 0.4 de confianza.
        assert cuerpo["low_confidence_fields"] == ["occurred_on"]
        assert cuerpo["confidence"]["amount"] == 0.95

    async def test_avisa_de_un_movimiento_igual_ya_cargado(
        self, client: AsyncClient, cuenta: CuentaDePrueba, lector: LectorDoble
    ) -> None:
        # Arrange: ya existe el mismo gasto, mismo monto y misma fecha.
        categorias = (await client.get("/api/v1/categories", headers=cuenta.headers)).json()
        alimentacion = next(c for c in categorias if c["name"] == "Alimentación")
        creado = await client.post(
            TRANSACCIONES,
            headers=cuenta.headers,
            json={
                "type": "EXPENSE",
                "amount": "12345.67",
                "occurred_on": "2026-08-03",
                "category_id": alimentacion["id"],
            },
        )

        # Act
        cuerpo = (await client.post(RUTA, headers=cuenta.headers, files=_archivo())).json()

        # Assert: avisa, no bloquea.
        assert cuerpo["possible_duplicates"] == [creado.json()["id"]]


class TestValidaciones:
    async def test_rechaza_un_pdf(
        self, client: AsyncClient, cuenta: CuentaDePrueba, lector: LectorDoble
    ) -> None:
        # Act
        respuesta = await client.post(
            RUTA, headers=cuenta.headers, files=_archivo("x.pdf", "application/pdf")
        )

        # Assert
        assert respuesta.status_code == 422
        assert respuesta.json()["code"] == "unsupported_file_type"

    async def test_no_llama_al_modelo_si_el_archivo_no_sirve(
        self, client: AsyncClient, cuenta: CuentaDePrueba, lector: LectorDoble
    ) -> None:
        # Act
        await client.post(RUTA, headers=cuenta.headers, files=_archivo("x.pdf", "application/pdf"))

        # Assert: validar antes de llamar evita pagarle al proveedor por un
        # archivo que ya sabíamos que no servía.
        assert lector.veces_llamado == 0

    async def test_sin_token_responde_401(self, client: AsyncClient, lector: LectorDoble) -> None:
        # Act
        respuesta = await client.post(RUTA, files=_archivo())

        # Assert
        assert respuesta.status_code == 401


class TestFallos:
    async def test_un_ticket_ilegible_da_422(
        self, client: AsyncClient, cuenta: CuentaDePrueba, lector: LectorDoble
    ) -> None:
        # Arrange
        lector.error = ReceiptUnreadableError("No se lee.")

        # Act
        respuesta = await client.post(RUTA, headers=cuenta.headers, files=_archivo())

        # Assert
        assert respuesta.status_code == 422
        assert respuesta.json()["code"] == "receipt_unreadable"

    async def test_el_proveedor_caido_da_503(
        self, client: AsyncClient, cuenta: CuentaDePrueba, lector: LectorDoble
    ) -> None:
        # Arrange
        lector.error = AssistantUnavailableError("OpenAI caído.")

        # Act
        respuesta = await client.post(RUTA, headers=cuenta.headers, files=_archivo())

        # Assert: nunca un borrador con ceros disfrazado de lectura.
        assert respuesta.status_code == 503
        assert respuesta.json()["code"] == "assistant_unavailable"


class TestTelemetria:
    async def test_persiste_la_lectura_sin_la_imagen(
        self,
        client: AsyncClient,
        cuenta: CuentaDePrueba,
        lector: LectorDoble,
        db_session: AsyncSession,
    ) -> None:
        # Act
        await client.post(RUTA, headers=cuenta.headers, files=_archivo())

        # Assert
        fila = (
            await db_session.scalars(
                select(ReceiptScanModel).where(ReceiptScanModel.user_id == cuenta.user_id)
            )
        ).one()
        assert fila.amount == Decimal("12345.67")
        assert fila.model == "modelo-de-prueba"
        # La tabla no tiene dónde guardar la imagen, y es a propósito.
        assert not hasattr(fila, "image")
        assert "image" not in ReceiptScanModel.__table__.columns

    async def test_un_intento_fallido_tambien_queda_registrado(
        self,
        client: AsyncClient,
        cuenta: CuentaDePrueba,
        lector: LectorDoble,
        db_session: AsyncSession,
    ) -> None:
        # Arrange
        lector.error = ReceiptUnreadableError("No se lee.")

        # Act
        await client.post(RUTA, headers=cuenta.headers, files=_archivo())

        # Assert: cuenta para el cupo igual que una lectura exitosa.
        total = await db_session.scalar(
            select(func.count())
            .select_from(ReceiptScanModel)
            .where(ReceiptScanModel.user_id == cuenta.user_id)
        )
        assert total == 1


class TestAislamiento:
    async def test_no_avisa_de_duplicados_de_otro_usuario(
        self, client: AsyncClient, cuenta: CuentaDePrueba, lector: LectorDoble
    ) -> None:
        # Arrange: el gasto igual lo tiene OTRA persona.
        ajena = await crear_cuenta(client, "otra@ejemplo.com")
        categorias = (await client.get("/api/v1/categories", headers=ajena.headers)).json()
        alimentacion = next(c for c in categorias if c["name"] == "Alimentación")
        await client.post(
            TRANSACCIONES,
            headers=ajena.headers,
            json={
                "type": "EXPENSE",
                "amount": "12345.67",
                "occurred_on": "2026-08-03",
                "category_id": alimentacion["id"],
            },
        )

        # Act
        cuerpo = (await client.post(RUTA, headers=cuenta.headers, files=_archivo())).json()

        # Assert: filtrar por `user_id` también acá. Sin eso, el aviso de
        # duplicado delataría que otra persona cargó ese mismo gasto.
        assert cuerpo["possible_duplicates"] == []
