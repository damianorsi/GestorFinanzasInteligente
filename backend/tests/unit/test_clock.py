"""Tests del reloj de la aplicación.

Buenos Aires es UTC-3 todo el año (Argentina no aplica horario de verano desde
2009), así que las fechas de estos tests no dependen de la época del año.
"""

from __future__ import annotations

from datetime import UTC, date
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from app.infrastructure.clock import SystemClock

BUENOS_AIRES = ZoneInfo("America/Argentina/Buenos_Aires")


@freeze_time("2026-08-05 02:30:00")
def test_antes_de_las_3_utc_hoy_es_el_dia_anterior_en_buenos_aires() -> None:
    """02:30 UTC son las 23:30 del día anterior en Argentina.

    Este es exactamente el caso que rompería si "hoy" se calculara en UTC: el
    job de recurrentes generaría los movimientos del día equivocado.
    """
    # Arrange
    reloj = SystemClock(BUENOS_AIRES)

    # Act / Assert
    assert reloj.today() == date(2026, 8, 4)


@freeze_time("2026-08-05 03:10:00")
def test_despues_de_las_3_utc_hoy_ya_es_el_dia_nuevo() -> None:
    # Arrange
    reloj = SystemClock(BUENOS_AIRES)

    # Act / Assert
    assert reloj.today() == date(2026, 8, 5)


@freeze_time("2026-08-05 02:30:00")
def test_now_devuelve_un_instante_con_zona_horaria() -> None:
    # Arrange
    reloj = SystemClock(BUENOS_AIRES)

    # Act
    ahora = reloj.now()

    # Assert
    assert ahora.tzinfo is not None
    assert ahora.hour == 23
    assert ahora.day == 4


@freeze_time("2026-08-05 02:30:00")
def test_utc_now_es_utc_para_los_timestamps_de_auditoria() -> None:
    """Las fechas de negocio van en hora local; la auditoría va en UTC."""
    # Arrange / Act
    ahora = SystemClock.utc_now()

    # Assert
    assert ahora.tzinfo == UTC
    assert ahora.hour == 2
    assert ahora.day == 5


@freeze_time("2026-12-31 23:30:00")
def test_fin_de_anio_utc_sigue_siendo_el_31_en_buenos_aires() -> None:
    # Arrange
    reloj = SystemClock(BUENOS_AIRES)

    # Act / Assert
    assert reloj.today() == date(2026, 12, 31)
