import { useState } from 'react'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { Cargando, ErrorVisible, SinDatos } from '@/components/Feedback'
import { Modal } from '@/components/Modal'
import { GoalForm } from '@/features/savings/GoalForm'
import { GoalProgressCard } from '@/features/savings/GoalProgressCard'
import { useAvanceDeMetas, useBorrarMeta, useMetas } from '@/features/savings/api'
import type { SavingsGoal } from '@/types/api'

export function SavingsGoalsPage() {
  const [enFormulario, setEnFormulario] = useState<SavingsGoal | 'nueva' | null>(null)
  const [aBorrar, setABorrar] = useState<SavingsGoal | null>(null)

  // El avance manda lo que se ve; el listado se pide para poder editar (el
  // avance no trae `is_active` ni el objetivo sin formatear).
  const avances = useAvanceDeMetas()
  const metas = useMetas()
  const borrar = useBorrarMeta()

  const metaPorId = (id: number) => (metas.data ?? []).find((meta) => meta.id === id)

  const confirmarBorrado = async () => {
    if (aBorrar === null) return
    await borrar.mutateAsync(aBorrar.id)
    setABorrar(null)
  }

  return (
    <section className="pagina">
      <div className="pagina__encabezado">
        <div>
          <h1>Metas de ahorro</h1>
          <p className="pagina__subtitulo">
            Cuánto llevás juntado y, si hay historial, en cuánto tiempo llegás.
          </p>
        </div>
        <button type="button" className="boton" onClick={() => setEnFormulario('nueva')}>
          Nueva meta
        </button>
      </div>

      {avances.isPending && <Cargando mensaje="Cargando tus metas…" />}

      {avances.isError && (
        <ErrorVisible
          mensaje="No se pudieron cargar las metas."
          onReintentar={() => void avances.refetch()}
        />
      )}

      {avances.isSuccess && avances.data.length === 0 && (
        <SinDatos
          titulo="No tenés metas de ahorro"
          detalle="Definí cuánto querés juntar y desde cuándo, y vas a ver el avance contra tu balance real."
          accion={
            <button type="button" className="boton" onClick={() => setEnFormulario('nueva')}>
              Crear la primera
            </button>
          }
        />
      )}

      {avances.isSuccess && avances.data.length > 0 && (
        <ul className="metas">
          {avances.data.map((avance) => (
            <GoalProgressCard
              key={avance.goal_id}
              avance={avance}
              onEditar={() => {
                const meta = metaPorId(avance.goal_id)
                if (meta) setEnFormulario(meta)
              }}
              onBorrar={() => {
                const meta = metaPorId(avance.goal_id)
                if (meta) setABorrar(meta)
              }}
            />
          ))}
        </ul>
      )}

      <Modal
        titulo={enFormulario === 'nueva' ? 'Nueva meta' : 'Editar meta'}
        abierto={enFormulario !== null}
        onCerrar={() => setEnFormulario(null)}
      >
        {enFormulario !== null && (
          <GoalForm
            meta={enFormulario === 'nueva' ? undefined : enFormulario}
            onListo={() => setEnFormulario(null)}
          />
        )}
      </Modal>

      <ConfirmDialog
        abierto={aBorrar !== null}
        titulo="Borrar meta"
        mensaje="¿Seguro? Los movimientos no se tocan: la meta es una lectura sobre tu balance, no una cuenta con plata adentro."
        enProceso={borrar.isPending}
        onConfirmar={() => void confirmarBorrado()}
        onCancelar={() => setABorrar(null)}
      />
    </section>
  )
}
