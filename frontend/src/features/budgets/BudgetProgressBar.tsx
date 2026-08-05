import type { BudgetProgressEntry } from '@/types/api'
import { formatMoney, formatPercent } from '@/utils/format'

const ETIQUETA_DE_ESTADO = {
  OK: 'dentro del tope',
  WARNING: 'cerca del tope',
  EXCEEDED: 'excedido',
} as const

const TOPE_VISUAL = 100

export function BudgetProgressBar({ entrada }: { entrada: BudgetProgressEntry }) {
  const porcentaje = Number(entrada.percentage)
  // La barra se corta en 100 aunque el porcentaje lo supere; el exceso se
  // comunica con el color, el texto y el restante en negativo.
  const ancho = Number.isFinite(porcentaje) ? Math.min(porcentaje, TOPE_VISUAL) : 0

  return (
    <li className={`progreso progreso--${entrada.status.toLowerCase()}`}>
      <div className="progreso__fila">
        <span className="progreso__nombre">{entrada.category_name}</span>
        <span className="progreso__cifras">
          {formatMoney(entrada.spent, 'ARS')} de {formatMoney(entrada.budgeted, 'ARS')}
        </span>
      </div>

      <div
        className="progreso__barra"
        role="progressbar"
        aria-valuenow={Math.round(porcentaje)}
        aria-valuemin={0}
        aria-valuemax={TOPE_VISUAL}
        aria-label={`${entrada.category_name}: ${ETIQUETA_DE_ESTADO[entrada.status]}`}
      >
        <span className="progreso__relleno" style={{ width: `${ancho}%` }} />
      </div>

      <div className="progreso__fila progreso__fila--pie">
        <span>{formatPercent(entrada.percentage)}</span>
        <span>
          {Number(entrada.remaining) < 0 ? 'Te pasaste ' : 'Te queda '}
          {formatMoney(entrada.remaining.replace('-', ''), 'ARS')}
        </span>
      </div>
    </li>
  )
}
