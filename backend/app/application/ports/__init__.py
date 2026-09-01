"""Puertos (interfaces Protocol) que implementa infrastructure."""

from app.application.ports.budget_alert_repository import BudgetAlertRepository
from app.application.ports.budget_repository import BudgetRepository
from app.application.ports.category_repository import CategoryRepository
from app.application.ports.chat_agent import ChatAgent
from app.application.ports.chat_repository import ChatRepository
from app.application.ports.clock import Clock
from app.application.ports.password_hasher import PasswordHasher
from app.application.ports.receipt_reader import ReceiptReader
from app.application.ports.receipt_scan_repository import ReceiptScanRepository
from app.application.ports.recurring_occurrence_repository import RecurringOccurrenceRepository
from app.application.ports.recurring_rule_repository import RecurringRuleRepository
from app.application.ports.refresh_token_repository import RefreshTokenRepository
from app.application.ports.report_repository import ReportRepository
from app.application.ports.savings_goal_repository import SavingsGoalRepository
from app.application.ports.token_service import TokenService
from app.application.ports.transaction_repository import TransactionRepository
from app.application.ports.user_repository import UserRepository

__all__ = [
    "BudgetAlertRepository",
    "BudgetRepository",
    "CategoryRepository",
    "ChatAgent",
    "ChatRepository",
    "Clock",
    "PasswordHasher",
    "ReceiptReader",
    "ReceiptScanRepository",
    "RecurringOccurrenceRepository",
    "RecurringRuleRepository",
    "RefreshTokenRepository",
    "ReportRepository",
    "SavingsGoalRepository",
    "TokenService",
    "TransactionRepository",
    "UserRepository",
]
