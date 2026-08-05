"""Tests de las invariantes de las entidades de dominio."""

from __future__ import annotations

from datetime import date

import pytest

from app.domain.entities import (
    Budget,
    Category,
    RecurringOccurrence,
    RecurringRule,
    Transaction,
    User,
)
from app.domain.enums import (
    OccurrenceStatus,
    RecurrenceFrequency,
    TransactionType,
)
from app.domain.exceptions import (
    InvalidBudgetError,
    InvalidCategoryError,
    InvalidRecurringRuleError,
    InvalidTransactionError,
    InvalidUserError,
)
from app.domain.value_objects import Money

CIEN_PESOS = Money.of("100.00", "ARS")


class TestUser:
    def test_normaliza_el_email(self) -> None:
        # Arrange / Act
        usuario = User(email="  Damian@Ejemplo.COM  ", full_name="  Damián Orsi  ")

        # Assert
        assert usuario.email == "damian@ejemplo.com"
        assert usuario.full_name == "Damián Orsi"

    @pytest.mark.parametrize("email", ["sinarroba", "@sinlocal.com", "sin@dominio", ""])
    def test_rechaza_emails_invalidos(self, email: str) -> None:
        # Arrange / Act / Assert
        with pytest.raises(InvalidUserError, match="Email inválido"):
            User(email=email, full_name="Alguien")

    def test_rechaza_nombre_vacio(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(InvalidUserError, match="no puede estar vacío"):
            User(email="a@b.com", full_name="   ")


class TestCategory:
    def test_recorta_el_nombre(self) -> None:
        # Arrange / Act
        categoria = Category(user_id=1, name="  Alimentación  ", type=TransactionType.EXPENSE)

        # Assert
        assert categoria.name == "Alimentación"
        assert categoria.is_expense

    def test_rechaza_nombre_vacio(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(InvalidCategoryError, match="no puede estar vacío"):
            Category(user_id=1, name="   ", type=TransactionType.EXPENSE)

    def test_rechaza_nombre_demasiado_largo(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(InvalidCategoryError, match="60 caracteres"):
            Category(user_id=1, name="x" * 61, type=TransactionType.EXPENSE)

    def test_normaliza_el_color_a_minusculas(self) -> None:
        # Arrange / Act
        categoria = Category(user_id=1, name="Ocio", type=TransactionType.EXPENSE, color="#1C9E6F")

        # Assert
        assert categoria.color == "#1c9e6f"

    @pytest.mark.parametrize("color", ["1c9e6f", "#12345", "#gggggg", "rojo"])
    def test_rechaza_colores_invalidos(self, color: str) -> None:
        # Arrange / Act / Assert
        with pytest.raises(InvalidCategoryError, match="Color inválido"):
            Category(user_id=1, name="Ocio", type=TransactionType.EXPENSE, color=color)


class TestTransaction:
    def _movimiento(self, tipo: TransactionType, monto: Money) -> Transaction:
        return Transaction(
            user_id=1,
            category_id=1,
            type=tipo,
            money=monto,
            occurred_on=date(2026, 8, 4),
        )

    @pytest.mark.parametrize("monto", ["0", "-100"])
    def test_rechaza_montos_no_positivos(self, monto: str) -> None:
        """El signo lo determina el tipo, no el monto."""
        # Arrange / Act / Assert
        with pytest.raises(InvalidTransactionError, match="mayor a cero"):
            self._movimiento(TransactionType.EXPENSE, Money.of(monto, "ARS"))

    def test_un_ingreso_suma_con_signo_positivo(self) -> None:
        # Arrange
        movimiento = self._movimiento(TransactionType.INCOME, CIEN_PESOS)

        # Act / Assert
        assert movimiento.signed_money == CIEN_PESOS

    def test_un_gasto_suma_con_signo_negativo(self) -> None:
        # Arrange
        movimiento = self._movimiento(TransactionType.EXPENSE, CIEN_PESOS)

        # Act / Assert
        assert movimiento.signed_money == Money.of("-100.00", "ARS")

    def test_el_balance_sale_de_sumar_montos_con_signo(self) -> None:
        # Arrange
        movimientos = [
            self._movimiento(TransactionType.INCOME, Money.of("1000", "ARS")),
            self._movimiento(TransactionType.EXPENSE, Money.of("250.50", "ARS")),
            self._movimiento(TransactionType.EXPENSE, Money.of("120.25", "ARS")),
        ]

        # Act
        balance = Money.sum((m.signed_money for m in movimientos), "ARS")

        # Assert
        assert balance == Money.of("629.25", "ARS")

    def test_expone_la_moneda_del_monto(self) -> None:
        # Arrange
        movimiento = self._movimiento(TransactionType.INCOME, CIEN_PESOS)

        # Act / Assert
        assert movimiento.currency == "ARS"

    def test_reconoce_si_lo_genero_una_regla(self) -> None:
        # Arrange
        suelto = self._movimiento(TransactionType.EXPENSE, CIEN_PESOS)
        generado = Transaction(
            user_id=1,
            category_id=1,
            type=TransactionType.EXPENSE,
            money=CIEN_PESOS,
            occurred_on=date(2026, 8, 4),
            recurring_rule_id=7,
        )

        # Act / Assert
        assert not suelto.is_recurring
        assert generado.is_recurring

    def test_rechaza_descripcion_demasiado_larga(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(InvalidTransactionError, match="255 caracteres"):
            Transaction(
                user_id=1,
                category_id=1,
                type=TransactionType.EXPENSE,
                money=CIEN_PESOS,
                occurred_on=date(2026, 8, 4),
                description="x" * 256,
            )


class TestBudget:
    def test_exige_que_el_periodo_sea_el_dia_uno(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(InvalidBudgetError, match="día 1 del mes"):
            Budget(user_id=1, category_id=1, period_month=date(2026, 8, 15), limit=CIEN_PESOS)

    def test_rechaza_topes_no_positivos(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(InvalidBudgetError, match="mayor a cero"):
            Budget(
                user_id=1,
                category_id=1,
                period_month=date(2026, 8, 1),
                limit=Money.zero("ARS"),
            )

    def test_sabe_si_una_fecha_cae_en_su_mes(self) -> None:
        # Arrange
        presupuesto = Budget(
            user_id=1, category_id=1, period_month=Budget.periodo(2026, 8), limit=CIEN_PESOS
        )

        # Act / Assert
        assert presupuesto.cubre(date(2026, 8, 1))
        assert presupuesto.cubre(date(2026, 8, 31))
        assert not presupuesto.cubre(date(2026, 7, 31))
        assert not presupuesto.cubre(date(2026, 9, 1))


class TestRecurringRule:
    def _regla(self, **overrides: object) -> RecurringRule:
        base: dict[str, object] = {
            "user_id": 1,
            "category_id": 1,
            "type": TransactionType.EXPENSE,
            "money": CIEN_PESOS,
            "frequency": RecurrenceFrequency.MONTHLY,
            "starts_on": date(2026, 1, 1),
            "day_of_month": 5,
        }
        base.update(overrides)
        return RecurringRule(**base)  # type: ignore[arg-type]

    def test_mensual_exige_dia_del_mes(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(InvalidRecurringRuleError, match="requiere day_of_month"):
            self._regla(day_of_month=None)

    @pytest.mark.parametrize("dia", [0, 32])
    def test_mensual_valida_el_rango_del_dia(self, dia: int) -> None:
        # Arrange / Act / Assert
        with pytest.raises(InvalidRecurringRuleError, match="entre 1 y 31"):
            self._regla(day_of_month=dia)

    def test_semanal_exige_dia_de_la_semana(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(InvalidRecurringRuleError, match="requiere day_of_week"):
            self._regla(frequency=RecurrenceFrequency.WEEKLY, day_of_month=None)

    def test_semanal_rechaza_dia_del_mes_sobrante(self) -> None:
        """Una regla semanal con day_of_month cargado es ambigua.

        Dejarla pasar significa que el job la interpreta distinto de lo que
        esperaba quien la creó.
        """
        # Arrange / Act / Assert
        with pytest.raises(InvalidRecurringRuleError, match="no usa day_of_month"):
            self._regla(frequency=RecurrenceFrequency.WEEKLY, day_of_month=5, day_of_week=1)

    def test_diaria_no_lleva_parametros(self) -> None:
        # Arrange / Act
        regla = self._regla(frequency=RecurrenceFrequency.DAILY, day_of_month=None)

        # Assert
        assert regla.frequency is RecurrenceFrequency.DAILY

    def test_anual_no_lleva_parametros_porque_los_deriva_de_starts_on(self) -> None:
        # Arrange / Act
        regla = self._regla(frequency=RecurrenceFrequency.YEARLY, day_of_month=None)

        # Assert
        assert regla.frequency is RecurrenceFrequency.YEARLY

    def test_rechaza_fin_anterior_al_inicio(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(InvalidRecurringRuleError, match="no puede ser anterior"):
            self._regla(starts_on=date(2026, 6, 1), ends_on=date(2026, 5, 1))

    def test_rechaza_monto_no_positivo(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(InvalidRecurringRuleError, match="mayor a cero"):
            self._regla(money=Money.zero("ARS"))

    def test_vigencia_respeta_la_ventana_y_la_pausa(self) -> None:
        # Arrange
        regla = self._regla(starts_on=date(2026, 3, 1), ends_on=date(2026, 6, 30))

        # Act / Assert
        assert not regla.vigente_en(date(2026, 2, 28))
        assert regla.vigente_en(date(2026, 3, 1))
        assert regla.vigente_en(date(2026, 6, 30))
        assert not regla.vigente_en(date(2026, 7, 1))

    def test_una_regla_pausada_no_esta_vigente(self) -> None:
        # Arrange
        regla = self._regla(is_active=False)

        # Act / Assert
        assert not regla.vigente_en(date(2026, 6, 5))


class TestRecurringOccurrence:
    def test_saltear_marca_el_estado_y_suelta_el_movimiento(self) -> None:
        """Saltear no borra la fila: si se borrara, el job la volvería a crear."""
        # Arrange
        ocurrencia = RecurringOccurrence(
            rule_id=1,
            occurred_on=date(2026, 8, 5),
            status=OccurrenceStatus.GENERATED,
            transaction_id=42,
        )

        # Act
        ocurrencia.saltear()

        # Assert
        assert ocurrencia.fue_salteada
        assert ocurrencia.transaction_id is None
