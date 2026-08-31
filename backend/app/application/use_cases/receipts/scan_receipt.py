"""Caso de uso: leer un ticket y proponer un movimiento."""

from __future__ import annotations

import logging
import time
import unicodedata
from collections.abc import Sequence
from datetime import timedelta

from app.application.dtos import ReceiptDraft
from app.application.exceptions import (
    AssistantUnavailableError,
    RateLimitExceededError,
    ReceiptUnreadableError,
    UnsupportedFileTypeError,
)
from app.application.ports import (
    CategoryRepository,
    Clock,
    ReceiptReader,
    ReceiptScanRepository,
)
from app.domain.entities import Category
from app.domain.enums import TransactionType

logger = logging.getLogger(__name__)

TIPOS_ACEPTADOS = frozenset({"image/jpeg", "image/png", "image/webp"})
BYTES_POR_MB = 1024 * 1024


def _normalizar(texto: str) -> str:
    """Minúsculas y sin acentos, para comparar nombres de categoría.

    El modelo puede devolver "alimentacion" donde la categoría se llama
    "Alimentación". Sin normalizar, esa coincidencia obvia se pierde y el
    borrador sale sin categoría.
    """
    descompuesto = unicodedata.normalize("NFKD", texto.strip().casefold())
    return "".join(caracter for caracter in descompuesto if not unicodedata.combining(caracter))


class ScanReceipt:
    """Convierte la foto de un ticket en un borrador para confirmar.

    **No crea el movimiento.** Devuelve datos para precargar el formulario, y
    la creación sigue pasando por el alta de siempre. Un lector que escribe
    montos mal leídos en silencio deja el error en el historial, contamina los
    reportes y el presupuesto, y nadie se entera hasta que las cuentas no
    cierran (docs/PROMPT.md §21.1).
    """

    def __init__(
        self,
        reader: ReceiptReader,
        scans: ReceiptScanRepository,
        categories: CategoryRepository,
        clock: Clock,
        default_currency: str,
        max_size_mb: int,
        rate_limit_per_hour: int,
        model: str,
    ) -> None:
        self._reader = reader
        self._scans = scans
        self._categories = categories
        self._clock = clock
        self._default_currency = default_currency
        self._max_size_mb = max_size_mb
        self._rate_limit_per_hour = rate_limit_per_hour
        self._model = model

    async def execute(self, user_id: int, image: bytes, mime_type: str) -> ReceiptDraft:
        self._validar_archivo(image, mime_type)
        await self._verificar_cupo(user_id)

        # Solo las de gasto: un ticket es un comprobante de algo que se pagó.
        # Ofrecerle al modelo las de ingreso solo agrega ruido y chances de que
        # elija mal.
        categorias = [
            categoria
            for categoria in await self._categories.list_for_user(user_id)
            if categoria.type is TransactionType.EXPENSE
        ]

        comenzo = time.perf_counter()
        try:
            extraido = await self._reader.read(image, mime_type, categorias)
        except (ReceiptUnreadableError, AssistantUnavailableError):
            # El fallo se registra igual y se vuelve a lanzar: el repositorio
            # lo persiste en su propia transacción, porque la de este request
            # está por revertirse.
            await self._scans.save_failure(
                user_id, self._model, int((time.perf_counter() - comenzo) * 1000)
            )
            raise

        latencia_ms = int((time.perf_counter() - comenzo) * 1000)
        categoria = self._resolver_categoria(extraido.category_name, categorias)

        # Si el ticket no trae fecha legible, se propone hoy resuelto con el
        # `Clock`. Nunca una fecha inventada por el modelo.
        fecha = extraido.occurred_on or self._clock.today()

        scan_id = await self._scans.save(
            user_id=user_id,
            extracted=extraido,
            category_id=categoria.id if categoria else None,
            model=self._model,
            total_tokens=0,
            latency_ms=latencia_ms,
        )

        duplicados: list[int] = []
        if extraido.amount is not None:
            duplicados = await self._scans.find_possible_duplicates(
                user_id, extraido.amount, fecha, self._default_currency
            )

        logger.info(
            "Ticket leído",
            extra={
                "user_id": user_id,
                "scan_id": scan_id,
                "latency_ms": latencia_ms,
                "con_monto": extraido.amount is not None,
                "con_categoria": categoria is not None,
                "duplicados": len(duplicados),
            },
        )

        return ReceiptDraft(
            scan_id=scan_id,
            amount=extraido.amount,
            occurred_on=fecha,
            merchant=extraido.merchant,
            currency=self._default_currency,
            category_id=categoria.id if categoria else None,
            category_name=categoria.name if categoria else None,
            confidence=dict(extraido.confidence),
            possible_duplicates=duplicados,
        )

    def _validar_archivo(self, image: bytes, mime_type: str) -> None:
        if mime_type not in TIPOS_ACEPTADOS:
            aceptados = ", ".join(sorted(TIPOS_ACEPTADOS))
            raise UnsupportedFileTypeError(
                f"El archivo tiene que ser una imagen ({aceptados}). Se recibió {mime_type}."
            )
        if not image:
            raise UnsupportedFileTypeError("El archivo está vacío.")
        if len(image) > self._max_size_mb * BYTES_POR_MB:
            raise UnsupportedFileTypeError(
                f"La imagen no puede superar los {self._max_size_mb} MB."
            )

    async def _verificar_cupo(self, user_id: int) -> None:
        desde = self._clock.now() - timedelta(hours=1)
        usadas = await self._scans.count_since(user_id, desde)
        if usadas >= self._rate_limit_per_hour:
            raise RateLimitExceededError(
                f"Llegaste al límite de {self._rate_limit_per_hour} lecturas por hora. "
                "Podés cargar el gasto a mano mientras tanto."
            )

    @staticmethod
    def _resolver_categoria(nombre: str | None, categorias: Sequence[Category]) -> Category | None:
        """Busca la categoría propuesta entre las del usuario.

        Si el modelo devuelve una que no existe, **se descarta**: el borrador
        sale sin categoría y la persona la elige. Crear categorías desde acá
        llenaría la lista de variantes inventadas por el modelo.
        """
        if not nombre:
            return None
        buscado = _normalizar(nombre)
        return next(
            (categoria for categoria in categorias if _normalizar(categoria.name) == buscado),
            None,
        )
