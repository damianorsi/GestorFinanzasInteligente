"""Router agregador de la API v1.

Los routers de negocio se van sumando acá a medida que avanzan las fases:
categories (4), transactions (5), reports (6), budgets (7), chat (10),
recurring-rules (12).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import (
    auth,
    budgets,
    categories,
    chat,
    reports,
    transactions,
    users,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(categories.router)
api_router.include_router(transactions.router)
api_router.include_router(reports.router)
api_router.include_router(budgets.router)
api_router.include_router(chat.router)
