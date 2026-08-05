"""Serialización a CSV.

Vive en la capa de presentación: el caso de uso devuelve filas tipadas y acá se
deciden separadores, formato de fecha y encoding, que son decisiones de
formato y no de negocio.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from enum import StrEnum

from app.application.dtos import TransactionExportRow
from app.domain.enums import TransactionType

ENCABEZADOS = (
    "id",
    "fecha",
    "tipo",
    "categoria",
    "descripcion",
    "monto",
    "moneda",
    "recurrente",
)

_ETIQUETA_DE_TIPO = {TransactionType.INCOME: "Ingreso", TransactionType.EXPENSE: "Gasto"}


class FormatoCsv(StrEnum):
    """Cómo se arma el archivo.

    `EXCEL_ES` existe porque Excel en español usa el punto y coma como
    separador de listas y la coma como separador decimal: con el formato
    estándar, un doble clic muestra todo el archivo en una sola columna.
    Son dos decisiones que van juntas, por eso un solo parámetro y no dos.
    """

    ESTANDAR = "standard"
    EXCEL_ES = "excel_es"


def construir_csv(
    filas: Sequence[TransactionExportRow], formato: FormatoCsv = FormatoCsv.ESTANDAR
) -> bytes:
    """Devuelve el CSV ya codificado en UTF-8 con BOM.

    El BOM es lo que hace que Excel reconozca el encoding: sin él abre el
    archivo en la codificación del sistema y los acentos salen rotos.
    """
    es_excel = formato is FormatoCsv.EXCEL_ES
    separador = ";" if es_excel else ","

    buffer = io.StringIO()
    escritor = csv.writer(
        buffer,
        delimiter=separador,
        quoting=csv.QUOTE_MINIMAL,
        # RFC 4180. El módulo csv usa \r\n por defecto, pero fijarlo evita que
        # dependa de la plataforma.
        lineterminator="\r\n",
    )

    escritor.writerow(ENCABEZADOS)
    for fila in filas:
        monto = f"{fila.amount:.2f}"
        if es_excel:
            monto = monto.replace(".", ",")
        escritor.writerow(
            (
                fila.id,
                fila.occurred_on.isoformat(),
                _ETIQUETA_DE_TIPO[fila.type],
                fila.category_name,
                fila.description,
                monto,
                fila.currency,
                "Sí" if fila.is_recurring else "No",
            )
        )

    # `utf-8-sig` agrega el BOM al principio.
    return buffer.getvalue().encode("utf-8-sig")


def nombre_de_archivo(prefijo: str = "movimientos") -> str:
    return f"{prefijo}.csv"
