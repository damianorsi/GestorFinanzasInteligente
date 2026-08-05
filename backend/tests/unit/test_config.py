"""Tests de la configuración de la aplicación."""

from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.core.config import INSECURE_DEFAULT_SECRET, Settings


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "app_env": "test",
        "jwt_secret_key": "x" * 40,
        "default_currency": "ARS",
        "supported_currencies": "ARS",
        "app_timezone": "America/Argentina/Buenos_Aires",
        "cors_origins": "http://localhost:5173,http://localhost:8080",
        # Los tests de producción necesitan partir de valores válidos para poder
        # invalidar uno solo por vez.
        "argon2_time_cost": 3,
        "argon2_memory_cost_kib": 65536,
        "argon2_parallelism": 4,
    }
    base.update(overrides)
    return Settings(**base)


def test_cors_origins_se_parsea_separado_por_comas() -> None:
    # Arrange
    settings = _settings(cors_origins="http://a.com, http://b.com ,")

    # Act
    origins = settings.cors_origins_list

    # Assert
    assert origins == ["http://a.com", "http://b.com"]


def test_supported_currencies_se_normaliza_a_mayusculas() -> None:
    # Arrange
    settings = _settings(supported_currencies="ars, usd", default_currency="ars")

    # Act
    currencies = settings.supported_currencies_set

    # Assert
    assert currencies == frozenset({"ARS", "USD"})


def test_default_currency_debe_estar_entre_las_soportadas() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValidationError, match="SUPPORTED_CURRENCIES"):
        _settings(default_currency="USD", supported_currencies="ARS")


def test_v1_no_habilita_usd() -> None:
    """Salvaguarda de la decisión de alcance: USD no está habilitado en v1."""
    # Arrange
    settings = _settings()

    # Act / Assert
    assert settings.supported_currencies_set == frozenset({"ARS"})
    assert "USD" not in settings.supported_currencies_set


def test_timezone_invalida_falla() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValidationError, match="APP_TIMEZONE"):
        _settings(app_timezone="Marte/Olympus_Mons")


def test_timezone_devuelve_zoneinfo_de_buenos_aires() -> None:
    # Arrange
    settings = _settings()

    # Act
    tz = settings.timezone

    # Assert
    assert tz == ZoneInfo("America/Argentina/Buenos_Aires")


def test_produccion_rechaza_el_secreto_de_ejemplo() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValidationError, match="valor de ejemplo"):
        _settings(app_env="production", jwt_secret_key=INSECURE_DEFAULT_SECRET)


def test_produccion_rechaza_secretos_cortos() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValidationError, match="32 caracteres"):
        _settings(app_env="production", jwt_secret_key="corto")


def test_produccion_rechaza_un_argon2_barato() -> None:
    """Impide que la configuración de la suite de tests llegue a producción.

    Sin esta validación, arrastrar ARGON2_TIME_COST=1 dejaría las contraseñas
    con un hashing trivial de romper y nada lo delataría en runtime.
    """
    # Arrange / Act / Assert
    with pytest.raises(ValidationError, match="ARGON2_TIME_COST"):
        _settings(app_env="production", jwt_secret_key="x" * 40, argon2_time_cost=1)

    with pytest.raises(ValidationError, match="ARGON2_MEMORY_COST_KIB"):
        _settings(app_env="production", jwt_secret_key="x" * 40, argon2_memory_cost_kib=8)


def test_produccion_acepta_los_parametros_por_defecto_de_argon2() -> None:
    # Arrange / Act
    settings = _settings(app_env="production", jwt_secret_key="x" * 40)

    # Assert
    assert settings.is_production
    assert settings.argon2_memory_cost_kib >= 19456


def test_desarrollo_tolera_el_secreto_de_ejemplo() -> None:
    """En desarrollo el default sirve; la restricción es solo de producción."""
    # Arrange
    settings = _settings(app_env="development", jwt_secret_key=INSECURE_DEFAULT_SECRET)

    # Act / Assert
    assert settings.is_production is False
