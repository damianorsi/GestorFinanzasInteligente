"""Tests del scheduler.

El job en sí se testea en `test_recurring_generation.py`: acá solo se cubre lo
que el scheduler decide por su cuenta —si arranca y qué informa en `/health`—
porque eso no vive en ningún caso de uso.
"""

from __future__ import annotations

from datetime import datetime

from app.core.config import Settings, get_settings
from app.infrastructure.scheduler import EstadoDelScheduler, iniciar_scheduler
from app.infrastructure.scheduler import estado as estado_global


class TestArranque:
    def test_no_arranca_en_el_entorno_de_test(self) -> None:
        # Act
        scheduler = iniciar_scheduler(get_settings())

        # Assert: un job disparándose en medio de la suite generaría
        # movimientos que ningún test pidió y volvería las aserciones no
        # deterministas.
        assert scheduler is None

    async def test_arranca_fuera_de_test_y_se_puede_apagar(self) -> None:
        # Arrange: async a propósito. `AsyncIOScheduler.start()` se engancha al
        # loop corriendo, así que solo se puede iniciar desde adentro de uno
        # —que es justo lo que hace el `lifespan` de FastAPI—.
        settings = Settings(app_env="development", jwt_secret_key="x" * 40)

        # Act
        scheduler = iniciar_scheduler(settings)

        # Assert
        assert scheduler is not None
        try:
            assert scheduler.get_job("generar-recurrentes") is not None
        finally:
            scheduler.shutdown(wait=False)
            # `estado` es global del proceso: sin restaurarlo, el test de
            # `/health` vería un scheduler habilitado que nadie arrancó.
            estado_global.habilitado = False


class TestEstado:
    def test_deshabilitado_mientras_no_arranco(self) -> None:
        assert EstadoDelScheduler().estado == "disabled"

    def test_pendiente_apenas_arranca(self) -> None:
        assert EstadoDelScheduler(habilitado=True).estado == "pending"

    def test_ok_despues_de_una_corrida(self) -> None:
        # Arrange
        estado = EstadoDelScheduler(habilitado=True, ultima_corrida=datetime(2026, 8, 5, 3, 0))

        # Act / Assert
        assert estado.estado == "ok"

    def test_error_si_la_ultima_corrida_fallo(self) -> None:
        # Arrange: se informa el error aunque haya habido corridas exitosas
        # antes, porque lo que importa es si el job está funcionando ahora.
        estado = EstadoDelScheduler(
            habilitado=True,
            ultima_corrida=datetime(2026, 8, 5, 3, 0),
            ultimo_error="OperationalError",
        )

        # Act / Assert
        assert estado.estado == "error"
