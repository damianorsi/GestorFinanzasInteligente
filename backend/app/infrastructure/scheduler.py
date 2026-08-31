"""Scheduler del job de movimientos recurrentes.

El job **no tiene lógica**: arma las dependencias, llama al caso de uso y
registra el resultado. Todo lo que se pueda probar vive en
`GenerateRecurringTransactions`, que se invoca a mano en los tests
(docs/PROMPT.md §4 y §9).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.application.use_cases.alerts import GenerateBudgetAlerts
from app.application.use_cases.budgets import GetBudgetProgress
from app.application.use_cases.recurring import GenerateRecurringTransactions
from app.application.use_cases.reports import (
    GetCategoryBreakdown,
    GetMonthlyTrend,
    GetPeriodSummary,
)
from app.application.use_cases.transactions import ListTransactions
from app.core.config import Settings, get_settings
from app.infrastructure.assistant import DependenciasDelAsistente, LangChainAssistant
from app.infrastructure.clock import SystemClock
from app.infrastructure.db.repositories import (
    SqlAlchemyBudgetAlertRepository,
    SqlAlchemyBudgetRepository,
    SqlAlchemyCategoryRepository,
    SqlAlchemyRecurringOccurrenceRepository,
    SqlAlchemyRecurringRuleRepository,
    SqlAlchemyReportRepository,
    SqlAlchemyTransactionRepository,
)
from app.infrastructure.db.session import dispose_engine, session_scope

logger = logging.getLogger(__name__)

ID_DEL_JOB = "generar-recurrentes"
ID_DEL_JOB_DE_ALERTAS = "generar-alertas"


@dataclass
class EstadoDelScheduler:
    """Última corrida, para poder informarla en `GET /health`.

    Vive en memoria a propósito: es un dato operativo de **este** proceso. Con
    varias réplicas cada una informaría la suya, que es justamente lo que se
    quiere saber.
    """

    habilitado: bool = False
    ultima_corrida: datetime | None = None
    ultimo_error: str | None = None
    ultimos_generados: int = 0
    # El job de alertas se informa aparte: que falle no dice nada sobre el de
    # recurrentes, y mezclarlos escondería cuál de los dos se rompió.
    ultima_corrida_de_alertas: datetime | None = None
    ultimo_error_de_alertas: str | None = None
    ultimas_alertas: int = 0

    @property
    def estado(self) -> str:
        if not self.habilitado:
            return "disabled"
        if self.ultimo_error is not None or self.ultimo_error_de_alertas is not None:
            return "error"
        return "ok" if self.ultima_corrida is not None else "pending"


estado = EstadoDelScheduler()


async def ejecutar_generacion(settings: Settings) -> None:
    """Una corrida del job. Se puede invocar a mano desde un shell."""
    reloj = SystemClock(settings.timezone)
    try:
        async with session_scope() as session:
            caso = GenerateRecurringTransactions(
                rules=SqlAlchemyRecurringRuleRepository(session),
                occurrences=SqlAlchemyRecurringOccurrenceRepository(session),
                categories=SqlAlchemyCategoryRepository(session),
                catchup_max_days=settings.recurring_catchup_max_days,
            )
            resultado = await caso.execute(reloj.today())
    except Exception as exc:
        # Que el job falle no puede voltear al scheduler: si la excepción
        # escapara, APScheduler lo anotaría y el proceso seguiría sin volver a
        # intentarlo hasta mañana, pero sin dejar rastro en /health.
        estado.ultimo_error = type(exc).__name__
        logger.exception("Falló la corrida del job de recurrentes")
        return

    estado.ultima_corrida = reloj.now()
    estado.ultimo_error = None
    estado.ultimos_generados = resultado.generated


async def ejecutar_alertas(settings: Settings) -> None:
    """Una corrida del job de alertas (docs/PROMPT.md §21.2).

    Va **después** del de recurrentes en la misma madrugada: los movimientos
    generados por reglas cuentan para el presupuesto, y si las alertas corrieran
    primero avisarían sobre un gasto que todavía no incluye el alquiler del mes.
    """
    reloj = SystemClock(settings.timezone)
    monedas = settings.supported_currencies_set
    moneda = settings.default_currency
    try:
        async with session_scope() as session:
            reportes = SqlAlchemyReportRepository(session)
            categorias = SqlAlchemyCategoryRepository(session)
            presupuestos = SqlAlchemyBudgetRepository(session)

            agente: LangChainAssistant | None = None
            if settings.openai_api_key:
                agente = LangChainAssistant(
                    deps=DependenciasDelAsistente(
                        resumen=GetPeriodSummary(reportes, reloj, monedas, moneda),
                        por_categoria=GetCategoryBreakdown(reportes, reloj, monedas, moneda),
                        tendencia=GetMonthlyTrend(reportes, reloj, monedas, moneda),
                        presupuestos=GetBudgetProgress(
                            presupuestos, categorias, reportes, monedas, moneda
                        ),
                        movimientos=ListTransactions(SqlAlchemyTransactionRepository(session)),
                        reglas=SqlAlchemyRecurringRuleRepository(session),
                        default_currency=moneda,
                    ),
                    api_key=settings.openai_api_key,
                    model=settings.openai_model,
                    max_tokens=settings.openai_max_tokens,
                    max_iterations=settings.agent_max_iterations,
                    timeout_seconds=settings.openai_timeout_seconds,
                )

            caso = GenerateBudgetAlerts(
                budgets=presupuestos,
                alerts=SqlAlchemyBudgetAlertRepository(session),
                progress=GetBudgetProgress(presupuestos, categorias, reportes, monedas, moneda),
                currency=moneda,
                minimo_sin_presupuesto=settings.alerts_min_unbudgeted_amount,
                agent=agente,
                max_recomendaciones=settings.alerts_max_recommendations,
            )
            resultado = await caso.execute(reloj.today())
    except Exception as exc:
        estado.ultimo_error_de_alertas = type(exc).__name__
        logger.exception("Falló la corrida del job de alertas")
        return

    estado.ultima_corrida_de_alertas = reloj.now()
    estado.ultimo_error_de_alertas = None
    estado.ultimas_alertas = resultado.created


def iniciar_scheduler(settings: Settings) -> AsyncIOScheduler | None:
    """Arranca el scheduler, salvo en tests.

    En el entorno de test no se arranca: un job disparándose en medio de la
    suite generaría movimientos que ningún test pidió y volvería las
    aserciones no deterministas.
    """
    if settings.app_env == "test":
        logger.info("Scheduler no iniciado: entorno de test")
        return None

    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.add_job(
        ejecutar_generacion,
        trigger=CronTrigger(hour=settings.recurring_job_hour, minute=0),
        args=[settings],
        id=ID_DEL_JOB,
        # Si el proceso estuvo caído a la hora del job, se corre igual al
        # arrancar: el catch-up del caso de uso se encarga del resto.
        misfire_grace_time=None,
        # Nunca dos corridas simultáneas de lo mismo.
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        ejecutar_alertas,
        trigger=CronTrigger(hour=settings.alerts_job_hour, minute=0),
        args=[settings],
        id=ID_DEL_JOB_DE_ALERTAS,
        misfire_grace_time=None,
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.start()
    estado.habilitado = True
    logger.info(
        "Scheduler iniciado",
        extra={"hora": settings.recurring_job_hour, "timezone": settings.app_timezone},
    )
    return scheduler


async def _correr_a_mano(cual: str) -> None:
    """Una corrida puntual desde la línea de comandos.

        python -m app.infrastructure.scheduler            # recurrentes
        python -m app.infrastructure.scheduler alertas    # alertas

    Sirve para retomar tras una caída y para ver el efecto de una regla o un
    presupuesto recién creados sin esperar a la madrugada.

    El `dispose_engine` no es opcional: sin él, `asyncio.run` cierra el loop
    antes de que aiomysql suelte sus conexiones y el comando termina escupiendo
    un `RuntimeError: Event loop is closed` que no significa nada.
    """
    settings = get_settings()
    if cual == "alertas":
        await ejecutar_alertas(settings)
        if estado.ultimo_error_de_alertas is None:
            print(f"Job de alertas ejecutado. Alertas nuevas: {estado.ultimas_alertas}")
        else:
            print(f"El job de alertas falló: {estado.ultimo_error_de_alertas}. Revisá los logs.")
    else:
        await ejecutar_generacion(settings)
        if estado.ultimo_error is None:
            print(f"Job ejecutado. Movimientos generados: {estado.ultimos_generados}")
        else:
            print(f"El job falló: {estado.ultimo_error}. Revisá los logs.")
    await dispose_engine()


if __name__ == "__main__":
    import asyncio
    import sys

    asyncio.run(_correr_a_mano(sys.argv[1] if len(sys.argv) > 1 else "recurrentes"))
