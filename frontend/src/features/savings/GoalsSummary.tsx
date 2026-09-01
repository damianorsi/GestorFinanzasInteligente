import { Link } from 'react-router-dom'

import { formatMoney, formatPercent } from '@/utils/format'

import { useAvanceDeMetas } from './api'
import { ETIQUETA_DE_ESTADO } from './estados'

/** El dashboard resume: la lista completa está en la pantalla de metas. */
const MAXIMO_EN_EL_DASHBOARD = 3

/**
 * Resumen de metas para el dashboard.
 *
 * **Acá no va la proyección.** El dashboard muestra lo que se midió —cuánto
 * llevás juntado y cuánto falta—; la fecha estimada vive en la pantalla de
 * metas, que es donde entra la aclaración de sobre cuántos meses se calculó.
 * Traer el «te faltan 5 meses» sin esa línea al lado convertiría una regla de
 * tres en una predicción, que es justo lo que la especificación pide no hacer
 * (docs/PROMPT.md §21.3).
 *
 * El estado sí viaja, porque es una etiqueta y no una cifra con precisión
 * fingida. Cuando viene en null no se muestra nada: inventar un chip sería
 * afirmar algo que los datos no sostienen.
 */
export function GoalsSummary() {
  const avance = useAvanceDeMetas()

  // Igual que los vencimientos: si no hay nada, el bloque no aparece. Un
  // dashboard lleno de secciones vacías esconde las que sí tienen algo.
  if (!avance.isSuccess || avance.data.length === 0) {
    return null
  }

  return (
    <div className="grupo">
      <h2>Metas de ahorro</h2>
      <ul className="lista">
        {avance.data.slice(0, MAXIMO_EN_EL_DASHBOARD).map((meta) => (
          <li key={meta.goal_id} className="lista__item">
            <span className="lista__nombre">
              {meta.name}
              {/* El espacio es literal: sin él, el nombre y el chip se
                  concatenan en el árbol de accesibilidad y se lee
                  «Viaje a BrasilVas tarde». */}
              {meta.status !== null && (
                <> <span className="etiqueta">{ETIQUETA_DE_ESTADO[meta.status]}</span></>
              )}
            </span>
            <span className="tabla__numero">
              {formatPercent(meta.percentage)}
              {Number(meta.remaining) > 0 &&
                ` · faltan ${formatMoney(meta.remaining, meta.currency)}`}
            </span>
          </li>
        ))}
      </ul>
      <p className="pagina__subtitulo">
        <Link to="/savings-goals">
          {avance.data.length > MAXIMO_EN_EL_DASHBOARD
            ? `Ver las ${avance.data.length} metas`
            : 'Ver las metas'}
        </Link>
      </p>
    </div>
  )
}
