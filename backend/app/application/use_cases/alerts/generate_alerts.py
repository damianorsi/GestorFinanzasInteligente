"""El job de alertas proactivas (docs/PROMPT.md §21.2)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.application.dtos import BudgetProgress, TemporalContext, UnbudgetedSpending
from app.application.exceptions import AssistantUnavailableError
from app.application.ports import BudgetAlertRepository, BudgetRepository, ChatAgent
from app.application.use_cases.budgets import GetBudgetProgress
from app.domain.alerts import detectar_desvio, porcentaje_proyectado
from app.domain.calendar import etiqueta_de_periodo, primer_dia_del_mes
from app.domain.entities import BudgetAlert
from app.domain.enums import AlertType
from app.domain.value_objects import Money

logger = logging.getLogger(__name__)


@dataclass
class AlertGenerationResult:
    """Qué hizo una corrida del job."""

    as_of: date
    created: int = 0
    already_open: int = 0
    resolved: int = 0
    users_processed: int = 0
    users_failed: int = 0
    recommendations: int = 0
    tipos: dict[str, int] = field(default_factory=dict)


class GenerateBudgetAlerts:
    """Detecta desvíos presupuestarios y emite alertas.

    Lo que la vuelve **proactiva** es la proyección: avisar al día 10 que el
    ritmo termina en 180% del tope todavía se puede corregir; decir "te
    pasaste" cuando ya pasó es repetir lo que la pantalla de presupuestos ya
    muestra.

    Lo que la vuelve **IA** es la recomendación: la detección es una regla, y
    qué hacer al respecto lo redacta el agente con las herramientas que ya
    existen. Si el proveedor no responde, la alerta se emite igual sin
    recomendación.

    Es idempotente por la UNIQUE del libro de alertas: correrla cincuenta veces
    deja lo mismo que correrla una.

    **Alcance deliberado**: solo mira a quienes tienen al menos un presupuesto
    en el mes. Quien nunca definió ninguno no recibe alertas, ni siquiera de
    categorías sin tope. Es una decisión de producto —avisarle a alguien que no
    usa la función es consejo no pedido, y la pantalla de presupuestos ya le
    muestra sus gastos sin tope— y también de costo: recorrer a todos los
    usuarios activos significaría calcular el avance completo de cada uno todos
    los días.
    """

    def __init__(
        self,
        budgets: BudgetRepository,
        alerts: BudgetAlertRepository,
        progress: GetBudgetProgress,
        currency: str,
        minimo_sin_presupuesto: Decimal,
        agent: ChatAgent | None = None,
        max_recomendaciones: int = 0,
    ) -> None:
        self._budgets = budgets
        self._alerts = alerts
        self._progress = progress
        self._currency = currency
        self._minimo_sin_presupuesto = minimo_sin_presupuesto
        self._agent = agent
        self._max_recomendaciones = max_recomendaciones

    async def execute(self, as_of: date) -> AlertGenerationResult:
        periodo = primer_dia_del_mes(as_of)
        usuarios = await self._budgets.list_user_ids_with_budgets(periodo, self._currency)
        resultado = AlertGenerationResult(as_of=as_of, users_processed=len(usuarios))
        # El presupuesto de recomendaciones es global a la corrida, no por
        # usuario: cada una es una corrida completa del agente y sin techo el
        # job podría gastar sin control en una base con muchos usuarios.
        presupuesto_de_recomendaciones = self._max_recomendaciones

        for user_id in usuarios:
            try:
                presupuesto_de_recomendaciones = await self._procesar_usuario(
                    user_id, periodo, as_of, resultado, presupuesto_de_recomendaciones
                )
            except Exception:
                # Un usuario que falla no puede dejar sin alertas a los demás,
                # igual que en el job de recurrentes.
                resultado.users_failed += 1
                logger.exception("Falló la generación de alertas", extra={"user_id": user_id})

        logger.info(
            "Job de alertas ejecutado",
            extra={
                "as_of": as_of.isoformat(),
                "created": resultado.created,
                "already_open": resultado.already_open,
                "resolved": resultado.resolved,
                "users_processed": resultado.users_processed,
                "users_failed": resultado.users_failed,
                "recommendations": resultado.recommendations,
            },
        )
        return resultado

    async def _procesar_usuario(
        self,
        user_id: int,
        periodo: date,
        as_of: date,
        resultado: AlertGenerationResult,
        presupuesto_de_recomendaciones: int,
    ) -> int:
        # Se reusa el mismo caso de uso que alimenta la pantalla: si el job
        # calculara el gasto por su cuenta, la alerta podría decir una cifra y
        # la pantalla otra, y no habría forma de saber cuál está bien.
        reporte = await self._progress.execute(user_id, periodo)

        vigentes: set[int] = set()

        for entrada in reporte.entries:
            tipo = detectar_desvio(entrada.spent, entrada.budgeted, as_of)
            if tipo is None:
                continue
            alerta, presupuesto_de_recomendaciones = await self._emitir(
                user_id=user_id,
                periodo=periodo,
                tipo=tipo,
                mensaje=self._mensaje_de_presupuesto(tipo, entrada, as_of),
                category_id=entrada.category_id,
                proyectado=porcentaje_proyectado(entrada.spent, entrada.budgeted, as_of),
                pregunta=self._pregunta(tipo, entrada.category_name, as_of),
                resultado=resultado,
                presupuesto_de_recomendaciones=presupuesto_de_recomendaciones,
            )
            if alerta is not None:
                vigentes.add(alerta.id or 0)

        for sin_tope in reporte.unbudgeted:
            if sin_tope.spent.amount < self._minimo_sin_presupuesto:
                continue
            alerta, presupuesto_de_recomendaciones = await self._emitir(
                user_id=user_id,
                periodo=periodo,
                tipo=AlertType.UNBUDGETED_SPENDING,
                mensaje=self._mensaje_sin_presupuesto(sin_tope),
                category_id=sin_tope.category_id,
                proyectado=None,
                # Sin recomendación: qué hacer acá ya lo dice el propio
                # mensaje —definir un tope—, y gastar una corrida del agente
                # para repetirlo no aporta.
                pregunta=None,
                resultado=resultado,
                presupuesto_de_recomendaciones=presupuesto_de_recomendaciones,
            )
            if alerta is not None:
                vigentes.add(alerta.id or 0)

        abiertas = await self._alerts.list_open_period_ids(user_id, periodo)
        if abiertas - vigentes:
            resultado.resolved += await self._alerts.resolve_stale(user_id, periodo, vigentes)

        return presupuesto_de_recomendaciones

    async def _emitir(
        self,
        *,
        user_id: int,
        periodo: date,
        tipo: AlertType,
        mensaje: str,
        category_id: int,
        proyectado: Decimal | None,
        pregunta: str | None,
        resultado: AlertGenerationResult,
        presupuesto_de_recomendaciones: int,
    ) -> tuple[BudgetAlert | None, int]:
        borrador = BudgetAlert(
            user_id=user_id,
            category_id=category_id,
            period_month=periodo,
            type=tipo,
            message=mensaje,
            projected_percentage=proyectado,
        )
        creada = await self._alerts.create_if_absent(borrador)

        if creada is None:
            # Ya existía: sigue vigente, pero no se vuelve a emitir ni se le
            # regenera la recomendación.
            resultado.already_open += 1
            existentes = await self._alerts.list_for_user(user_id)
            previa = next(
                (
                    alerta
                    for alerta in existentes
                    if alerta.category_id == category_id
                    and alerta.period_month == periodo
                    and alerta.type is tipo
                ),
                None,
            )
            return previa, presupuesto_de_recomendaciones

        resultado.created += 1
        resultado.tipos[tipo.value] = resultado.tipos.get(tipo.value, 0) + 1

        if pregunta and presupuesto_de_recomendaciones > 0:
            recomendacion = await self._recomendar(user_id, pregunta, as_of=periodo)
            presupuesto_de_recomendaciones -= 1
            if recomendacion:
                creada.recommendation = recomendacion
                await self._alerts.update(creada)
                resultado.recommendations += 1

        return creada, presupuesto_de_recomendaciones

    async def _recomendar(self, user_id: int, pregunta: str, as_of: date) -> str | None:
        """Le pide al agente qué hacer con el desvío.

        Devuelve `None` si el proveedor no responde: la alerta ya se creó y su
        valor no depende de esto.
        """
        if self._agent is None:
            return None
        try:
            respuesta = await self._agent.answer(
                user_id=user_id,
                message=pregunta,
                history=[],
                temporal=self._contexto(as_of),
            )
        except AssistantUnavailableError:
            logger.info(
                "Alerta emitida sin recomendación: el asistente no respondió",
                extra={"user_id": user_id},
            )
            return None
        return None if respuesta.degraded else respuesta.content

    @staticmethod
    def _contexto(periodo: date) -> TemporalContext:
        from app.domain.calendar import sumar_meses, ultimo_dia_del_mes

        anterior = sumar_meses(periodo, -1)
        return TemporalContext(
            today=periodo.isoformat(),
            current_month=etiqueta_de_periodo(periodo),
            current_month_from=periodo.isoformat(),
            current_month_to=ultimo_dia_del_mes(periodo).isoformat(),
            previous_month=etiqueta_de_periodo(anterior),
            previous_month_from=anterior.isoformat(),
            previous_month_to=ultimo_dia_del_mes(anterior).isoformat(),
        )

    @staticmethod
    def _pregunta(tipo: AlertType, categoria: str, as_of: date) -> str:
        mes = etiqueta_de_periodo(as_of)
        if tipo is AlertType.BUDGET_EXCEEDED:
            return (
                f"Me pasé del presupuesto de {categoria} en {mes}. "
                "En dos o tres frases, ¿qué me conviene hacer con lo que queda del mes?"
            )
        return (
            f"Al ritmo actual voy a pasarme del presupuesto de {categoria} en {mes}. "
            "En dos o tres frases, ¿qué me conviene ajustar para no pasarme?"
        )

    @staticmethod
    def _mensaje_de_presupuesto(tipo: AlertType, entrada: BudgetProgress, as_of: date) -> str:
        gastado = _con_moneda(entrada.spent)
        tope = _con_moneda(entrada.budgeted)
        if tipo is AlertType.BUDGET_EXCEEDED:
            return (
                f"Te pasaste del presupuesto de {entrada.category_name}: "
                f"gastaste {gastado} de {tope}."
            )
        proyectado = porcentaje_proyectado(entrada.spent, entrada.budgeted, as_of)
        return (
            f"Vas camino a pasarte del presupuesto de {entrada.category_name}. "
            f"Llevás {gastado} de {tope} y, a este ritmo, el mes termina "
            f"en el {proyectado}% del tope."
        )

    @staticmethod
    def _mensaje_sin_presupuesto(sin_tope: UnbudgetedSpending) -> str:
        return (
            f"Gastaste {_con_moneda(sin_tope.spent)} en {sin_tope.category_name} "
            "y esa categoría no tiene presupuesto este mes."
        )


def _con_moneda(monto: Money) -> str:
    """Monto listo para leer, con su moneda al lado.

    A diferencia del formato que reciben las tools del asistente, este texto se
    muestra tal cual en pantalla: `43500.00 ARS` al lado de un `$ 43.500,00`
    del resto de la app se lee como un dato crudo que se escapó.

    Se agrupan los miles con punto y se separan los decimales con coma, como en
    es-AR. La moneda va como código y no como símbolo porque el backend no
    tiene un mapa de símbolos y no corresponde inventarlo acá.
    """
    entero, _, decimales = f"{monto.amount:.2f}".partition(".")
    signo, digitos = ("-", entero[1:]) if entero.startswith("-") else ("", entero)
    return f"{signo}{f'{int(digitos):,}'.replace(',', '.')},{decimales} {monto.currency}"
