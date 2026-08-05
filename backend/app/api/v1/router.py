"""Router agregador de la API v1.

Los routers de negocio se van sumando acá a medida que avanzan las fases:
auth (3), categories (4), transactions (5), reports (6), budgets (7),
chat (10), recurring-rules (12).
"""

from __future__ import annotations

from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1")
