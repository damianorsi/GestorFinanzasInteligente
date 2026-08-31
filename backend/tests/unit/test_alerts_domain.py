"""Tests de la detección de desvíos presupuestarios.

Funciones puras: la fecha entra por parámetro, así que no hace falta congelar
el reloj ni levantar la base.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.domain.alerts import (
    DIAS_MINIMOS_PARA_PROYECTAR,
    detectar_desvio,
    porcentaje_proyectado,
    proyectar_gasto_del_mes,
)
from app.domain.enums import AlertType
from app.domain.value_objects import Money

MONEDA = "ARS"


def plata(monto: str) -> Money:
    return Money(Decimal(monto), MONEDA)


class TestProyeccion:
    def test_extrapola_el_ritmo_a_fin_de_mes(self) -> None:
        # Arrange: 60.000 en 10 de los 31 días de agosto.
        # Act
        proyectado = proyectar_gasto_del_mes(plata("60000.00"), date(2026, 8, 10))

        # Assert: 60.000 * 31 / 10.
        assert proyectado == plata("186000.00")

    def test_a_fin_de_mes_la_proyeccion_es_lo_gastado(self) -> None:
        # Arrange / Act
        proyectado = proyectar_gasto_del_mes(plata("120000.00"), date(2026, 8, 31))

        # Assert: no queda mes por delante que extrapolar.
        assert proyectado == plata("120000.00")

    def test_usa_los_dias_reales_de_cada_mes(self) -> None:
        # Arrange: el mismo gasto y el mismo día, en febrero y en agosto.
        # Act
        febrero = proyectar_gasto_del_mes(plata("10000.00"), date(2026, 2, 10))
        agosto = proyectar_gasto_del_mes(plata("10000.00"), date(2026, 8, 10))

        # Assert: febrero tiene 28 días, así que proyecta menos.
        assert febrero == plata("28000.00")
        assert agosto == plata("31000.00")

    def test_el_porcentaje_proyectado_tiene_dos_decimales(self) -> None:
        # Arrange / Act
        porcentaje = porcentaje_proyectado(plata("60000.00"), plata("100000.00"), date(2026, 8, 10))

        # Assert: 186.000 sobre 100.000.
        assert porcentaje == Decimal("186.00")

    def test_un_tope_en_cero_no_divide_por_cero(self) -> None:
        # Act / Assert
        assert porcentaje_proyectado(plata("100.00"), plata("0.00"), date(2026, 8, 10)) == Decimal(
            "0.00"
        )


class TestDeteccion:
    def test_avisa_cuando_ya_se_paso(self) -> None:
        # Act
        tipo = detectar_desvio(plata("120000.00"), plata("100000.00"), date(2026, 8, 20))

        # Assert
        assert tipo is AlertType.BUDGET_EXCEEDED

    def test_avisa_antes_de_pasarse_si_el_ritmo_no_da(self) -> None:
        # Arrange: 60.000 de 100.000 al día 10 proyecta 186%.
        # Act
        tipo = detectar_desvio(plata("60000.00"), plata("100000.00"), date(2026, 8, 10))

        # Assert: es lo que hace proactiva a la feature. Todavía se corrige.
        assert tipo is AlertType.BUDGET_AT_RISK

    def test_pasarse_gana_sobre_ir_camino_a_pasarse(self) -> None:
        # Arrange: gastado por encima del tope y encima con ritmo alto.
        # Act
        tipo = detectar_desvio(plata("150000.00"), plata("100000.00"), date(2026, 8, 10))

        # Assert: son excluyentes. Emitir las dos sería decir dos veces lo
        # mismo con distinta urgencia.
        assert tipo is AlertType.BUDGET_EXCEEDED

    def test_un_ritmo_que_llega_justo_no_dispara_alerta(self) -> None:
        # Arrange: 32.000 de 100.000 al día 10 proyecta 99,2%.
        # Act
        tipo = detectar_desvio(plata("32000.00"), plata("100000.00"), date(2026, 8, 10))

        # Assert
        assert tipo is None

    def test_un_desvio_chico_no_dispara_alerta(self) -> None:
        # Arrange: proyecta 105%, dentro del margen del propio método.
        # Act
        tipo = detectar_desvio(plata("33870.00"), plata("100000.00"), date(2026, 8, 10))

        # Assert: avisar por un 5% sería alarmismo y enseña a ignorar avisos.
        assert tipo is None

    @pytest.mark.parametrize("dia", [1, 2, 3, 4])
    def test_no_proyecta_en_los_primeros_dias_del_mes(self, dia: int) -> None:
        # Arrange: una compra grande el día 2 proyectaría quince veces el tope.
        # Act
        tipo = detectar_desvio(plata("30000.00"), plata("100000.00"), date(2026, 8, dia))

        # Assert: con tan pocos días el ritmo no dice nada sobre el mes.
        assert tipo is None
        assert dia < DIAS_MINIMOS_PARA_PROYECTAR

    def test_pero_si_ya_se_paso_avisa_aunque_sea_dia_1(self) -> None:
        # Act
        tipo = detectar_desvio(plata("120000.00"), plata("100000.00"), date(2026, 8, 1))

        # Assert: haberse pasado es un hecho, no una proyección.
        assert tipo is AlertType.BUDGET_EXCEEDED

    def test_sin_gasto_no_hay_alerta(self) -> None:
        # Act / Assert
        assert detectar_desvio(plata("0.00"), plata("100000.00"), date(2026, 8, 20)) is None
