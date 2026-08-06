import { Cargando, ErrorVisible, SinDatos } from '@/components/Feedback'
import { formatDate } from '@/utils/format'

import { useOcurrencias } from './api'

/**
 * Historial de una regla.
 *
 * Distingue tres estados que se ven parecido pero significan cosas distintas:
 * generada y vigente, generada y borrada después, y salteada. El de "borrada"
 * importa porque explica por qué el job no la va a volver a crear.
 */
export function OccurrencesList({ ruleId }: { ruleId: number }) {
  const ocurrencias = useOcurrencias(ruleId)

  if (ocurrencias.isPending) return <Cargando mensaje="Cargando el historial…" />

  if (ocurrencias.isError) {
    return (
      <ErrorVisible
        mensaje="No se pudo cargar el historial."
        onReintentar={() => void ocurrencias.refetch()}
      />
    )
  }

  if (ocurrencias.data.length === 0) {
    return (
      <SinDatos
        titulo="Todavía no generó nada"
        detalle="Los movimientos se crean el día que corresponde, nunca por adelantado."
      />
    )
  }

  return (
    <ul className="lista">
      {ocurrencias.data.map((ocurrencia) => {
        const salteada = ocurrencia.status === 'SKIPPED'
        const borrada = !salteada && ocurrencia.transaction_id === null
        return (
          <li key={ocurrencia.id} className="lista__item">
            <span className="lista__nombre">{formatDate(ocurrencia.occurred_on)}</span>
            {salteada && <span className="etiqueta">salteada</span>}
            {borrada && <span className="etiqueta">generada y borrada</span>}
            {!salteada && !borrada && <span className="etiqueta">generada</span>}
          </li>
        )
      })}
    </ul>
  )
}
