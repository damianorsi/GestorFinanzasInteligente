import { useState } from 'react'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { Cargando, ErrorVisible, SinDatos } from '@/components/Feedback'
import { Modal } from '@/components/Modal'
import { BudgetForm } from '@/features/budgets/BudgetForm'
import { BudgetProgressBar } from '@/features/budgets/BudgetProgressBar'
import {
  useAvanceDePresupuestos,
  useBorrarPresupuesto,
  useCopiarPresupuestos,
  usePresupuestos,
} from '@/features/budgets/api'
import type { Budget } from '@/types/api'
import { aErroresDeFormulario } from '@/utils/apiErrors'
import { formatMoney, formatPeriod } from '@/utils/format'
import { desplazarPeriodo, periodoActual } from '@/utils/periods'

export function BudgetsPage() {
  const [periodo, setPeriodo] = useState(periodoActual())
  const [enFormulario, setEnFormulario] = useState<Budget | 'nuevo' | null>(null)
  const [aBorrar, setABorrar] = useState<Budget | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)

  const avance = useAvanceDePresupuestos(periodo)
  const presupuestos = usePresupuestos(periodo)
  const borrar = useBorrarPresupuesto()
  const copiar = useCopiarPresupuestos()

  const copiarDelMesAnterior = async () => {
    setAviso(null)
    try {
      const resultado = await copiar.mutateAsync({
        from_period: desplazarPeriodo(periodo, -1),
        to_period: periodo,
      })
      if (resultado.created === 0 && resultado.skipped.length === 0) {
        setAviso('El mes anterior no tenía presupuestos para copiar.')
      } else {
        const salteados = resultado.skipped.map((s) => s.category_name).join(', ')
        setAviso(
          `Se copiaron ${resultado.created} presupuestos.` +
            (salteados ? ` No se tocaron los que ya existían: ${salteados}.` : ''),
        )
      }
    } catch (excepcion) {
      setAviso(aErroresDeFormulario(excepcion).general)
    }
  }

  const confirmarBorrado = async () => {
    if (!aBorrar) return
    try {
      await borrar.mutateAsync(aBorrar.id)
    } catch (excepcion) {
      setAviso(aErroresDeFormulario(excepcion).general)
    } finally {
      setABorrar(null)
    }
  }

  const ocupadas = (presupuestos.data ?? []).map((p) => p.category_id)
  const porCategoria = new Map((presupuestos.data ?? []).map((p) => [p.category_id, p]))

  return (
    <section className="pagina">
      <div className="pagina__encabezado">
        <h1>Presupuestos</h1>
        <div className="pagina__acciones">
          <button
            type="button"
            className="boton boton--secundario"
            onClick={() => void copiarDelMesAnterior()}
            disabled={copiar.isPending}
          >
            {copiar.isPending ? 'Copiando…' : 'Copiar del mes anterior'}
          </button>
          <button
            type="button"
            className="boton boton--primario"
            onClick={() => setEnFormulario('nuevo')}
          >
            Nuevo presupuesto
          </button>
        </div>
      </div>

      <div className="selector-de-mes">
        <button
          type="button"
          className="boton boton--secundario boton--chico"
          onClick={() => setPeriodo(desplazarPeriodo(periodo, -1))}
          aria-label="Mes anterior"
        >
          ←
        </button>
        <strong aria-live="polite">{formatPeriod(periodo)}</strong>
        <button
          type="button"
          className="boton boton--secundario boton--chico"
          onClick={() => setPeriodo(desplazarPeriodo(periodo, 1))}
          aria-label="Mes siguiente"
        >
          →
        </button>
      </div>

      {aviso && (
        <p className="aviso" role="status">
          {aviso}
        </p>
      )}

      {avance.isPending && <Cargando mensaje="Cargando presupuestos…" />}

      {avance.isError && (
        <ErrorVisible
          mensaje="No se pudo cargar el avance de los presupuestos."
          onReintentar={() => void avance.refetch()}
        />
      )}

      {avance.isSuccess && (
        <>
          {avance.data.exceeded_count > 0 && (
            <p className="aviso aviso--alerta" role="status">
              Te pasaste del tope en {avance.data.exceeded_count}{' '}
              {avance.data.exceeded_count === 1 ? 'categoría' : 'categorías'}.
            </p>
          )}

          {avance.data.entries.length === 0 ? (
            <SinDatos
              titulo="No hay presupuestos para este mes"
              detalle="Creá uno o copiá los del mes anterior."
            />
          ) : (
            <ul className="progresos">
              {avance.data.entries.map((entrada) => (
                <div key={entrada.budget_id} className="progreso__contenedor">
                  <BudgetProgressBar entrada={entrada} />
                  <div className="progreso__acciones">
                    <button
                      type="button"
                      className="boton boton--secundario boton--chico"
                      onClick={() => {
                        const presupuesto = porCategoria.get(entrada.category_id)
                        if (presupuesto) setEnFormulario(presupuesto)
                      }}
                    >
                      Editar
                    </button>
                    <button
                      type="button"
                      className="boton boton--secundario boton--chico"
                      onClick={() => {
                        const presupuesto = porCategoria.get(entrada.category_id)
                        if (presupuesto) setABorrar(presupuesto)
                      }}
                    >
                      Borrar
                    </button>
                  </div>
                </div>
              ))}
            </ul>
          )}

          {avance.data.unbudgeted.length > 0 && (
            <div className="grupo">
              <h2>Gastos sin presupuesto</h2>
              <p className="pagina__subtitulo">
                Estas categorías tuvieron movimientos este mes pero no tienen tope.
              </p>
              <ul className="lista">
                {avance.data.unbudgeted.map((sinTope) => (
                  <li key={sinTope.category_id} className="lista__item">
                    <span className="lista__nombre">{sinTope.category_name}</span>
                    <span className="lista__acciones">
                      {formatMoney(sinTope.spent, avance.data.currency)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      <Modal
        titulo={enFormulario === 'nuevo' ? 'Nuevo presupuesto' : 'Editar presupuesto'}
        abierto={enFormulario !== null}
        onCerrar={() => setEnFormulario(null)}
      >
        {enFormulario !== null && (
          <BudgetForm
            periodo={periodo}
            presupuesto={enFormulario === 'nuevo' ? undefined : enFormulario}
            categoriasOcupadas={ocupadas}
            onListo={() => setEnFormulario(null)}
          />
        )}
      </Modal>

      <ConfirmDialog
        abierto={aBorrar !== null}
        titulo="Borrar presupuesto"
        mensaje="¿Seguro que querés borrar este presupuesto? Los movimientos no se tocan."
        enProceso={borrar.isPending}
        onConfirmar={() => void confirmarBorrado()}
        onCancelar={() => setABorrar(null)}
      />
    </section>
  )
}
