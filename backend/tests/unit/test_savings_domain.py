"""Tests de la proyección de metas de ahorro (docs/PROMPT.md §21.3).

Funciones puras: la fecha entra por parámetro, así que no hace falta congelar
el reloj ni levantar la base.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.domain.entities import SavingsGoal
from app.domain.enums import GoalStatus
from app.domain.exceptions import InvalidSavingsGoalError
from app.domain.savings import (
    MESES_MINIMOS_DE_HISTORIAL,
    evaluar_estado,
    fecha_proyectada,
    meses_para_alcanzar,
    porcentaje_alcanzado,
    ritmo_mensual,
)
from app.domain.value_objects import Money

MONEDA = "ARS"
HOY = date(2026, 8, 10)


def plata(monto: str) -> Money:
    return Money(Decimal(monto), MONEDA)


class TestRitmo:
    def test_promedia_los_balances_mensuales(self) -> None:
        # Arrange / Act
        ritmo = ritmo_mensual([plata("100000.00"), plata("80000.00"), plata("60000.00")], MONEDA)

        # Assert
        assert ritmo == plata("80000.00")

    def test_un_mes_en_rojo_entra_en_el_promedio(self) -> None:
        # Arrange / Act
        ritmo = ritmo_mensual([plata("100000.00"), plata("-40000.00")], MONEDA)

        # Assert: excluirlo daría una proyección optimista que nadie pidió.
        assert ritmo == plata("30000.00")

    def test_sin_historial_suficiente_no_hay_ritmo(self) -> None:
        # Arrange: un solo mes, por debajo del mínimo.
        assert MESES_MINIMOS_DE_HISTORIAL == 2

        # Act
        ritmo = ritmo_mensual([plata("100000.00")], MONEDA)

        # Assert: con un solo dato, un mes con aguinaldo diría cualquier cosa.
        assert ritmo is None

    def test_sin_ningun_mes_tampoco(self) -> None:
        # Arrange / Act / Assert
        assert ritmo_mensual([], MONEDA) is None


class TestMesesParaAlcanzar:
    def test_redondea_hacia_arriba(self) -> None:
        # Arrange: faltan 250.000 a 100.000 por mes son 2,5 meses.
        # Act
        meses = meses_para_alcanzar(plata("250000.00"), plata("100000.00"))

        # Assert: medio mes de ahorro no compra media meta.
        assert meses == 3

    def test_con_ritmo_cero_no_se_llega_nunca(self) -> None:
        # Arrange / Act
        meses = meses_para_alcanzar(plata("250000.00"), plata("0.00"))

        # Assert: un número grande mentiría menos, pero mentiría igual.
        assert meses is None

    def test_con_ritmo_negativo_tampoco(self) -> None:
        # Arrange / Act / Assert
        assert meses_para_alcanzar(plata("250000.00"), plata("-5000.00")) is None

    def test_un_horizonte_absurdo_se_informa_como_inalcanzable(self) -> None:
        # Arrange: 1.000.000 a 100 por mes son 10.000 meses.
        # Act
        meses = meses_para_alcanzar(plata("1000000.00"), plata("100.00"))

        # Assert: "faltan 10.000 meses" se lee como un error, no como un dato.
        assert meses is None

    def test_sin_nada_pendiente_son_cero_meses(self) -> None:
        # Arrange / Act / Assert
        assert meses_para_alcanzar(plata("0.00"), plata("100000.00")) == 0


class TestFechaProyectada:
    def test_cae_en_el_primero_del_mes(self) -> None:
        # Arrange / Act
        cuando = fecha_proyectada(HOY, 3)

        # Assert: el ritmo es mensual; dar un día exacto fingiría precisión.
        assert cuando == date(2026, 11, 1)

    def test_cruza_el_fin_de_año(self) -> None:
        # Arrange / Act / Assert
        assert fecha_proyectada(date(2026, 11, 20), 4) == date(2027, 3, 1)


class TestEstado:
    def test_una_meta_cubierta_esta_alcanzada(self) -> None:
        # Arrange / Act
        estado = evaluar_estado(
            plata("2000000.00"), plata("2000000.00"), None, date(2026, 12, 1), HOY
        )

        # Assert: gana sobre todo lo demás, aunque el ritmo venga mal.
        assert estado is GoalStatus.ACHIEVED

    def test_llegar_despues_de_la_fecha_objetivo_es_riesgo(self) -> None:
        # Arrange: faltan 6 meses y la fecha objetivo es en 4.
        # Act
        estado = evaluar_estado(plata("500000.00"), plata("2000000.00"), 6, date(2026, 12, 15), HOY)

        # Assert
        assert estado is GoalStatus.AT_RISK

    def test_llegar_a_tiempo_es_ir_en_camino(self) -> None:
        # Arrange / Act
        estado = evaluar_estado(plata("500000.00"), plata("2000000.00"), 2, date(2026, 12, 15), HOY)

        # Assert
        assert estado is GoalStatus.ON_TRACK

    def test_sin_fecha_objetivo_no_se_llega_tarde(self) -> None:
        # Arrange / Act
        estado = evaluar_estado(plata("500000.00"), plata("2000000.00"), 40, None, HOY)

        # Assert: sin fecha no hay tarde ni temprano.
        assert estado is GoalStatus.ON_TRACK

    def test_sin_fecha_pero_sin_llegar_nunca_es_riesgo(self) -> None:
        # Arrange / Act
        estado = evaluar_estado(plata("500000.00"), plata("2000000.00"), None, None, HOY)

        # Assert: decir "vas bien" con ritmo cero o negativo sería falso.
        assert estado is GoalStatus.AT_RISK


class TestPorcentaje:
    def test_calcula_el_avance(self) -> None:
        # Arrange / Act / Assert
        assert porcentaje_alcanzado(plata("500000.00"), plata("2000000.00")) == Decimal("25.00")

    def test_no_recorta_arriba_de_cien(self) -> None:
        # Arrange / Act
        porcentaje = porcentaje_alcanzado(plata("2500000.00"), plata("2000000.00"))

        # Assert: haber juntado de más es información.
        assert porcentaje == Decimal("125.00")

    def test_un_acumulado_negativo_no_da_porcentaje_negativo(self) -> None:
        # Arrange: gastó más de lo que ingresó desde que arrancó la meta.
        # Act
        porcentaje = porcentaje_alcanzado(plata("-30000.00"), plata("2000000.00"))

        # Assert: un porcentaje negativo de una meta no significa nada.
        assert porcentaje == Decimal("0.00")


class TestEntidad:
    def test_exige_un_nombre(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(InvalidSavingsGoalError):
            SavingsGoal(
                user_id=1, name="   ", target=plata("100000.00"), starts_on=date(2026, 1, 1)
            )

    def test_exige_un_objetivo_positivo(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(InvalidSavingsGoalError):
            SavingsGoal(user_id=1, name="Viaje", target=plata("0.00"), starts_on=date(2026, 1, 1))

    def test_la_fecha_objetivo_no_puede_ser_anterior_al_inicio(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(InvalidSavingsGoalError):
            SavingsGoal(
                user_id=1,
                name="Viaje",
                target=plata("100000.00"),
                starts_on=date(2026, 6, 1),
                target_date=date(2026, 5, 1),
            )
