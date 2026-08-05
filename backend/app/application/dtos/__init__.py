"""DTOs que cruzan la frontera de los casos de uso."""

from app.application.dtos.auth import (
    IssuedToken,
    StoredRefreshToken,
    TokenClaims,
    TokenPair,
    TokenType,
    UserCredentials,
)
from app.application.dtos.budgets import (
    BudgetCopyResult,
    BudgetProgress,
    BudgetProgressReport,
    SkippedBudget,
    UnbudgetedSpending,
)
from app.application.dtos.categories import CategoryUsage
from app.application.dtos.pagination import (
    LIMITE_MAXIMO,
    LIMITE_POR_DEFECTO,
    Page,
    PaginatedResult,
)
from app.application.dtos.reports import (
    CategoryBreakdown,
    CategoryTotal,
    MonthlyTotal,
    MonthlyTrend,
    PeriodSummary,
)
from app.application.dtos.transactions import (
    ORDEN_POR_DEFECTO,
    SortCriterion,
    SortDirection,
    SortField,
    TransactionExportRow,
    TransactionFilters,
)

__all__ = [
    "LIMITE_MAXIMO",
    "LIMITE_POR_DEFECTO",
    "ORDEN_POR_DEFECTO",
    "BudgetCopyResult",
    "BudgetProgress",
    "BudgetProgressReport",
    "CategoryBreakdown",
    "CategoryTotal",
    "CategoryUsage",
    "IssuedToken",
    "MonthlyTotal",
    "MonthlyTrend",
    "Page",
    "PaginatedResult",
    "PeriodSummary",
    "SkippedBudget",
    "SortCriterion",
    "SortDirection",
    "SortField",
    "StoredRefreshToken",
    "TokenClaims",
    "TokenPair",
    "TokenType",
    "TransactionExportRow",
    "TransactionFilters",
    "UnbudgetedSpending",
    "UserCredentials",
]
