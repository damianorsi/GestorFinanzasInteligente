"""Dependencias compartidas por los endpoints.

Acá se arma el cableado: los casos de uso reciben los puertos y este módulo es
el único que sabe qué implementación concreta va en cada uno.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import timedelta
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos import TokenType
from app.application.exceptions import InvalidTokenError
from app.application.ports import (
    BudgetRepository,
    CategoryRepository,
    ChatAgent,
    ChatRepository,
    Clock,
    PasswordHasher,
    RecurringOccurrenceRepository,
    RecurringRuleRepository,
    RefreshTokenRepository,
    ReportRepository,
    TokenService,
    TransactionRepository,
    UserRepository,
)
from app.application.use_cases.auth.login_user import LoginUser
from app.application.use_cases.auth.logout_user import LogoutUser
from app.application.use_cases.auth.refresh_tokens import RefreshTokens
from app.application.use_cases.auth.register_user import RegisterUser
from app.application.use_cases.budgets import (
    CopyBudgets,
    CreateBudget,
    DeleteBudget,
    GetBudgetProgress,
    ListBudgets,
    UpdateBudget,
)
from app.application.use_cases.categories import (
    CreateCategory,
    DeleteCategory,
    GetCategory,
    ListCategories,
    UpdateCategory,
)
from app.application.use_cases.chat import AskAssistant, GetChatHistory
from app.application.use_cases.reports import (
    GetCategoryBreakdown,
    GetMonthlyTrend,
    GetPeriodSummary,
)
from app.application.use_cases.transactions import (
    CreateTransaction,
    DeleteTransaction,
    ExportTransactions,
    GetTransaction,
    ListTransactions,
    UpdateTransaction,
)
from app.core.config import Settings, get_settings
from app.domain.entities import User
from app.infrastructure.assistant import DependenciasDelAsistente, LangChainAssistant
from app.infrastructure.clock import get_clock
from app.infrastructure.db.repositories import (
    SqlAlchemyBudgetRepository,
    SqlAlchemyCategoryRepository,
    SqlAlchemyChatRepository,
    SqlAlchemyRecurringOccurrenceRepository,
    SqlAlchemyRecurringRuleRepository,
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemyReportRepository,
    SqlAlchemyTransactionRepository,
    SqlAlchemyUserRepository,
)
from app.infrastructure.db.session import session_scope
from app.infrastructure.security import Argon2Hasher, JwtTokenService

# `auto_error=False` para poder devolver el contrato de error propio en vez del
# `{"detail": ...}` que arma FastAPI por su cuenta.
_bearer = HTTPBearer(auto_error=False, description="Token de acceso JWT.")


async def get_db() -> AsyncIterator[AsyncSession]:
    """Sesión de base de datos con alcance de request."""
    async with session_scope() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


# --- Servicios sin estado (una instancia para todo el proceso) --------------
@lru_cache(maxsize=1)
def get_password_hasher() -> PasswordHasher:
    """El hasher se cachea: construirlo calcula el hash descartable, que es caro."""
    settings = get_settings()
    return Argon2Hasher(
        time_cost=settings.argon2_time_cost,
        memory_cost_kib=settings.argon2_memory_cost_kib,
        parallelism=settings.argon2_parallelism,
    )


@lru_cache(maxsize=1)
def get_token_service() -> TokenService:
    settings = get_settings()
    return JwtTokenService(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_ttl=timedelta(minutes=settings.access_token_expire_minutes),
        refresh_ttl=timedelta(days=settings.refresh_token_expire_days),
        clock=get_clock(),
    )


def get_app_clock() -> Clock:
    return get_clock()


# --- Repositorios (uno por request, atados a su sesión) --------------------
def get_user_repository(session: DbSession) -> UserRepository:
    return SqlAlchemyUserRepository(session)


def get_category_repository(session: DbSession) -> CategoryRepository:
    return SqlAlchemyCategoryRepository(session)


def get_refresh_token_repository(session: DbSession) -> RefreshTokenRepository:
    return SqlAlchemyRefreshTokenRepository(session)


def get_transaction_repository(session: DbSession) -> TransactionRepository:
    return SqlAlchemyTransactionRepository(session)


def get_occurrence_repository(session: DbSession) -> RecurringOccurrenceRepository:
    return SqlAlchemyRecurringOccurrenceRepository(session)


def get_report_repository(session: DbSession) -> ReportRepository:
    return SqlAlchemyReportRepository(session)


def get_budget_repository(session: DbSession) -> BudgetRepository:
    return SqlAlchemyBudgetRepository(session)


def get_chat_repository(session: DbSession) -> ChatRepository:
    return SqlAlchemyChatRepository(session)


def get_recurring_rule_repository(session: DbSession) -> RecurringRuleRepository:
    return SqlAlchemyRecurringRuleRepository(session)


Users = Annotated[UserRepository, Depends(get_user_repository)]
Categories = Annotated[CategoryRepository, Depends(get_category_repository)]
Transactions = Annotated[TransactionRepository, Depends(get_transaction_repository)]
Occurrences = Annotated[RecurringOccurrenceRepository, Depends(get_occurrence_repository)]
Reports = Annotated[ReportRepository, Depends(get_report_repository)]
Budgets = Annotated[BudgetRepository, Depends(get_budget_repository)]
Chats = Annotated[ChatRepository, Depends(get_chat_repository)]
Rules = Annotated[RecurringRuleRepository, Depends(get_recurring_rule_repository)]
RefreshTokens_ = Annotated[RefreshTokenRepository, Depends(get_refresh_token_repository)]
Hasher = Annotated[PasswordHasher, Depends(get_password_hasher)]
Tokens = Annotated[TokenService, Depends(get_token_service)]
AppClock = Annotated[Clock, Depends(get_app_clock)]


# --- Casos de uso ----------------------------------------------------------
def get_register_user(users: Users, categories: Categories, hasher: Hasher) -> RegisterUser:
    return RegisterUser(users=users, categories=categories, hasher=hasher)


def get_login_user(
    users: Users, refresh: RefreshTokens_, hasher: Hasher, tokens: Tokens, clock: AppClock
) -> LoginUser:
    return LoginUser(users=users, refresh_tokens=refresh, hasher=hasher, tokens=tokens, clock=clock)


def get_refresh_tokens(
    users: Users, refresh: RefreshTokens_, tokens: Tokens, clock: AppClock
) -> RefreshTokens:
    return RefreshTokens(users=users, refresh_tokens=refresh, tokens=tokens, clock=clock)


def get_logout_user(refresh: RefreshTokens_, tokens: Tokens, clock: AppClock) -> LogoutUser:
    return LogoutUser(refresh_tokens=refresh, tokens=tokens, clock=clock)


def get_list_categories(categories: Categories) -> ListCategories:
    return ListCategories(categories)


def get_get_category(categories: Categories) -> GetCategory:
    return GetCategory(categories)


def get_create_category(categories: Categories) -> CreateCategory:
    return CreateCategory(categories)


def get_update_category(categories: Categories) -> UpdateCategory:
    return UpdateCategory(categories)


def get_delete_category(categories: Categories) -> DeleteCategory:
    return DeleteCategory(categories)


def get_list_transactions(transactions: Transactions) -> ListTransactions:
    return ListTransactions(transactions)


def get_get_transaction(transactions: Transactions) -> GetTransaction:
    return GetTransaction(transactions)


def get_create_transaction(
    transactions: Transactions, categories: Categories, settings: AppSettings
) -> CreateTransaction:
    return CreateTransaction(
        transactions=transactions,
        categories=categories,
        supported_currencies=settings.supported_currencies_set,
        default_currency=settings.default_currency,
    )


def get_update_transaction(
    transactions: Transactions, categories: Categories, settings: AppSettings
) -> UpdateTransaction:
    return UpdateTransaction(
        transactions=transactions,
        categories=categories,
        supported_currencies=settings.supported_currencies_set,
        default_currency=settings.default_currency,
    )


def get_delete_transaction(
    transactions: Transactions, occurrences: Occurrences
) -> DeleteTransaction:
    return DeleteTransaction(transactions=transactions, occurrences=occurrences)


def get_export_transactions(
    transactions: Transactions, categories: Categories, settings: AppSettings
) -> ExportTransactions:
    return ExportTransactions(
        transactions=transactions,
        categories=categories,
        max_rows=settings.export_max_rows,
    )


def get_period_summary(
    reports: Reports, clock: AppClock, settings: AppSettings
) -> GetPeriodSummary:
    return GetPeriodSummary(
        reports=reports,
        clock=clock,
        supported_currencies=settings.supported_currencies_set,
        default_currency=settings.default_currency,
    )


def get_category_breakdown(
    reports: Reports, clock: AppClock, settings: AppSettings
) -> GetCategoryBreakdown:
    return GetCategoryBreakdown(
        reports=reports,
        clock=clock,
        supported_currencies=settings.supported_currencies_set,
        default_currency=settings.default_currency,
    )


def _presupuestos(
    budgets: Budgets, categories: Categories, settings: AppSettings
) -> tuple[BudgetRepository, CategoryRepository, frozenset[str], str]:
    return (
        budgets,
        categories,
        settings.supported_currencies_set,
        settings.default_currency,
    )


def get_list_budgets(
    budgets: Budgets, categories: Categories, settings: AppSettings
) -> ListBudgets:
    return ListBudgets(*_presupuestos(budgets, categories, settings))


def get_create_budget(
    budgets: Budgets, categories: Categories, settings: AppSettings
) -> CreateBudget:
    return CreateBudget(*_presupuestos(budgets, categories, settings))


def get_update_budget(
    budgets: Budgets, categories: Categories, settings: AppSettings
) -> UpdateBudget:
    return UpdateBudget(*_presupuestos(budgets, categories, settings))


def get_delete_budget(
    budgets: Budgets, categories: Categories, settings: AppSettings
) -> DeleteBudget:
    return DeleteBudget(*_presupuestos(budgets, categories, settings))


def get_copy_budgets(
    budgets: Budgets, categories: Categories, settings: AppSettings
) -> CopyBudgets:
    return CopyBudgets(*_presupuestos(budgets, categories, settings))


def get_budget_progress(
    budgets: Budgets, categories: Categories, reports: Reports, settings: AppSettings
) -> GetBudgetProgress:
    return GetBudgetProgress(
        budgets=budgets,
        categories=categories,
        reports=reports,
        supported_currencies=settings.supported_currencies_set,
        default_currency=settings.default_currency,
    )


def get_monthly_trend(reports: Reports, clock: AppClock, settings: AppSettings) -> GetMonthlyTrend:
    return GetMonthlyTrend(
        reports=reports,
        clock=clock,
        supported_currencies=settings.supported_currencies_set,
        default_currency=settings.default_currency,
    )


def get_assistant_agent(
    reports: Reports,
    budgets: Budgets,
    categories: Categories,
    transactions: Transactions,
    rules: Rules,
    clock: AppClock,
    settings: AppSettings,
) -> ChatAgent:
    """Construye el agente con las dependencias de la request.

    Las herramientas se arman después, dentro de `answer`, con el `user_id` ya
    cerrado: acá solo se cablean los casos de uso que van a respaldarlas.
    """
    monedas = settings.supported_currencies_set
    moneda = settings.default_currency
    return LangChainAssistant(
        deps=DependenciasDelAsistente(
            resumen=GetPeriodSummary(reports, clock, monedas, moneda),
            por_categoria=GetCategoryBreakdown(reports, clock, monedas, moneda),
            tendencia=GetMonthlyTrend(reports, clock, monedas, moneda),
            presupuestos=GetBudgetProgress(budgets, categories, reports, monedas, moneda),
            movimientos=ListTransactions(transactions),
            reglas=rules,
            default_currency=moneda,
        ),
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        max_tokens=settings.openai_max_tokens,
        max_iterations=settings.agent_max_iterations,
        timeout_seconds=settings.openai_timeout_seconds,
    )


def get_ask_assistant(
    agent: Annotated[ChatAgent, Depends(get_assistant_agent)],
    chat: Chats,
    clock: AppClock,
    settings: AppSettings,
) -> AskAssistant:
    return AskAssistant(
        agent=agent,
        chat=chat,
        clock=clock,
        history_window=settings.chat_history_window,
        rate_limit_per_hour=settings.chat_rate_limit_per_hour,
    )


def get_chat_history(chat: Chats, settings: AppSettings) -> GetChatHistory:
    return GetChatHistory(chat, settings.chat_history_window)


# --- Usuario autenticado ---------------------------------------------------
async def get_current_user(
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    users: Users,
    tokens: Tokens,
) -> User:
    """Resuelve el usuario del token, o corta con 401.

    Es la única fuente del `user_id` para todo el resto de la aplicación: nunca
    se confía en un identificador que venga del body, la query o el prompt del
    chat.
    """
    if credenciales is None or not credenciales.credentials:
        raise InvalidTokenError("Falta el token de acceso.")

    claims = tokens.decode(credenciales.credentials)

    # Un refresh token dura siete días; sin esta comprobación serviría para
    # autenticar requests como si fuera un access token de quince minutos.
    if claims.token_type is not TokenType.ACCESS:
        raise InvalidTokenError("Se requiere un token de acceso.")

    usuario = await users.get_by_id(claims.user_id)
    if usuario is None or not usuario.is_active:
        raise InvalidTokenError("La cuenta ya no está disponible.")

    return usuario


CurrentUser = Annotated[User, Depends(get_current_user)]
