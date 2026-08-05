import { useMemo, useState } from 'react'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { Cargando, ErrorVisible, SinDatos } from '@/components/Feedback'
import { Modal } from '@/components/Modal'
import { useCategorias } from '@/features/categories/api'
import { TransactionFilters } from '@/features/transactions/TransactionFilters'
import { TransactionForm } from '@/features/transactions/TransactionForm'
import {
  FILTROS_VACIOS,
  exportarMovimientos,
  useBorrarMovimiento,
  useMovimientos,
} from '@/features/transactions/api'
import type { FiltrosDeMovimientos } from '@/features/transactions/api'
import type { Transaction } from '@/types/api'
import { aErroresDeFormulario } from '@/utils/apiErrors'
import { formatDate, formatMoney } from '@/utils/format'

const POR_PAGINA = 20

export function TransactionsPage() {
  const [filtros, setFiltros] = useState<FiltrosDeMovimientos>(FILTROS_VACIOS)
  const [offset, setOffset] = useState(0)
  const [enFormulario, setEnFormulario] = useState<Transaction | 'nuevo' | null>(null)
  const [aBorrar, setABorrar] = useState<Transaction | null>(null)
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null)

  const movimientos = useMovimientos(filtros, { offset, limit: POR_PAGINA })
  const categorias = useCategorias()
  const borrar = useBorrarMovimiento()

  const nombrePorCategoria = useMemo(
    () => new Map((categorias.data ?? []).map((categoria) => [categoria.id, categoria.name])),
    [categorias.data],
  )

  const cambiarFiltros = (nuevos: FiltrosDeMovimientos) => {
    setFiltros(nuevos)
    // Sin esto, filtrar estando en la página 5 dejaría la tabla vacía aunque
    // haya resultados, porque el offset queda más allá del total nuevo.
    setOffset(0)
  }

  const exportar = async (formato: 'standard' | 'excel_es') => {
    setErrorGeneral(null)
    try {
      await exportarMovimientos(filtros, formato)
    } catch (excepcion) {
      setErrorGeneral(aErroresDeFormulario(excepcion).general)
    }
  }

  const confirmarBorrado = async () => {
    if (!aBorrar) return
    try {
      await borrar.mutateAsync(aBorrar.id)
      setABorrar(null)
    } catch (excepcion) {
      setErrorGeneral(aErroresDeFormulario(excepcion).general)
      setABorrar(null)
    }
  }

  const total = movimientos.data?.totalCount ?? 0
  const desde = total === 0 ? 0 : offset + 1
  const hasta = Math.min(offset + POR_PAGINA, total)

  return (
    <section className="pagina">
      <div className="pagina__encabezado">
        <h1>Movimientos</h1>
        <div className="pagina__acciones">
          <button
            type="button"
            className="boton boton--secundario"
            onClick={() => void exportar('standard')}
          >
            Exportar CSV
          </button>
          {/* La explicación va como texto asociado y no en `title`: el atributo
              title reemplaza el nombre accesible del botón, así que un lector
              de pantalla leería el tooltip entero en vez de la etiqueta. */}
          <button
            type="button"
            className="boton boton--secundario"
            onClick={() => void exportar('excel_es')}
            aria-describedby="ayuda-export-excel"
          >
            Exportar para Excel
          </button>
          <span id="ayuda-export-excel" className="visualmente-oculto">
            Separador punto y coma y coma decimal, para abrir con doble clic en Excel en
            español.
          </span>
          <button
            type="button"
            className="boton boton--primario"
            onClick={() => setEnFormulario('nuevo')}
          >
            Nuevo movimiento
          </button>
        </div>
      </div>

      {errorGeneral && (
        <p className="formulario__error" role="alert">
          {errorGeneral}
        </p>
      )}

      <TransactionFilters filtros={filtros} onCambiar={cambiarFiltros} />

      {movimientos.isPending && <Cargando mensaje="Cargando movimientos…" />}

      {movimientos.isError && (
        <ErrorVisible
          mensaje="No se pudieron cargar los movimientos."
          onReintentar={() => void movimientos.refetch()}
        />
      )}

      {movimientos.isSuccess && movimientos.data.entries.length === 0 && (
        <SinDatos
          titulo="No hay movimientos"
          detalle={
            Object.keys(filtros).length > 0
              ? 'Probá con otros filtros o limpiálos.'
              : 'Registrá tu primer ingreso o gasto para empezar.'
          }
        />
      )}

      {movimientos.isSuccess && movimientos.data.entries.length > 0 && (
        <>
          <div className="tabla__contenedor">
            <table className="tabla">
              <caption className="visualmente-oculto">
                Movimientos registrados, {total} en total
              </caption>
              <thead>
                <tr>
                  <th scope="col">Fecha</th>
                  <th scope="col">Categoría</th>
                  <th scope="col">Descripción</th>
                  <th scope="col" className="tabla__numero">
                    Monto
                  </th>
                  <th scope="col">
                    <span className="visualmente-oculto">Acciones</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {movimientos.data.entries.map((movimiento) => (
                  <tr key={movimiento.id}>
                    <td>{formatDate(movimiento.occurred_on)}</td>
                    <td>
                      {nombrePorCategoria.get(movimiento.category_id) ?? '—'}
                      {movimiento.is_recurring && (
                        <span className="etiqueta" title="Generado por una regla recurrente">
                          recurrente
                        </span>
                      )}
                    </td>
                    <td>{movimiento.description || '—'}</td>
                    <td
                      className={
                        movimiento.type === 'INCOME'
                          ? 'tabla__numero tabla__numero--positivo'
                          : 'tabla__numero tabla__numero--negativo'
                      }
                    >
                      {movimiento.type === 'INCOME' ? '+' : '−'}
                      {formatMoney(movimiento.amount, movimiento.currency)}
                    </td>
                    <td className="tabla__acciones">
                      <button
                        type="button"
                        className="boton boton--secundario boton--chico"
                        onClick={() => setEnFormulario(movimiento)}
                      >
                        Editar
                      </button>
                      <button
                        type="button"
                        className="boton boton--secundario boton--chico"
                        onClick={() => setABorrar(movimiento)}
                      >
                        Borrar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <nav className="paginador" aria-label="Paginación">
            <button
              type="button"
              className="boton boton--secundario boton--chico"
              onClick={() => setOffset(Math.max(0, offset - POR_PAGINA))}
              disabled={offset === 0}
            >
              Anterior
            </button>
            <span aria-live="polite">
              {desde}–{hasta} de {total}
            </span>
            <button
              type="button"
              className="boton boton--secundario boton--chico"
              onClick={() => setOffset(offset + POR_PAGINA)}
              disabled={hasta >= total}
            >
              Siguiente
            </button>
          </nav>
        </>
      )}

      <Modal
        titulo={enFormulario === 'nuevo' ? 'Nuevo movimiento' : 'Editar movimiento'}
        abierto={enFormulario !== null}
        onCerrar={() => setEnFormulario(null)}
      >
        {enFormulario !== null && (
          <TransactionForm
            movimiento={enFormulario === 'nuevo' ? undefined : enFormulario}
            onListo={() => setEnFormulario(null)}
          />
        )}
      </Modal>

      <ConfirmDialog
        abierto={aBorrar !== null}
        titulo="Borrar movimiento"
        mensaje={`¿Seguro que querés borrar este movimiento de ${
          aBorrar ? formatMoney(aBorrar.amount, aBorrar.currency) : ''
        }? Esta acción no se puede deshacer.`}
        enProceso={borrar.isPending}
        onConfirmar={() => void confirmarBorrado()}
        onCancelar={() => setABorrar(null)}
      />
    </section>
  )
}
