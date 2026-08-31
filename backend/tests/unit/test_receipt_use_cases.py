"""Tests del caso de uso de lectura de tickets.

El modelo de visión va **mockeado**: se prueba que el borrador se arma bien y
que la categoría sale de las del usuario, no que el modelo lea bien
(docs/PROMPT.md §14 y §21.1).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.application.dtos import ExtractedReceipt
from app.application.exceptions import (
    AssistantUnavailableError,
    RateLimitExceededError,
    ReceiptUnreadableError,
    UnsupportedFileTypeError,
)
from app.application.use_cases.receipts import ScanReceipt
from app.domain.entities import Category
from app.domain.enums import ReceiptScanStatus, TransactionType
from tests.fakes import FakeCategoryRepository, FakeReceiptScanRepository, FixedClock

MONEDA = "ARS"
AHORA = datetime(2026, 8, 5, 12, 0, 0)
HOY = date(2026, 8, 5)
USUARIO = 1

IMAGEN = b"\xff\xd8\xff" + b"x" * 500
JPEG = "image/jpeg"


class LectorFalso:
    """Devuelve lo que se le cargue, o levanta lo que se le cargue."""

    def __init__(
        self, resultado: ExtractedReceipt | None = None, error: Exception | None = None
    ) -> None:
        self.resultado = resultado or ExtractedReceipt(
            amount=Decimal("12345.67"),
            occurred_on=date(2026, 8, 3),
            merchant="Supermercado Día",
            category_name="Alimentación",
            confidence={"amount": 0.95, "occurred_on": 0.9},
        )
        self.error = error
        self.categorias_recibidas: list[Sequence[Category]] = []

    async def read(
        self, image: bytes, mime_type: str, categories: Sequence[Category]
    ) -> ExtractedReceipt:
        self.categorias_recibidas.append(list(categories))
        if self.error is not None:
            raise self.error
        return self.resultado


@pytest.fixture
def categorias() -> FakeCategoryRepository:
    repo = FakeCategoryRepository()
    repo.categorias.extend(
        [
            Category(id=1, user_id=USUARIO, name="Alimentación", type=TransactionType.EXPENSE),
            Category(id=2, user_id=USUARIO, name="Ocio", type=TransactionType.EXPENSE),
            Category(id=3, user_id=USUARIO, name="Sueldo", type=TransactionType.INCOME),
        ]
    )
    return repo


@pytest.fixture
def scans() -> FakeReceiptScanRepository:
    return FakeReceiptScanRepository()


def _caso(
    lector: LectorFalso,
    scans: FakeReceiptScanRepository,
    categorias: FakeCategoryRepository,
    *,
    max_size_mb: int = 8,
    rate_limit: int = 10,
) -> ScanReceipt:
    return ScanReceipt(
        reader=lector,
        scans=scans,
        categories=categorias,
        clock=FixedClock(AHORA),
        default_currency=MONEDA,
        max_size_mb=max_size_mb,
        rate_limit_per_hour=rate_limit,
        model="gpt-5-mini",
    )


class TestBorrador:
    async def test_arma_el_borrador_con_lo_leido(
        self, scans: FakeReceiptScanRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Act
        borrador = await _caso(LectorFalso(), scans, categorias).execute(USUARIO, IMAGEN, JPEG)

        # Assert
        assert borrador.amount == Decimal("12345.67")
        assert borrador.occurred_on == date(2026, 8, 3)
        assert borrador.merchant == "Supermercado Día"
        assert borrador.currency == MONEDA
        assert borrador.category_id == 1

    async def test_no_crea_ningun_movimiento(
        self, scans: FakeReceiptScanRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Act
        await _caso(LectorFalso(), scans, categorias).execute(USUARIO, IMAGEN, JPEG)

        # Assert: es la regla de oro de la feature. El borrador precarga el
        # formulario; la creación sigue pasando por el alta de siempre.
        assert scans.movimientos_creados == []

    async def test_sin_fecha_legible_propone_hoy(
        self, scans: FakeReceiptScanRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        lector = LectorFalso(
            ExtractedReceipt(amount=Decimal("500.00"), occurred_on=None, confidence={})
        )

        # Act
        borrador = await _caso(lector, scans, categorias).execute(USUARIO, IMAGEN, JPEG)

        # Assert: hoy sale del `Clock`, nunca de una fecha inventada por el
        # modelo.
        assert borrador.occurred_on == HOY

    async def test_marca_los_campos_de_confianza_baja(
        self, scans: FakeReceiptScanRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange: el papel estaba arrugado y el total podría ser otro.
        lector = LectorFalso(
            ExtractedReceipt(
                amount=Decimal("1230.00"),
                confidence={"amount": 0.35, "merchant": 0.99},
            )
        )

        # Act
        borrador = await _caso(lector, scans, categorias).execute(USUARIO, IMAGEN, JPEG)

        # Assert: esconder la duda es lo que hace que alguien confirme un monto
        # equivocado.
        assert borrador.campos_dudosos == ["amount"]

    async def test_avisa_de_un_posible_duplicado(
        self, scans: FakeReceiptScanRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange: ya hay un gasto del mismo monto y fecha.
        scans.duplicados = [77]

        # Act
        borrador = await _caso(LectorFalso(), scans, categorias).execute(USUARIO, IMAGEN, JPEG)

        # Assert: informa pero no bloquea. Pagar dos cafés iguales el mismo día
        # es normal; escanear dos veces el mismo ticket también.
        assert borrador.possible_duplicates == [77]


class TestCategoria:
    async def test_solo_le_ofrece_al_modelo_categorias_de_gasto(
        self, scans: FakeReceiptScanRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        lector = LectorFalso()

        # Act
        await _caso(lector, scans, categorias).execute(USUARIO, IMAGEN, JPEG)

        # Assert: un ticket es un comprobante de algo que se pagó; ofrecerle
        # las de ingreso solo agrega chances de que elija mal.
        ofrecidas = {categoria.name for categoria in lector.categorias_recibidas[0]}
        assert ofrecidas == {"Alimentación", "Ocio"}

    async def test_resuelve_la_categoria_sin_acentos_ni_mayusculas(
        self, scans: FakeReceiptScanRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange: el modelo devuelve "alimentacion" y la categoría se llama
        # "Alimentación".
        lector = LectorFalso(
            ExtractedReceipt(amount=Decimal("100.00"), category_name="alimentacion")
        )

        # Act
        borrador = await _caso(lector, scans, categorias).execute(USUARIO, IMAGEN, JPEG)

        # Assert
        assert borrador.category_id == 1
        assert borrador.category_name == "Alimentación"

    async def test_descarta_una_categoria_que_no_es_del_usuario(
        self, scans: FakeReceiptScanRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        lector = LectorFalso(ExtractedReceipt(amount=Decimal("100.00"), category_name="Mascotas"))

        # Act
        borrador = await _caso(lector, scans, categorias).execute(USUARIO, IMAGEN, JPEG)

        # Assert: el borrador sale sin categoría y la persona la elige. Crear
        # categorías desde acá llenaría la lista de variantes del modelo.
        assert borrador.category_id is None
        assert borrador.category_name is None

    async def test_una_categoria_de_ingreso_no_se_resuelve(
        self, scans: FakeReceiptScanRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        lector = LectorFalso(ExtractedReceipt(amount=Decimal("100.00"), category_name="Sueldo"))

        # Act
        borrador = await _caso(lector, scans, categorias).execute(USUARIO, IMAGEN, JPEG)

        # Assert
        assert borrador.category_id is None


class TestValidaciones:
    @pytest.mark.parametrize("tipo", ["application/pdf", "text/plain", "", "image/gif"])
    async def test_rechaza_un_formato_no_aceptado(
        self, scans: FakeReceiptScanRepository, categorias: FakeCategoryRepository, tipo: str
    ) -> None:
        # Act / Assert
        with pytest.raises(UnsupportedFileTypeError):
            await _caso(LectorFalso(), scans, categorias).execute(USUARIO, IMAGEN, tipo)

    async def test_rechaza_un_archivo_vacio(
        self, scans: FakeReceiptScanRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Act / Assert
        with pytest.raises(UnsupportedFileTypeError, match="vacío"):
            await _caso(LectorFalso(), scans, categorias).execute(USUARIO, b"", JPEG)

    async def test_rechaza_una_imagen_demasiado_grande(
        self, scans: FakeReceiptScanRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange: 2 MB con el tope en 1.
        grande = b"x" * (2 * 1024 * 1024)

        # Act / Assert
        with pytest.raises(UnsupportedFileTypeError, match="1 MB"):
            await _caso(LectorFalso(), scans, categorias, max_size_mb=1).execute(
                USUARIO, grande, JPEG
            )

    async def test_no_llama_al_modelo_si_el_archivo_no_sirve(
        self, scans: FakeReceiptScanRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        lector = LectorFalso()

        # Act
        with pytest.raises(UnsupportedFileTypeError):
            await _caso(lector, scans, categorias).execute(USUARIO, IMAGEN, "application/pdf")

        # Assert: validar antes de llamar evita pagarle al proveedor por un
        # archivo que ya sabíamos que no servía.
        assert lector.categorias_recibidas == []


class TestFallos:
    async def test_propaga_el_ticket_ilegible(
        self, scans: FakeReceiptScanRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        lector = LectorFalso(error=ReceiptUnreadableError("No se lee."))

        # Act / Assert
        with pytest.raises(ReceiptUnreadableError):
            await _caso(lector, scans, categorias).execute(USUARIO, IMAGEN, JPEG)

    async def test_propaga_la_caida_del_proveedor(
        self, scans: FakeReceiptScanRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        lector = LectorFalso(error=AssistantUnavailableError("OpenAI caído."))

        # Act / Assert: nunca un borrador con ceros. Un monto en cero que
        # parece leído es peor que un error explícito.
        with pytest.raises(AssistantUnavailableError):
            await _caso(lector, scans, categorias).execute(USUARIO, IMAGEN, JPEG)

    async def test_un_intento_fallido_queda_registrado(
        self, scans: FakeReceiptScanRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        lector = LectorFalso(error=ReceiptUnreadableError("No se lee."))

        # Act
        with pytest.raises(ReceiptUnreadableError):
            await _caso(lector, scans, categorias).execute(USUARIO, IMAGEN, JPEG)

        # Assert: cuenta para el cupo igual que uno exitoso. Si no, un archivo
        # ilegible permitiría reintentar sin techo contra un proveedor que
        # cobra por llamada.
        assert len(scans.lecturas) == 1
        assert scans.lecturas[0].status is ReceiptScanStatus.FAILED


class TestCupo:
    async def test_corta_al_llegar_al_limite_por_hora(
        self, scans: FakeReceiptScanRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        caso = _caso(LectorFalso(), scans, categorias, rate_limit=2)
        await caso.execute(USUARIO, IMAGEN, JPEG)
        await caso.execute(USUARIO, IMAGEN, JPEG)

        # Act / Assert
        with pytest.raises(RateLimitExceededError):
            await caso.execute(USUARIO, IMAGEN, JPEG)

    async def test_el_cupo_es_por_usuario(
        self, scans: FakeReceiptScanRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        caso = _caso(LectorFalso(), scans, categorias, rate_limit=1)
        await caso.execute(USUARIO, IMAGEN, JPEG)

        # Act
        borrador = await caso.execute(2, IMAGEN, JPEG)

        # Assert
        assert borrador.amount == Decimal("12345.67")

    async def test_solo_cuentan_las_lecturas_de_la_ultima_hora(
        self, scans: FakeReceiptScanRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange: una lectura de hace dos horas no ocupa cupo.
        scans.ahora = AHORA - timedelta(hours=2)
        await _caso(LectorFalso(), scans, categorias, rate_limit=1).execute(USUARIO, IMAGEN, JPEG)
        scans.ahora = AHORA

        # Act
        borrador = await _caso(LectorFalso(), scans, categorias, rate_limit=1).execute(
            USUARIO, IMAGEN, JPEG
        )

        # Assert
        assert borrador.amount == Decimal("12345.67")


class TestTelemetria:
    async def test_guarda_la_lectura_pero_nunca_la_imagen(
        self, scans: FakeReceiptScanRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Act
        await _caso(LectorFalso(), scans, categorias).execute(USUARIO, IMAGEN, JPEG)

        # Assert: el repositorio no recibe los bytes en ningún momento. La foto
        # puede traer datos de una tarjeta y el producto no la necesita.
        assert len(scans.lecturas) == 1
        guardada = scans.lecturas[0]
        assert guardada.amount == Decimal("12345.67")
        assert guardada.model == "gpt-5-mini"
        assert not hasattr(guardada, "image")
