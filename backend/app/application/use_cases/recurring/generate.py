"""El job de generación de movimientos recurrentes.

Es un caso de uso normal, invocable a mano: el scheduler solo lo llama. Los
tests testean esto, no APScheduler (docs/PROMPT.md §9).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from app.application.dtos import GenerationResult
from app.application.ports import (
    CategoryRepository,
    RecurringOccurrenceRepository,
    RecurringRuleRepository,
)
from app.domain.entities import RecurringRule, Transaction
from app.domain.recurrence import fechas_de_la_regla

logger = logging.getLogger(__name__)


class GenerateRecurringTransactions:
    """Materializa las ocurrencias pendientes de todas las reglas activas.

    Tres invariantes que no se pueden romper:

    1. **Nunca se materializa el futuro.** Solo se generan fechas menores o
       iguales a `as_of`. Materializar el sueldo del día 1 por adelantado haría
       que el balance de hoy muestre plata que todavía no se cobró.
    2. **Es idempotente.** Correrlo cincuenta veces seguidas genera lo mismo
       que correrlo una. El libro mayor dice qué fechas ya se resolvieron y la
       UNIQUE de la base es la red por si dos corridas se pisan.
    3. **Una regla que falla no voltea a las demás.** Cada una se procesa por
       separado con su propio manejo de error.
    """

    def __init__(
        self,
        rules: RecurringRuleRepository,
        occurrences: RecurringOccurrenceRepository,
        categories: CategoryRepository,
        catchup_max_days: int,
    ) -> None:
        self._rules = rules
        self._occurrences = occurrences
        self._categories = categories
        self._catchup_max_days = catchup_max_days

    async def execute(self, as_of: date) -> GenerationResult:
        reglas = await self._rules.list_all_active()

        generados = 0
        ya_resueltas = 0
        fallidas = 0
        desactivadas = 0
        recortadas: list[int] = []

        for regla in reglas:
            try:
                nuevos, existentes, recortada = await self._procesar(regla, as_of)
            except _CategoriaInexistenteError:
                await self._rules.deactivate(regla.id or 0)
                desactivadas += 1
                logger.warning(
                    "Regla desactivada: su categoría ya no existe",
                    extra={"rule_id": regla.id, "category_id": regla.category_id},
                )
                continue
            except Exception:
                # Se traga la excepción a propósito: el objetivo es que las
                # otras reglas se generen igual. El `exception` deja el stack
                # completo para poder investigarlo después.
                fallidas += 1
                logger.exception("Falló la generación de una regla", extra={"rule_id": regla.id})
                continue

            generados += nuevos
            ya_resueltas += existentes
            if recortada:
                recortadas.append(regla.id or 0)

        resultado = GenerationResult(
            as_of=as_of,
            generated=generados,
            already_resolved=ya_resueltas,
            rules_processed=len(reglas),
            rules_failed=fallidas,
            rules_deactivated=desactivadas,
            rules_truncated=recortadas,
        )
        logger.info(
            "Job de recurrentes ejecutado",
            extra={
                "as_of": as_of.isoformat(),
                "generated": generados,
                "already_resolved": ya_resueltas,
                "rules_processed": len(reglas),
                "rules_failed": fallidas,
                "rules_deactivated": desactivadas,
                "rules_truncated": len(recortadas),
            },
        )
        return resultado

    async def _procesar(self, regla: RecurringRule, as_of: date) -> tuple[int, int, bool]:
        """Genera lo pendiente de una regla. Devuelve (nuevos, ya resueltos, recortada)."""
        categoria = await self._categories.get_for_user(regla.user_id, regla.category_id)
        if categoria is None:
            raise _CategoriaInexistenteError

        piso = as_of - timedelta(days=self._catchup_max_days)
        # Sin este piso, un contenedor apagado ocho meses inyectaría cientos de
        # movimientos de golpe la primera vez que arranca.
        recortada = regla.starts_on < piso
        desde = max(regla.starts_on, piso)

        if recortada:
            logger.warning(
                "Catch-up recortado por el tope de días",
                extra={
                    "rule_id": regla.id,
                    "starts_on": regla.starts_on.isoformat(),
                    "desde": desde.isoformat(),
                    "catchup_max_days": self._catchup_max_days,
                },
            )

        # `as_of` como techo es la garantía de que nunca se materializa futuro.
        fechas = fechas_de_la_regla(regla, desde, as_of)
        resueltas = await self._occurrences.resolved_dates(regla.id or 0)

        nuevos = 0
        existentes = 0
        for fecha in fechas:
            if fecha in resueltas:
                existentes += 1
                continue

            movimiento = Transaction(
                user_id=regla.user_id,
                category_id=regla.category_id,
                type=regla.type,
                money=regla.money,
                occurred_on=fecha,
                description=regla.description,
                recurring_rule_id=regla.id,
            )
            if await self._occurrences.register_generated(movimiento, fecha):
                nuevos += 1
            else:
                # Otra corrida ganó la carrera. No es un error.
                existentes += 1

        return nuevos, existentes, recortada


class _CategoriaInexistenteError(Exception):
    """Interna: separa "la regla quedó huérfana" de un fallo cualquiera."""
