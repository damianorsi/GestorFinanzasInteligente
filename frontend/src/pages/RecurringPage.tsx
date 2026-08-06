import { useState } from 'react'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { Cargando, ErrorVisible, SinDatos } from '@/components/Feedback'
import { Modal } from '@/components/Modal'
import { OccurrencesList } from '@/features/recurring/OccurrencesList'
import { RecurringRuleForm } from '@/features/recurring/RecurringRuleForm'
import { useBorrarRegla, useEditarRegla, useReglas } from '@/features/recurring/api'
import { describirFrecuencia } from '@/features/recurring/labels'
import { useCategorias } from '@/features/categories/api'
import type { RecurringRule } from '@/types/api'
import { aErroresDeFormulario } from '@/utils/apiErrors'
import { formatDate, formatMoney } from '@/utils/format'

export function RecurringPage() {
  const reglas = useReglas()
  const categorias = useCategorias()
  const editar = useEditarRegla()
  const borrar = useBorrarRegla()

  const [enFormulario, setEnFormulario] = useState<RecurringRule | 'nueva' | null>(null)
  const [enHistorial, setEnHistorial] = useState<RecurringRule | null>(null)
  const [aBorrar, setABorrar] = useState<RecurringRule | null>(null)
  const [errorAlBorrar, setErrorAlBorrar] = useState<string | null>(null)

  const nombreDeCategoria = (id: number) =>
    (categorias.data ?? []).find((categoria) => categoria.id === id)?.name ?? '(sin categoría)'

  const alternarPausa = async (regla: RecurringRule) => {
    await editar.mutateAsync({ id: regla.id, is_active: !regla.is_active })
  }

  const confirmarBorrado = async () => {
    if (!aBorrar) return
    setErrorAlBorrar(null)
    try {
      await borrar.mutateAsync(aBorrar.id)
      setABorrar(null)
    } catch (excepcion) {
      setErrorAlBorrar(aErroresDeFormulario(excepcion).general)
    }
  }

  return (
    <section className="pagina">
      <div className="pagina__encabezado">
        <div>
          <h1>Movimientos recurrentes</h1>
          <p className="pagina__subtitulo">
            Los movimientos se generan el día que corresponde, nunca por adelantado.
          </p>
        </div>
        <button
          type="button"
          className="boton boton--primario"
          onClick={() => setEnFormulario('nueva')}
        >
          Nueva regla
        </button>
      </div>

      {reglas.isPending && <Cargando mensaje="Cargando tus reglas…" />}

      {reglas.isError && (
        <ErrorVisible
          mensaje="No se pudieron cargar las reglas."
          onReintentar={() => void reglas.refetch()}
        />
      )}

      {reglas.isSuccess && reglas.data.length === 0 && (
        <SinDatos
          titulo="Todavía no tenés reglas"
          detalle="Cargá tus gastos fijos —alquiler, servicios, suscripciones— y se van a registrar solos."
        />
      )}

      {reglas.isSuccess && reglas.data.length > 0 && (
        <ul className="reglas">
          {reglas.data.map((regla) => (
            <li key={regla.id} className={`regla ${regla.is_active ? '' : 'regla--pausada'}`.trim()}>
              <div className="regla__cabecera">
                <span className="regla__descripcion">
                  {regla.description || nombreDeCategoria(regla.category_id)}
                </span>
                <span
                  className={
                    regla.type === 'INCOME'
                      ? 'regla__monto regla__monto--positivo'
                      : 'regla__monto regla__monto--negativo'
                  }
                >
                  {formatMoney(regla.amount, regla.currency)}
                </span>
              </div>

              <p className="regla__detalle">
                {describirFrecuencia(regla)} · {nombreDeCategoria(regla.category_id)}
                {regla.ends_on && ` · hasta el ${formatDate(regla.ends_on)}`}
              </p>

              {regla.is_active ? (
                <p className="regla__proximas">
                  Próximas:{' '}
                  {regla.next_dates.length > 0
                    ? regla.next_dates.map(formatDate).join(' · ')
                    : 'no quedan fechas por generar'}
                </p>
              ) : (
                <p className="regla__proximas regla__proximas--pausada">
                  Pausada. Al reactivarla no se generan los movimientos del período pausado.
                </p>
              )}

              <div className="regla__acciones">
                <button
                  type="button"
                  className="boton boton--secundario boton--chico"
                  onClick={() => void alternarPausa(regla)}
                  disabled={editar.isPending}
                >
                  {regla.is_active ? 'Pausar' : 'Reactivar'}
                </button>
                <button
                  type="button"
                  className="boton boton--secundario boton--chico"
                  onClick={() => setEnFormulario(regla)}
                >
                  Editar
                </button>
                <button
                  type="button"
                  className="boton boton--secundario boton--chico"
                  onClick={() => setEnHistorial(regla)}
                >
                  Historial
                </button>
                <button
                  type="button"
                  className="boton boton--secundario boton--chico"
                  onClick={() => {
                    setErrorAlBorrar(null)
                    setABorrar(regla)
                  }}
                >
                  Borrar
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Modal
        titulo={enFormulario === 'nueva' ? 'Nueva regla' : 'Editar regla'}
        abierto={enFormulario !== null}
        onCerrar={() => setEnFormulario(null)}
      >
        {enFormulario !== null && (
          <RecurringRuleForm
            regla={enFormulario === 'nueva' ? undefined : enFormulario}
            onListo={() => setEnFormulario(null)}
          />
        )}
      </Modal>

      <Modal
        titulo="Historial de la regla"
        abierto={enHistorial !== null}
        onCerrar={() => setEnHistorial(null)}
      >
        {enHistorial !== null && <OccurrencesList ruleId={enHistorial.id} />}
      </Modal>

      <ConfirmDialog
        abierto={aBorrar !== null}
        titulo="Borrar regla"
        mensaje={
          errorAlBorrar ??
          'Los movimientos que ya generó no se borran: quedan como movimientos sueltos. ' +
            'Lo que se corta es la generación hacia adelante.'
        }
        enProceso={borrar.isPending}
        onConfirmar={() => void confirmarBorrado()}
        onCancelar={() => {
          setABorrar(null)
          setErrorAlBorrar(null)
        }}
      />
    </section>
  )
}
