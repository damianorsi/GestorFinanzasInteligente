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
from app.application.dtos.chat import (
    AssistantAnswer,
    ChatMessage,
    TemporalContext,
    TokenUsage,
)
from app.application.dtos.pagination import (
    LIMITE_MAXIMO,
    LIMITE_POR_DEFECTO,
    Page,
    PaginatedResult,
)
from app.application.dtos.receipts import (
    UMBRAL_DE_CONFIANZA_BAJA,
    ExtractedReceipt,
    ReceiptDraft,
)
from app.application.dtos.recurring import (
    GenerationResult,
    UpcomingOccurrence,
    UpcomingSummary,
)
from app.application.dtos.reports import (
    CategoryBreakdown,
    CategoryTotal,
    MonthlyTotal,
    MonthlyTrend,
    PeriodSummary,
)
from app.application.dtos.savings import SavingsGoalProgress, SavingsProjection
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
    "UMBRAL_DE_CONFIANZA_BAJA",
    "AssistantAnswer",
    "BudgetCopyResult",
    "BudgetProgress",
    "BudgetProgressReport",
    "CategoryBreakdown",
    "CategoryTotal",
    "CategoryUsage",
    "ChatMessage",
    "ExtractedReceipt",
    "GenerationResult",
    "IssuedToken",
    "MonthlyTotal",
    "MonthlyTrend",
    "Page",
    "PaginatedResult",
    "PeriodSummary",
    "ReceiptDraft",
    "SavingsGoalProgress",
    "SavingsProjection",
    "SkippedBudget",
    "SortCriterion",
    "SortDirection",
    "SortField",
    "StoredRefreshToken",
    "TemporalContext",
    "TokenClaims",
    "TokenPair",
    "TokenType",
    "TokenUsage",
    "TransactionExportRow",
    "TransactionFilters",
    "UnbudgetedSpending",
    "UpcomingOccurrence",
    "UpcomingSummary",
    "UserCredentials",
]
