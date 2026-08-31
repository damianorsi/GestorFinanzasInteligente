"""Configuración de la aplicación, cargada desde variables de entorno."""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valor de ejemplo de `.env.example`. Sirve para desarrollo local, pero la
# aplicación se niega a arrancar con él en producción (ver _validar_produccion).
INSECURE_DEFAULT_SECRET = "cambiame_por_una_clave_larga_y_aleatoria"

# Pisos que se exigen en producción (recomendación de OWASP para Argon2id).
ARGON2_TIME_COST_MINIMO = 2
ARGON2_MEMORIA_MINIMA_KIB = 19456


class Settings(BaseSettings):
    """Configuración tipada de toda la aplicación.

    Las listas y conjuntos se declaran como `str` separado por comas y se
    exponen ya parseados vía propiedades. Motivo: pydantic-settings intenta
    interpretar los tipos complejos como JSON al leerlos del entorno, y
    `CORS_ORIGINS=http://a,http://b` explotaría con un error de parseo.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Aplicación --------------------------------------------------------
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    # --- Base de datos -----------------------------------------------------
    database_url: str = "mysql+aiomysql://finanzas:finanzas@db:3306/finanzas?charset=utf8mb4"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_recycle_seconds: int = 3600

    # --- Seguridad / JWT ---------------------------------------------------
    jwt_secret_key: str = INSECURE_DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Parámetros de Argon2id. Los defaults son los de argon2-cffi, alineados con
    # la recomendación de OWASP. Se exponen para poder bajarlos en la suite de
    # tests, donde el costo deliberado del hashing solo agrega segundos.
    argon2_time_cost: int = 3
    argon2_memory_cost_kib: int = 65536
    argon2_parallelism: int = 4

    # --- OpenAI / Asistente ------------------------------------------------
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"
    openai_max_tokens: int = 500
    openai_timeout_seconds: int = 30
    agent_max_iterations: int = 3
    chat_history_window: int = 6
    chat_rate_limit_per_hour: int = 20

    # --- Lectura de tickets (docs/PROMPT.md §21.1) --------------------------
    # Modelo con visión. Se separa de `openai_model` para poder usar uno más
    # capaz solo acá: leer un ticket arrugado es más difícil que redactar una
    # respuesta sobre datos ya agregados.
    openai_vision_model: str = "gpt-5-mini"
    receipt_max_size_mb: int = 8
    receipt_rate_limit_per_hour: int = 10

    # --- Exportación --------------------------------------------------------
    # Tope de filas por export. Se avisa al superarlo en vez de truncar: un CSV
    # recortado en silencio parece completo y es peor que un error.
    export_max_rows: int = 50000

    # --- Movimientos recurrentes -------------------------------------------
    recurring_job_hour: int = 3
    recurring_catchup_max_days: int = 90

    # --- Alertas proactivas (docs/PROMPT.md §21.2) -------------------------
    # Después del job de recurrentes: los movimientos que ese genera cuentan
    # para el presupuesto, y correr antes avisaría sobre un gasto incompleto.
    alerts_job_hour: int = 4
    # Gasto mínimo en una categoría sin tope para que valga la pena avisar.
    alerts_min_unbudgeted_amount: Decimal = Decimal("10000")
    # Tope de recomendaciones por corrida: cada una es una corrida completa
    # del agente, y sin techo el job podría gastar sin control.
    alerts_max_recommendations: int = 20

    # --- Localización (decisiones cerradas, ver docs/PROMPT.md §5) ----------
    app_timezone: str = "America/Argentina/Buenos_Aires"
    default_currency: str = "ARS"
    supported_currencies: str = "ARS"

    # --- Propiedades derivadas ---------------------------------------------
    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def supported_currencies_set(self) -> frozenset[str]:
        return frozenset(
            code.strip().upper() for code in self.supported_currencies.split(",") if code.strip()
        )

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.app_timezone)

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    # --- Validaciones ------------------------------------------------------
    @model_validator(mode="after")
    def _validar_moneda(self) -> Settings:
        if self.default_currency.upper() not in self.supported_currencies_set:
            raise ValueError(
                f"DEFAULT_CURRENCY={self.default_currency!r} no está en "
                f"SUPPORTED_CURRENCIES={self.supported_currencies!r}"
            )
        return self

    @model_validator(mode="after")
    def _validar_timezone(self) -> Settings:
        try:
            ZoneInfo(self.app_timezone)
        except Exception as exc:
            raise ValueError(f"APP_TIMEZONE={self.app_timezone!r} no es una zona válida") from exc
        return self

    @model_validator(mode="after")
    def _validar_produccion(self) -> Settings:
        """En producción no se tolera ningún secreto de ejemplo."""
        if not self.is_production:
            return self
        if self.jwt_secret_key == INSECURE_DEFAULT_SECRET:
            raise ValueError("JWT_SECRET_KEY tiene el valor de ejemplo; generá uno real")
        if len(self.jwt_secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY debe tener al menos 32 caracteres")
        # Sin esto, arrastrar por descuido la configuración de tests a producción
        # dejaría las contraseñas con un hashing barato de romper, y nada lo
        # delataría en runtime.
        if self.argon2_time_cost < ARGON2_TIME_COST_MINIMO:
            raise ValueError(
                f"ARGON2_TIME_COST debe ser al menos {ARGON2_TIME_COST_MINIMO} en producción"
            )
        if self.argon2_memory_cost_kib < ARGON2_MEMORIA_MINIMA_KIB:
            raise ValueError(
                f"ARGON2_MEMORY_COST_KIB debe ser al menos {ARGON2_MEMORIA_MINIMA_KIB} "
                "en producción"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Devuelve la configuración, cacheada para todo el proceso."""
    return Settings()
