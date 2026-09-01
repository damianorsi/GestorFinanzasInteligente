"""Avance y proyección de las metas de ahorro (docs/PROMPT.md §21.3)."""

from __future__ import annotations

from datetime import date, timedelta

from app.application.dtos import SavingsGoalProgress, SavingsProjection
from app.application.exceptions import UnsupportedCurrencyError
from app.application.ports import Clock, ReportRepository, SavingsGoalRepository
from app.domain.calendar import primer_dia_del_mes
from app.domain.entities import SavingsGoal
from app.domain.enums import GoalStatus
from app.domain.savings import (
    evaluar_estado,
    fecha_proyectada,
    meses_para_alcanzar,
    porcentaje_alcanzado,
    ritmo_mensual,
)
from app.domain.value_objects import Money


class GetSavingsGoalsProgress:
    """Cuánto se juntó de cada meta y, si hay con qué, cuándo se alcanzaría.

    El avance se mide contra el **balance acumulado desde `starts_on`**: el
    producto no maneja cuentas, así que no hay un saldo ahorrado que consultar.
    Es una convención, no una medición de plata apartada, y por eso la pantalla
    muestra desde cuándo cuenta.

    El ritmo sale de los meses **cerrados**: el mes en curso va por la mitad y
    meterlo en el promedio lo hunde sistemáticamente. Contarlo haría que toda
    meta se viera peor a principio de mes que a fin de mes, sin que haya
    cambiado nada.
    """

    def __init__(
        self,
        goals: SavingsGoalRepository,
        reports: ReportRepository,
        clock: Clock,
        supported_currencies: frozenset[str],
        default_currency: str,
    ) -> None:
        self._goals = goals
        self._reports = reports
        self._clock = clock
        self._supported_currencies = supported_currencies
        self._default_currency = default_currency

    async def execute(self, user_id: int, currency: str | None = None) -> list[SavingsGoalProgress]:
        moneda = (currency or self._default_currency).upper()
        if moneda not in self._supported_currencies:
            habilitadas = ", ".join(sorted(self._supported_currencies))
            raise UnsupportedCurrencyError(
                f"La moneda {moneda} no está habilitada. Disponibles: {habilitadas}."
            )

        metas = await self._goals.list_for_user(user_id, moneda, only_active=True)
        if not metas:
            return []

        hoy = self._clock.today()
        return [await self._avance(user_id, meta, moneda, hoy) for meta in metas]

    async def _avance(
        self, user_id: int, meta: SavingsGoal, moneda: str, hoy: date
    ) -> SavingsGoalProgress:
        acumulado = await self._acumulado_desde(user_id, meta.starts_on, moneda, hoy)
        faltante = meta.target - acumulado

        # Una meta alcanzada deja de proyectar (§21.3): "llegás en 0 meses" no
        # es información, y calcularlo sería consultar la base para nada.
        alcanzada = acumulado >= meta.target
        proyeccion = (
            None if alcanzada else await self._proyeccion(user_id, meta, moneda, hoy, faltante)
        )

        if alcanzada:
            estado: GoalStatus | None = GoalStatus.ACHIEVED
        elif proyeccion is None:
            # Sin historial no se sabe, y `AT_RISK` sería un diagnóstico que
            # los datos no sostienen.
            estado = None
        else:
            estado = evaluar_estado(
                acumulado, meta.target, proyeccion.months_to_target, meta.target_date, hoy
            )

        return SavingsGoalProgress(
            goal_id=meta.id or 0,
            name=meta.name,
            target=meta.target,
            saved=acumulado,
            # Lo que falta no baja de cero: "te faltan -50.000" no se entiende,
            # y el excedente ya se ve en el porcentaje.
            remaining=max(faltante, Money.zero(moneda)),
            percentage=porcentaje_alcanzado(acumulado, meta.target),
            starts_on=meta.starts_on,
            target_date=meta.target_date,
            status=estado,
            projection=proyeccion,
        )

    async def _acumulado_desde(self, user_id: int, desde: date, moneda: str, hoy: date) -> Money:
        """Balance acumulado entre el inicio de la meta y hoy.

        Puede ser negativo: es una resta de ingresos menos gastos, no un total.
        """
        if desde > hoy:
            # Una meta que arranca en el futuro todavía no acumuló nada, y
            # pedir un rango invertido devolvería basura.
            return Money.zero(moneda)
        resumen = await self._reports.period_summary(user_id, moneda, desde, hoy)
        return resumen.balance

    async def _proyeccion(
        self, user_id: int, meta: SavingsGoal, moneda: str, hoy: date, faltante: Money
    ) -> SavingsProjection | None:
        """El ritmo mensual y lo que implica, o `None` si falta historial."""
        # El último día del mes cerrado más reciente.
        fin = primer_dia_del_mes(hoy) - timedelta(days=1)
        if meta.starts_on > fin:
            # La meta arrancó este mes: todavía no hay ningún mes cerrado.
            return None

        mensuales = await self._reports.monthly_totals(user_id, moneda, meta.starts_on, fin)
        # `monthly_totals` solo devuelve los meses con movimientos. No se
        # rellenan los vacíos: un mes sin un solo movimiento es un mes sin
        # datos, y contarlo como balance cero diría que esa persona ahorró
        # exactamente nada, que es una afirmación más fuerte que "no sé".
        ritmo = ritmo_mensual([mes.balance for mes in mensuales], moneda)
        if ritmo is None:
            return None

        meses = meses_para_alcanzar(faltante, ritmo)
        return SavingsProjection(
            monthly_rate=ritmo,
            months_of_history=len(mensuales),
            months_to_target=meses,
            projected_date=None if meses is None else fecha_proyectada(hoy, meses),
        )
