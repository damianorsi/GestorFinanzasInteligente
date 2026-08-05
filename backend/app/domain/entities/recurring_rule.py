"""Entidad `RecurringRule`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.domain.enums import RecurrenceFrequency, TransactionType
from app.domain.exceptions import InvalidRecurringRuleError
from app.domain.value_objects import Money

LARGO_MAXIMO_DESCRIPCION = 255
DIA_DEL_MES_MAXIMO = 31
DIA_DE_LA_SEMANA_MAXIMO = 6


@dataclass(slots=True)
class RecurringRule:
    """Regla que genera movimientos periódicos.

    Solo describe *qué* generar y *cada cuánto*. El cálculo de las fechas
    concretas es una función pura aparte (fase 12), y la materialización la
    hace el job, nunca esta entidad.
    """

    user_id: int
    category_id: int
    type: TransactionType
    money: Money
    frequency: RecurrenceFrequency
    starts_on: date
    description: str = ""
    day_of_month: int | None = None
    day_of_week: int | None = None
    ends_on: date | None = None
    is_active: bool = True
    id: int | None = None

    def __post_init__(self) -> None:
        if not self.money.is_positive:
            raise InvalidRecurringRuleError(
                f"El monto de una regla debe ser mayor a cero, se recibió {self.money}."
            )

        descripcion = self.description.strip()
        if len(descripcion) > LARGO_MAXIMO_DESCRIPCION:
            raise InvalidRecurringRuleError(
                f"La descripción no puede superar los {LARGO_MAXIMO_DESCRIPCION} caracteres."
            )
        self.description = descripcion

        if self.ends_on is not None and self.ends_on < self.starts_on:
            raise InvalidRecurringRuleError(
                f"La fecha de fin ({self.ends_on.isoformat()}) no puede ser anterior "
                f"a la de inicio ({self.starts_on.isoformat()})."
            )

        self._validar_parametros_de_frecuencia()

    def _validar_parametros_de_frecuencia(self) -> None:
        """Cada frecuencia exige exactamente los parámetros que usa.

        Se rechazan los sobrantes además de los faltantes: una regla semanal
        con `day_of_month` cargado es ambigua, y dejarla pasar significa que el
        job la interpreta distinto de lo que esperaba quien la creó.
        """
        # YEARLY no lleva parámetros: repite el mes y el día de `starts_on`.
        # Pedirle `day_of_month` sería ambiguo, porque no diría en qué mes cae.
        # DAILY tampoco lleva, por razones obvias.
        requiere_dia_del_mes = self.frequency is RecurrenceFrequency.MONTHLY
        requiere_dia_de_la_semana = self.frequency is RecurrenceFrequency.WEEKLY

        if requiere_dia_del_mes:
            if self.day_of_month is None:
                raise InvalidRecurringRuleError(
                    f"La frecuencia {self.frequency} requiere day_of_month."
                )
            if not 1 <= self.day_of_month <= DIA_DEL_MES_MAXIMO:
                raise InvalidRecurringRuleError(
                    f"day_of_month debe estar entre 1 y {DIA_DEL_MES_MAXIMO}, "
                    f"se recibió {self.day_of_month}."
                )
        elif self.day_of_month is not None:
            raise InvalidRecurringRuleError(f"La frecuencia {self.frequency} no usa day_of_month.")

        if requiere_dia_de_la_semana:
            if self.day_of_week is None:
                raise InvalidRecurringRuleError(
                    f"La frecuencia {self.frequency} requiere day_of_week."
                )
            if not 0 <= self.day_of_week <= DIA_DE_LA_SEMANA_MAXIMO:
                raise InvalidRecurringRuleError(
                    f"day_of_week debe estar entre 0 (lunes) y {DIA_DE_LA_SEMANA_MAXIMO} "
                    f"(domingo), se recibió {self.day_of_week}."
                )
        elif self.day_of_week is not None:
            raise InvalidRecurringRuleError(f"La frecuencia {self.frequency} no usa day_of_week.")

    @property
    def currency(self) -> str:
        return self.money.currency

    def vigente_en(self, dia: date) -> bool:
        """Si la regla está activa y el día cae dentro de su ventana de vigencia."""
        if not self.is_active or dia < self.starts_on:
            return False
        return self.ends_on is None or dia <= self.ends_on
