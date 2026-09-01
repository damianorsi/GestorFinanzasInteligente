"""DTOs de metas de ahorro (docs/PROMPT.md §21.3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.enums import GoalStatus
from app.domain.value_objects import Money


@dataclass(frozen=True, slots=True)
class SavingsProjection:
    """La parte estimada del avance, separada de la parte medida.

    Va en su propio objeto y no aplanada en `SavingsGoalProgress` porque toda
    ella puede faltar a la vez: con menos de dos meses de historial no se
    proyecta nada. Tenerla aparte hace imposible mostrar una fecha estimada
    sin decir sobre cuántos meses se calculó.
    """

    monthly_rate: Money
    months_of_history: int
    # `None` cuando a ese ritmo no se llega nunca (promedio cero o negativo) o
    # cuando el horizonte es tan largo que informarlo no ayuda.
    months_to_target: int | None
    projected_date: date | None


@dataclass(frozen=True, slots=True)
class SavingsGoalProgress:
    """Avance de una meta: lo que ya pasó, y opcionalmente lo que se estima."""

    goal_id: int
    name: str
    target: Money
    saved: Money
    remaining: Money
    percentage: Decimal
    starts_on: date
    target_date: date | None
    # `None` cuando no hay con qué decidir: sin historial suficiente, «no
    # sabemos» no es lo mismo que `AT_RISK`, y forzar uno de los tres estados
    # convertiría una falta de datos en un diagnóstico. `ACHIEVED` sí se
    # informa siempre, porque se mide y no se estima.
    status: GoalStatus | None
    # `None` cuando falta historial. La pantalla dice que faltan datos en vez
    # de proyectar (§21.3).
    projection: SavingsProjection | None
