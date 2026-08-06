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

from app.application.use_cases.recurring import GenerateRecurringTransactions
from app.core.config import Settings, get_settings
from app.infrastructure.clock import SystemClock
from app.infrastructure.db.repositories import (
    SqlAlchemyCategoryRepository,
    SqlAlchemyRecurringOccurrenceRepository,
    SqlAlchemyRecurringRuleRepository,
)
from app.infrastructure.db.session import dispose_engine, session_scope

logger = logging.getLogger(__name__)

ID_DEL_JOB = "generar-recurrentes"


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

    @property
    def estado(self) -> str:
        if not self.habilitado:
            return "disabled"
        if self.ultimo_error is not None:
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
    scheduler.start()
    estado.habilitado = True
    logger.info(
        "Scheduler iniciado",
        extra={"hora": settings.recurring_job_hour, "timezone": settings.app_timezone},
    )
    return scheduler


async def _correr_a_mano() -> None:
    """Una corrida puntual desde la línea de comandos.

    `python -m app.infrastructure.scheduler` dispara el job sin esperar a la
    hora programada. Sirve para retomar tras una caída y para ver una regla
    recién creada generar sus movimientos.

    El `dispose_engine` no es opcional: sin él, `asyncio.run` cierra el loop
    antes de que aiomysql suelte sus conexiones y el comando termina escupiendo
    un `RuntimeError: Event loop is closed` que no significa nada.
    """
    settings = get_settings()
    await ejecutar_generacion(settings)
    if estado.ultimo_error is None:
        print(f"Job ejecutado. Movimientos generados: {estado.ultimos_generados}")
    else:
        print(f"El job falló: {estado.ultimo_error}. Revisá los logs.")
    await dispose_engine()


if __name__ == "__main__":
    import asyncio

    asyncio.run(_correr_a_mano())
