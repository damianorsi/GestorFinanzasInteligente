"""Agregaciones de reportes sobre SQLAlchemy.

Las sumas las hace MySQL. Traer los movimientos a memoria para recorrerlos
funcionaría con cien filas y se caería con cien mil.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos import CategoryTotal, MonthlyTotal, PeriodSummary
from app.domain.enums import TransactionType
from app.domain.value_objects import Money
from app.infrastructure.db.models import CategoryModel, TransactionModel

CERO = Decimal("0")


class SqlAlchemyReportRepository:
    """Implementación del puerto `ReportRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _acotar(
        self,
        consulta: Select[Any],
        user_id: int,
        currency: str,
        date_from: date,
        date_to: date,
    ) -> Select[Any]:
        return consulta.where(
            TransactionModel.user_id == user_id,
            TransactionModel.currency == currency,
            TransactionModel.occurred_on >= date_from,
            TransactionModel.occurred_on <= date_to,
        )

    async def period_summary(
        self, user_id: int, currency: str, date_from: date, date_to: date
    ) -> PeriodSummary:
        consulta = self._acotar(
            select(TransactionModel.type, func.sum(TransactionModel.amount)),
            user_id,
            currency,
            date_from,
            date_to,
        ).group_by(TransactionModel.type)

        filas = (await self._session.execute(consulta)).all()
        # Un tipo sin movimientos no aparece en el GROUP BY: su total es cero,
        # no ausencia. Por eso el default y no un KeyError.
        totales = {tipo: monto or CERO for tipo, monto in filas}

        return PeriodSummary(
            currency=currency,
            date_from=date_from,
            date_to=date_to,
            income=Money(totales.get(TransactionType.INCOME, CERO), currency),
            expense=Money(totales.get(TransactionType.EXPENSE, CERO), currency),
        )

    async def totals_by_category(
        self,
        user_id: int,
        currency: str,
        date_from: date,
        date_to: date,
        type: TransactionType | None = None,
    ) -> list[CategoryTotal]:
        total = func.sum(TransactionModel.amount)
        consulta = self._acotar(
            select(
                CategoryModel.id,
                CategoryModel.name,
                TransactionModel.type,
                total.label("total"),
                func.count(TransactionModel.id).label("cantidad"),
            ).join(CategoryModel, CategoryModel.id == TransactionModel.category_id),
            user_id,
            currency,
            date_from,
            date_to,
        )
        if type is not None:
            consulta = consulta.where(TransactionModel.type == type)

        consulta = consulta.group_by(
            CategoryModel.id, CategoryModel.name, TransactionModel.type
        ).order_by(total.desc(), CategoryModel.name)

        filas = (await self._session.execute(consulta)).all()
        return [
            CategoryTotal(
                category_id=int(category_id),
                category_name=str(nombre),
                type=tipo,
                total=Money(monto or CERO, currency),
                transaction_count=int(cantidad),
            )
            for category_id, nombre, tipo, monto, cantidad in filas
        ]

    async def monthly_totals(
        self, user_id: int, currency: str, date_from: date, date_to: date
    ) -> list[MonthlyTotal]:
        # Descomponer una columna DATE en año y mes no viola la regla de "no
        # calcular fechas en SQL": esa regla prohíbe derivar *hoy* en la base,
        # porque dependería de la zona horaria del servidor. Extraer partes de
        # una fecha ya almacenada es determinístico.
        anio = extract("year", TransactionModel.occurred_on).label("anio")
        mes = extract("month", TransactionModel.occurred_on).label("mes")

        consulta = (
            self._acotar(
                select(anio, mes, TransactionModel.type, func.sum(TransactionModel.amount)),
                user_id,
                currency,
                date_from,
                date_to,
            )
            .group_by(anio, mes, TransactionModel.type)
            .order_by(anio, mes)
        )

        acumulado: dict[date, dict[TransactionType, Decimal]] = {}
        for anio_valor, mes_valor, tipo, monto in (await self._session.execute(consulta)).all():
            periodo = date(int(anio_valor), int(mes_valor), 1)
            acumulado.setdefault(periodo, {})[tipo] = monto or CERO

        return [
            MonthlyTotal(
                period=periodo,
                income=Money(totales.get(TransactionType.INCOME, CERO), currency),
                expense=Money(totales.get(TransactionType.EXPENSE, CERO), currency),
            )
            for periodo, totales in sorted(acumulado.items())
        ]
