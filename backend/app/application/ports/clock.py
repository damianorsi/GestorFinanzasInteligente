"""Puerto `Clock`: la única fuente de "qué día es hoy".

Existe para que nadie llame a `date.today()` suelto por el código. Dos razones
(docs/PROMPT.md §5.2):

1. **Corrección**: "hoy" tiene que resolverse siempre en `APP_TIMEZONE`. Con
   una sola implementación, la decisión de zona horaria se aplica en un lugar
   en vez de repetirse —y desincronizarse— en cada llamador.
2. **Testeabilidad**: el job de recurrentes y la resolución de fechas relativas
   del asistente ("este mes", "el mes pasado") dependen de la fecha actual. Con
   un puerto inyectable, el test fija el día sin tener que parchear el reloj
   del sistema.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Protocol


class Clock(Protocol):
    """Reloj de la aplicación."""

    def today(self) -> date:
        """El día de hoy en la zona horaria de la aplicación."""
        ...

    def now(self) -> datetime:
        """El instante actual, con zona horaria."""
        ...
