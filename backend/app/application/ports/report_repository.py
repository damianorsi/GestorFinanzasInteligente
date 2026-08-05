"""Puerto de agregaciones para reportes.

Es un puerto aparte del de movimientos porque devuelve totales y no entidades:
sumar en SQL es la diferencia entre una consulta y traerse el historial entero
a memoria para recorrerlo.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from app.application.dtos import CategoryTotal, MonthlyTotal, PeriodSummary
from app.domain.enums import TransactionType


class ReportRepository(Protocol):
    async def period_summary(
        self, user_id: int, currency: str, date_from: date, date_to: date
    ) -> PeriodSummary:
        """Ingresos y gastos totales del período. Sin movimientos, devuelve ceros."""
        ...

    async def totals_by_category(
        self,
        user_id: int,
        currency: str,
        date_from: date,
        date_to: date,
        type: TransactionType | None = None,
    ) -> list[CategoryTotal]:
        """Agregado por categoría, de mayor a menor."""
        ...

    async def monthly_totals(
        self, user_id: int, currency: str, date_from: date, date_to: date
    ) -> list[MonthlyTotal]:
        """Totales por mes. **Solo devuelve los meses que tienen movimientos.**

        Rellenar los meses vacíos es responsabilidad del caso de uso: un
        GROUP BY no puede inventar filas que no existen.
        """
        ...
