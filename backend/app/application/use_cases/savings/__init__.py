"""Casos de uso de metas de ahorro (docs/PROMPT.md §21.3)."""

from app.application.use_cases.savings.goal_progress import GetSavingsGoalsProgress
from app.application.use_cases.savings.manage_goals import (
    CreateSavingsGoal,
    DeleteSavingsGoal,
    ListSavingsGoals,
    UpdateSavingsGoal,
)

__all__ = [
    "CreateSavingsGoal",
    "DeleteSavingsGoal",
    "GetSavingsGoalsProgress",
    "ListSavingsGoals",
    "UpdateSavingsGoal",
]
