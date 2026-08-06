import { formatTime } from '@/utils/format'
import type { ChatRole } from '@/types/api'

export interface MensajeEnPantalla {
  role: ChatRole
  content: string
  created_at: string
  /** Respuesta de fallback: el asistente no llegó a consultar los datos. */
  degradado?: boolean
}

/**
 * Una burbuja de la conversación.
 *
 * El contenido se parte por saltos de línea en vez de usar `white-space:
 * pre-wrap` sobre texto crudo: el asistente responde con listas cortas y así
 * cada ítem queda como un párrafo, que es lo que un lector de pantalla
 * anuncia bien.
 */
export function MessageBubble({ mensaje }: { mensaje: MensajeEnPantalla }) {
  const esDelUsuario = mensaje.role === 'USER'
  const hora = formatTime(mensaje.created_at)

  return (
    <li
      className={`chat__mensaje ${esDelUsuario ? 'chat__mensaje--propio' : 'chat__mensaje--asistente'}`}
    >
      <div
        className={`chat__burbuja ${mensaje.degradado ? 'chat__burbuja--degradada' : ''}`.trim()}
      >
        <span className="visualmente-oculto">{esDelUsuario ? 'Vos:' : 'Asistente:'}</span>
        {mensaje.content.split('\n').map((linea, indice) => (
          // El índice alcanza como key: las líneas de un mensaje ya emitido no
          // se reordenan ni se insertan en el medio.
          <p key={indice} className="chat__linea">
            {linea}
          </p>
        ))}
      </div>
      {hora && <span className="chat__hora">{hora}</span>}
    </li>
  )
}
