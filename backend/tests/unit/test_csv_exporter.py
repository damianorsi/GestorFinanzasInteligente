"""Tests de la serialización a CSV."""

from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal

import pytest

from app.api.v1.exporters import FormatoCsv, construir_csv
from app.application.dtos import TransactionExportRow
from app.domain.enums import TransactionType

BOM = b"\xef\xbb\xbf"


def _fila(
    descripcion: str = "Supermercado",
    monto: str = "1234.56",
    tipo: TransactionType = TransactionType.EXPENSE,
    recurrente: bool = False,
) -> TransactionExportRow:
    return TransactionExportRow(
        id=1,
        occurred_on=date(2026, 8, 5),
        type=tipo,
        category_name="Alimentación",
        description=descripcion,
        amount=Decimal(monto),
        currency="ARS",
        is_recurring=recurrente,
    )


def _parsear(crudo: bytes, delimitador: str = ",") -> list[list[str]]:
    texto = crudo.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(texto), delimiter=delimitador))


def test_arranca_con_el_bom() -> None:
    """Sin BOM, Excel abre el archivo en la codificación del sistema y rompe los acentos."""
    # Arrange / Act
    contenido = construir_csv([_fila()])

    # Assert
    assert contenido.startswith(BOM)


def test_la_primera_fila_son_los_encabezados() -> None:
    # Arrange / Act
    filas = _parsear(construir_csv([_fila()]))

    # Assert
    assert filas[0] == [
        "id",
        "fecha",
        "tipo",
        "categoria",
        "descripcion",
        "monto",
        "moneda",
        "recurrente",
    ]


def test_los_acentos_sobreviven() -> None:
    # Arrange / Act
    filas = _parsear(construir_csv([_fila(descripcion="Ñandú con acentuación")]))

    # Assert
    assert filas[1][3] == "Alimentación"
    assert filas[1][4] == "Ñandú con acentuación"


def test_una_descripcion_con_comas_no_rompe_las_columnas() -> None:
    # Arrange / Act
    filas = _parsear(construir_csv([_fila(descripcion="Pan, leche y huevos")]))

    # Assert
    assert len(filas[1]) == 8
    assert filas[1][4] == "Pan, leche y huevos"


def test_una_descripcion_con_comillas_se_escapa() -> None:
    # Arrange / Act
    filas = _parsear(construir_csv([_fila(descripcion='Compra en "El Almacén"')]))

    # Assert
    assert filas[1][4] == 'Compra en "El Almacén"'


def test_una_descripcion_con_salto_de_linea_no_rompe_las_filas() -> None:
    # Arrange / Act
    filas = _parsear(construir_csv([_fila(descripcion="Primera\nSegunda")]))

    # Assert
    assert len(filas) == 2
    assert filas[1][4] == "Primera\nSegunda"


def test_los_tipos_van_en_espanol() -> None:
    """El CSV lo lee una persona, no la API."""
    # Arrange / Act
    filas = _parsear(construir_csv([_fila(tipo=TransactionType.INCOME)]))

    # Assert
    assert filas[1][2] == "Ingreso"


def test_la_marca_de_recurrente_va_en_espanol() -> None:
    # Arrange / Act
    filas = _parsear(construir_csv([_fila(recurrente=True)]))

    # Assert
    assert filas[1][7] == "Sí"


def test_el_monto_conserva_los_dos_decimales() -> None:
    # Arrange / Act
    filas = _parsear(construir_csv([_fila(monto="1000")]))

    # Assert
    assert filas[1][5] == "1000.00"


def test_un_export_vacio_igual_trae_los_encabezados() -> None:
    """Un archivo sin ninguna línea es indistinguible de un error de descarga."""
    # Arrange / Act
    filas = _parsear(construir_csv([]))

    # Assert
    assert len(filas) == 1
    assert filas[0][0] == "id"


class TestFormatoExcelEs:
    def test_usa_punto_y_coma_como_separador(self) -> None:
        """Excel en español muestra todo en una columna si el separador es coma."""
        # Arrange / Act
        contenido = construir_csv([_fila()], FormatoCsv.EXCEL_ES)

        # Assert
        filas = _parsear(contenido, delimitador=";")
        assert len(filas[1]) == 8

    def test_usa_coma_como_separador_decimal(self) -> None:
        # Arrange / Act
        filas = _parsear(construir_csv([_fila(monto="1234.56")], FormatoCsv.EXCEL_ES), ";")

        # Assert
        assert filas[1][5] == "1234,56"

    def test_el_monto_con_coma_decimal_no_parte_la_columna(self) -> None:
        """Por esto los dos cambios van juntos en un solo formato y no sueltos."""
        # Arrange / Act
        filas = _parsear(construir_csv([_fila(monto="1234.56")], FormatoCsv.EXCEL_ES), ";")

        # Assert
        assert len(filas[1]) == 8


@pytest.mark.parametrize("formato", list(FormatoCsv))
def test_todos_los_formatos_llevan_bom(formato: FormatoCsv) -> None:
    # Arrange / Act / Assert
    assert construir_csv([_fila()], formato).startswith(BOM)
