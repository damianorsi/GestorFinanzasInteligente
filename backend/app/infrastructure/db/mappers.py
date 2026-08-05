"""Traducción entre modelos ORM y entidades de dominio.

Vive en infrastructure porque es la capa que conoce las dos formas. El dominio
no sabe que existe SQLAlchemy y los modelos no saben de invariantes.

Nota sobre `password_hash`: no es parte de la entidad `User` porque no es una
regla de negocio sino un detalle de autenticación. Se pasa aparte al construir
el modelo.
"""

from __future__ import annotations

from app.domain.entities import (
    Budget,
    Category,
    RecurringOccurrence,
    RecurringRule,
    Transaction,
    User,
)
from app.domain.value_objects import Money
from app.infrastructure.db.models import (
    BudgetModel,
    CategoryModel,
    RecurringOccurrenceModel,
    RecurringRuleModel,
    TransactionModel,
    UserModel,
)


# --- Usuarios --------------------------------------------------------------
def usuario_a_dominio(model: UserModel) -> User:
    return User(
        id=model.id,
        email=model.email,
        full_name=model.full_name,
        is_active=model.is_active,
    )


def usuario_a_modelo(entity: User, password_hash: str) -> UserModel:
    return UserModel(
        email=entity.email,
        full_name=entity.full_name,
        is_active=entity.is_active,
        password_hash=password_hash,
    )


# --- Categorías ------------------------------------------------------------
def categoria_a_dominio(model: CategoryModel) -> Category:
    return Category(
        id=model.id,
        user_id=model.user_id,
        name=model.name,
        type=model.type,
        color=model.color,
        is_default=model.is_default,
    )


def categoria_a_modelo(entity: Category) -> CategoryModel:
    return CategoryModel(
        user_id=entity.user_id,
        name=entity.name,
        type=entity.type,
        color=entity.color,
        is_default=entity.is_default,
    )


# --- Movimientos -----------------------------------------------------------
def movimiento_a_dominio(model: TransactionModel) -> Transaction:
    return Transaction(
        id=model.id,
        user_id=model.user_id,
        category_id=model.category_id,
        type=model.type,
        money=Money(model.amount, model.currency),
        occurred_on=model.occurred_on,
        description=model.description,
        recurring_rule_id=model.recurring_rule_id,
    )


def movimiento_a_modelo(entity: Transaction) -> TransactionModel:
    return TransactionModel(
        user_id=entity.user_id,
        category_id=entity.category_id,
        type=entity.type,
        amount=entity.money.amount,
        currency=entity.money.currency,
        occurred_on=entity.occurred_on,
        description=entity.description,
        recurring_rule_id=entity.recurring_rule_id,
    )


# --- Presupuestos ----------------------------------------------------------
def presupuesto_a_dominio(model: BudgetModel) -> Budget:
    return Budget(
        id=model.id,
        user_id=model.user_id,
        category_id=model.category_id,
        period_month=model.period_month,
        limit=Money(model.amount, model.currency),
    )


def presupuesto_a_modelo(entity: Budget) -> BudgetModel:
    return BudgetModel(
        user_id=entity.user_id,
        category_id=entity.category_id,
        period_month=entity.period_month,
        amount=entity.limit.amount,
        currency=entity.limit.currency,
    )


# --- Reglas recurrentes ----------------------------------------------------
def regla_a_dominio(model: RecurringRuleModel) -> RecurringRule:
    return RecurringRule(
        id=model.id,
        user_id=model.user_id,
        category_id=model.category_id,
        type=model.type,
        money=Money(model.amount, model.currency),
        frequency=model.frequency,
        starts_on=model.starts_on,
        description=model.description,
        day_of_month=model.day_of_month,
        day_of_week=model.day_of_week,
        ends_on=model.ends_on,
        is_active=model.is_active,
    )


def regla_a_modelo(entity: RecurringRule) -> RecurringRuleModel:
    return RecurringRuleModel(
        user_id=entity.user_id,
        category_id=entity.category_id,
        type=entity.type,
        amount=entity.money.amount,
        currency=entity.money.currency,
        description=entity.description,
        frequency=entity.frequency,
        day_of_month=entity.day_of_month,
        day_of_week=entity.day_of_week,
        starts_on=entity.starts_on,
        ends_on=entity.ends_on,
        is_active=entity.is_active,
    )


# --- Ocurrencias -----------------------------------------------------------
def ocurrencia_a_dominio(model: RecurringOccurrenceModel) -> RecurringOccurrence:
    return RecurringOccurrence(
        id=model.id,
        rule_id=model.rule_id,
        occurred_on=model.occurred_on,
        status=model.status,
        transaction_id=model.transaction_id,
    )


def ocurrencia_a_modelo(entity: RecurringOccurrence) -> RecurringOccurrenceModel:
    return RecurringOccurrenceModel(
        rule_id=entity.rule_id,
        occurred_on=entity.occurred_on,
        status=entity.status,
        transaction_id=entity.transaction_id,
    )
