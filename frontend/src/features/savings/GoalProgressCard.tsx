import type { SavingsGoalProgress, SavingsProjection } from '@/types/api'
import { formatDate, formatMoney, formatPercent } from '@/utils/format'

import { ETIQUETA_DE_ESTADO } from './estados'

const TOPE_VISUAL = 100

interface GoalProgressCardProps {
  avance: SavingsGoalProgress
  onEditar: () => void
  onBorrar: () => void
}

export function GoalProgressCard({ avance, onEditar, onBorrar }: GoalProgressCardProps) {
  const porcentaje = Number(avance.percentage)
  // La barra se corta en 100 aunque el porcentaje lo supere: haber juntado de
  // más se comunica con el estado y el texto, no estirando la barra.
  const ancho = Number.isFinite(porcentaje) ? Math.min(porcentaje, TOPE_VISUAL) : 0
  const clase = avance.status === null ? 'sin-datos' : avance.status.toLowerCase()

  return (
    <li className={`meta meta--${clase}`}>
      <div className="meta__cabecera">
        <h3 className="meta__nombre">{avance.name}</h3>
        {avance.status === null ? (
          <span className="etiqueta">Sin datos</span>
        ) : (
          <span className="etiqueta">{ETIQUETA_DE_ESTADO[avance.status]}</span>
        )}
      </div>

      <p className="meta__cifras">
        {formatMoney(avance.saved, avance.currency)} de{' '}
        {formatMoney(avance.target, avance.currency)}
      </p>

      <div
        className="meta__barra"
        role="progressbar"
        aria-valuenow={Math.round(porcentaje)}
        aria-valuemin={0}
        aria-valuemax={TOPE_VISUAL}
        aria-label={`${avance.name}: ${formatPercent(avance.percentage)} juntado`}
      >
        <span className="meta__relleno" style={{ width: `${ancho}%` }} />
      </div>

      <div className="meta__pie">
        <span>{formatPercent(avance.percentage)}</span>
        <span>
          {Number(avance.remaining) === 0
            ? 'Ya la juntaste'
            : `Faltan ${formatMoney(avance.remaining, avance.currency)}`}
        </span>
      </div>

      <p className="meta__desde">
        Cuenta tu balance desde el {formatDate(avance.starts_on)}
        {avance.target_date !== null && ` · objetivo: ${formatDate(avance.target_date)}`}
      </p>

      <Proyeccion avance={avance} />

      <div className="meta__acciones">
        <button type="button" className="boton boton--secundario boton--chico" onClick={onEditar}>
          Editar
        </button>
        <button type="button" className="boton boton--secundario boton--chico" onClick={onBorrar}>
          Borrar
        </button>
      </div>
    </li>
  )
}

/**
 * El bloque estimado.
 *
 * Nunca muestra una fecha sin decir sobre cuántos meses se calculó: sin ese
 * dato al lado, una regla de tres se lee como una predicción, que es
 * exactamente lo que la especificación pide no hacer (docs/PROMPT.md §21.3).
 */
function Proyeccion({ avance }: { avance: SavingsGoalProgress }) {
  if (avance.status === 'ACHIEVED') {
    return null
  }

  if (avance.projection === null) {
    return (
      <p className="meta__proyeccion meta__proyeccion--sin-datos">
        Todavía no se puede estimar cuándo la alcanzás: hacen falta al menos dos
        meses cerrados de movimientos.
      </p>
    )
  }

  return <TextoDeProyeccion proyeccion={avance.projection} currency={avance.currency} />
}

function TextoDeProyeccion({
  proyeccion,
  currency,
}: {
  proyeccion: SavingsProjection
  currency: string
}) {
  const ritmo = formatMoney(proyeccion.monthly_rate, currency)
  const aclaracion = (
    <span className="meta__aclaracion">
      Es tu balance mensual promedio de {proyeccion.months_of_history} meses, no una
      predicción.
    </span>
  )

  if (proyeccion.months_to_target === null) {
    return (
      <p className="meta__proyeccion">
        A este ritmo ({ritmo} por mes) no llegás a juntarla. {aclaracion}
      </p>
    )
  }

  return (
    <p className="meta__proyeccion">
      A este ritmo ({ritmo} por mes) te faltan {proyeccion.months_to_target}{' '}
      {proyeccion.months_to_target === 1 ? 'mes' : 'meses'}
      {proyeccion.projected_date !== null && `, cerca de ${formatDate(proyeccion.projected_date)}`}.{' '}
      {aclaracion}
    </p>
  )
}
