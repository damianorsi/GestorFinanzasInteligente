"""Implementación del puerto `Clock` sobre el reloj del sistema."""

from __future__ import annotations

from datetime import UTC, date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from app.core.config import get_settings


class SystemClock:
    """Reloj real, anclado a la zona horaria de la aplicación.

    Es el único lugar de la aplicación autorizado a preguntarle la hora al
    sistema operativo.
    """

    def __init__(self, timezone: ZoneInfo) -> None:
        self._timezone = timezone

    def today(self) -> date:
        return self.now().date()

    def now(self) -> datetime:
        return datetime.now(tz=self._timezone)

    @staticmethod
    def utc_now() -> datetime:
        """Instante actual en UTC, para timestamps de auditoría.

        Las fechas de negocio van en `APP_TIMEZONE`; los `created_at` y
        `updated_at` se guardan en UTC.
        """
        return datetime.now(tz=UTC)


@lru_cache(maxsize=1)
def get_clock() -> SystemClock:
    return SystemClock(get_settings().timezone)
