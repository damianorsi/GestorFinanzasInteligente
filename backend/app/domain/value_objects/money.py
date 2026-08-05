"""Value object `Money`: una cantidad de dinero con su moneda.

Existe para que la moneda viaje pegada al monto por todas las capas. Ese es el
mecanismo que hace barato habilitar USD más adelante: sin él, agregar la moneda
obligaría a tocar cada caso de uso (docs/PROMPT.md §5.1).

**Sobre el signo**: `Money` admite valores negativos. La regla "los montos son
siempre positivos" es una invariante de las *entidades* `Transaction`,
`Budget` y `RecurringRule` —donde el signo lo determina el `TransactionType`—,
no del tipo en sí: un balance es una resta y puede dar negativo. Ponerle la
restricción al value object obligaría a devolver los balances como `Decimal`
pelado, que es justo lo que este tipo viene a evitar.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Self

from app.domain.exceptions import CurrencyMismatchError, InvalidMoneyError

DECIMALES = 2
LARGO_CODIGO_MONEDA = 3

_CUANTIZADOR = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class Money:
    """Monto inmutable con su moneda ISO 4217.

    Construir preferentemente con `Money.of(...)`, que acepta `str` e `int`
    además de `Decimal`.
    """

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        codigo = self.currency
        if len(codigo) != LARGO_CODIGO_MONEDA or not codigo.isalpha():
            raise InvalidMoneyError(
                f"Código de moneda inválido: {codigo!r}. Se espera ISO 4217 de 3 letras."
            )
        object.__setattr__(self, "currency", codigo.upper())

        monto = self.amount
        if not monto.is_finite():
            raise InvalidMoneyError(f"El monto debe ser finito, se recibió {monto}.")

        exponente = monto.as_tuple().exponent
        if isinstance(exponente, int) and -exponente > DECIMALES:
            raise InvalidMoneyError(
                f"El monto {monto} tiene más de {DECIMALES} decimales. "
                "El redondeo es una decisión de negocio, no se hace en silencio."
            )
        object.__setattr__(self, "amount", monto.quantize(_CUANTIZADOR))

    # --- Construcción ------------------------------------------------------
    @classmethod
    def of(cls, amount: str | int | Decimal | float, currency: str) -> Self:
        """Construye un `Money` desde `str`, `int` o `Decimal`.

        `float` figura en la firma únicamente para poder rechazarlo con un
        mensaje claro: el flotante binario no representa exactamente 0.1, y en
        dinero eso es corrupción silenciosa.
        """
        if isinstance(amount, float):
            raise InvalidMoneyError(
                "El dinero nunca se construye desde float: usá str, int o Decimal."
            )
        try:
            valor = amount if isinstance(amount, Decimal) else Decimal(str(amount))
        except ArithmeticError as exc:
            raise InvalidMoneyError(f"No se pudo interpretar {amount!r} como monto.") from exc
        return cls(valor, currency)

    @classmethod
    def zero(cls, currency: str) -> Self:
        return cls(Decimal("0.00"), currency)

    @classmethod
    def sum(cls, montos: Iterable[Money], currency: str) -> Money:
        """Suma una colección, exigiendo la moneda del total explícitamente.

        La moneda es obligatoria y no se infiere del primer elemento: una
        colección vacía también tiene que saber en qué moneda vale cero.
        """
        total = cls.zero(currency)
        for monto in montos:
            total = total + monto
        return total

    # --- Aritmética --------------------------------------------------------
    def _exigir_misma_moneda(self, otro: Money, operacion: str) -> None:
        if self.currency != otro.currency:
            raise CurrencyMismatchError(
                f"No se puede {operacion} {self.currency} con {otro.currency}: "
                "la conversión entre monedas no está implementada."
            )

    def __add__(self, otro: Money) -> Money:
        self._exigir_misma_moneda(otro, "sumar")
        return Money(self.amount + otro.amount, self.currency)

    def __sub__(self, otro: Money) -> Money:
        self._exigir_misma_moneda(otro, "restar")
        return Money(self.amount - otro.amount, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    def __abs__(self) -> Money:
        return Money(abs(self.amount), self.currency)

    # --- Comparación -------------------------------------------------------
    # La igualdad la genera el dataclass: dos monedas distintas son distintas,
    # no un error. El orden sí exige la misma moneda, porque "¿es 100 ARS mayor
    # que 100 USD?" no tiene respuesta sin cotización.
    def __lt__(self, otro: Money) -> bool:
        self._exigir_misma_moneda(otro, "comparar")
        return self.amount < otro.amount

    def __le__(self, otro: Money) -> bool:
        self._exigir_misma_moneda(otro, "comparar")
        return self.amount <= otro.amount

    def __gt__(self, otro: Money) -> bool:
        self._exigir_misma_moneda(otro, "comparar")
        return self.amount > otro.amount

    def __ge__(self, otro: Money) -> bool:
        self._exigir_misma_moneda(otro, "comparar")
        return self.amount >= otro.amount

    # --- Consultas ---------------------------------------------------------
    @property
    def is_positive(self) -> bool:
        return self.amount > 0

    @property
    def is_negative(self) -> bool:
        return self.amount < 0

    @property
    def is_zero(self) -> bool:
        return self.amount == 0

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"
