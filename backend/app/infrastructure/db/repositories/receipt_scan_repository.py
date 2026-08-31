"""Repositorio de lecturas de ticket sobre SQLAlchemy."""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos import ExtractedReceipt
from app.domain.enums import ReceiptScanStatus, TransactionType
from app.infrastructure.clock import a_utc_naive
from app.infrastructure.db.models import ReceiptScanModel, TransactionModel
from app.infrastructure.db.session import session_scope

logger = logging.getLogger(__name__)


class SqlAlchemyReceiptScanRepository:
    """Implementación del puerto `ReceiptScanRepository`.

    No hay ninguna columna para la imagen: ver el modelo y §21.1.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(
        self,
        user_id: int,
        extracted: ExtractedReceipt,
        category_id: int | None,
        model: str,
        total_tokens: int,
        latency_ms: int,
    ) -> int:
        fila = ReceiptScanModel(
            user_id=user_id,
            status=ReceiptScanStatus.EXTRACTED,
            amount=extracted.amount,
            occurred_on=extracted.occurred_on,
            merchant=extracted.merchant,
            category_id=category_id,
            confidence=extracted.confidence or None,
            model=model,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
        )
        self._session.add(fila)
        await self._session.flush()
        return fila.id

    async def save_failure(self, user_id: int, model: str, latency_ms: int) -> None:
        """Sesión propia y commit propio: ver el porqué en el puerto.

        Un fallo al registrar el fallo no puede tapar el error original —que es
        lo que la persona necesita ver—, así que se loguea y se sigue.
        """
        try:
            async with session_scope() as sesion_aparte:
                sesion_aparte.add(
                    ReceiptScanModel(
                        user_id=user_id,
                        status=ReceiptScanStatus.FAILED,
                        model=model,
                        total_tokens=0,
                        latency_ms=latency_ms,
                    )
                )
        except Exception:
            logger.exception(
                "No se pudo registrar el intento fallido de lectura",
                extra={"user_id": user_id},
            )

    async def count_since(self, user_id: int, since: datetime) -> int:
        total = await self._session.scalar(
            # Cuenta también las fallidas: si no, un archivo ilegible
            # permitiría reintentar sin techo contra un proveedor que cobra
            # por llamada.
            select(func.count())
            .select_from(ReceiptScanModel)
            .where(
                ReceiptScanModel.user_id == user_id,
                ReceiptScanModel.created_at >= a_utc_naive(since),
            )
        )
        return int(total or 0)

    async def find_possible_duplicates(
        self, user_id: int, amount: Decimal, occurred_on: date, currency: str
    ) -> list[int]:
        ids = await self._session.scalars(
            select(TransactionModel.id).where(
                TransactionModel.user_id == user_id,
                TransactionModel.type == TransactionType.EXPENSE,
                TransactionModel.amount == amount,
                TransactionModel.occurred_on == occurred_on,
                TransactionModel.currency == currency,
            )
        )
        return list(ids.all())
