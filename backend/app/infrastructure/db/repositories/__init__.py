"""Implementaciones de los puertos de persistencia."""

from app.infrastructure.db.repositories.budget_alert_repository import (
    SqlAlchemyBudgetAlertRepository,
)
from app.infrastructure.db.repositories.budget_repository import SqlAlchemyBudgetRepository
from app.infrastructure.db.repositories.category_repository import SqlAlchemyCategoryRepository
from app.infrastructure.db.repositories.chat_repository import SqlAlchemyChatRepository
from app.infrastructure.db.repositories.receipt_scan_repository import (
    SqlAlchemyReceiptScanRepository,
)
from app.infrastructure.db.repositories.recurring_occurrence_repository import (
    SqlAlchemyRecurringOccurrenceRepository,
)
from app.infrastructure.db.repositories.recurring_rule_repository import (
    SqlAlchemyRecurringRuleRepository,
)
from app.infrastructure.db.repositories.refresh_token_repository import (
    SqlAlchemyRefreshTokenRepository,
)
from app.infrastructure.db.repositories.report_repository import SqlAlchemyReportRepository
from app.infrastructure.db.repositories.savings_goal_repository import (
    SqlAlchemySavingsGoalRepository,
)
from app.infrastructure.db.repositories.transaction_repository import (
    SqlAlchemyTransactionRepository,
)
from app.infrastructure.db.repositories.user_repository import SqlAlchemyUserRepository

__all__ = [
    "SqlAlchemyBudgetAlertRepository",
    "SqlAlchemyBudgetRepository",
    "SqlAlchemyCategoryRepository",
    "SqlAlchemyChatRepository",
    "SqlAlchemyReceiptScanRepository",
    "SqlAlchemyRecurringOccurrenceRepository",
    "SqlAlchemyRecurringRuleRepository",
    "SqlAlchemyRefreshTokenRepository",
    "SqlAlchemyReportRepository",
    "SqlAlchemySavingsGoalRepository",
    "SqlAlchemyTransactionRepository",
    "SqlAlchemyUserRepository",
]
