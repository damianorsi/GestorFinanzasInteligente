import { useEffect, useRef, useState } from 'react'

import { Cargando, ErrorVisible } from '@/components/Feedback'
import { MessageBubble } from '@/features/chat/MessageBubble'
import type { MensajeEnPantalla } from '@/features/chat/MessageBubble'
import { useHistorialDeChat, usePreguntarAlAsistente } from '@/features/chat/api'
import { ApiError } from '@/services/api'
import {
  clearConversationId,
  getConversationId,
  saveConversationId,
} from '@/services/session'
import { aErroresDeFormulario } from '@/utils/apiErrors'

/**
 * Preguntas de arranque.
 *
 * No son decoración: el asistente responde con herramientas acotadas y quien
 * llega por primera vez no tiene forma de saber qué sabe contestar. Mostrar
 * ejemplos reales evita la primera pregunta que no puede responder.
 */
const SUGERENCIAS = [
  '¿Cuánto gasté este mes?',
  '¿En qué categoría gasto más?',
  '¿Cómo voy con mis presupuestos?',
  '¿Gasté más que el mes pasado?',
]

const LARGO_MAXIMO = 1000

interface ErrorDeChat {
  mensaje: string
  /** El cupo no se reintenta: volver a mandar ya mismo falla otra vez. */
  esCupo: boolean
}

export function ChatPage() {
  const [conversacion, setConversacion] = useState<string | null>(() => getConversationId())
  const [mensajes, setMensajes] = useState<MensajeEnPantalla[]>([])
  const [texto, setTexto] = useState('')
  const [error, setError] = useState<ErrorDeChat | null>(null)

  const historial = useHistorialDeChat(conversacion)
  const preguntar = usePreguntarAlAsistente()

  const listaRef = useRef<HTMLOListElement>(null)
  const entradaRef = useRef<HTMLTextAreaElement>(null)

  // El historial se vuelca una sola vez, al llegar: a partir de ahí la lista en
  // pantalla es la fuente, y volver a copiarla pisaría los mensajes nuevos.
  const historialVolcado = useRef(false)
  useEffect(() => {
    if (historial.data && !historialVolcado.current) {
      historialVolcado.current = true
      setMensajes(historial.data)
    }
  }, [historial.data])

  // `scrollTop` y no `scrollTo`: jsdom no implementa el segundo, y la
  // diferencia de comportamiento no justifica que los tests no puedan montar
  // esta pantalla.
  useEffect(() => {
    const lista = listaRef.current
    if (lista) lista.scrollTop = lista.scrollHeight
  }, [mensajes, preguntar.isPending])

  const enviar = async (consulta: string) => {
    const limpio = consulta.trim()
    if (!limpio || preguntar.isPending) return

    setError(null)
    setTexto('')
    const ahora = new Date().toISOString()
    setMensajes((previos) => [...previos, { role: 'USER', content: limpio, created_at: ahora }])

    try {
      const respuesta = await preguntar.mutateAsync({
        message: limpio,
        conversationId: conversacion,
      })

      if (conversacion === null) {
        setConversacion(respuesta.conversation_id)
        saveConversationId(respuesta.conversation_id)
        // Ya se está mostrando la conversación: que la query del historial no
        // la vuelva a traer y duplique lo que hay en pantalla.
        historialVolcado.current = true
      }

      setMensajes((previos) => [
        ...previos,
        {
          role: 'ASSISTANT',
          content: respuesta.content,
          created_at: new Date().toISOString(),
          degradado: respuesta.degraded,
        },
      ])
    } catch (excepcion) {
      // Se saca la burbuja optimista y el texto vuelve al campo. Si el error es
      // de cupo el backend ni siquiera lo guardó, así que dejarla en pantalla
      // sería mostrar un mensaje que no existe.
      setMensajes((previos) => previos.slice(0, -1))
      setTexto(limpio)
      const esCupo = excepcion instanceof ApiError && excepcion.code === 'rate_limit_exceeded'
      setError({
        mensaje:
          aErroresDeFormulario(excepcion).general ?? 'No se pudo consultar al asistente.',
        esCupo,
      })
    } finally {
      entradaRef.current?.focus()
    }
  }

  const empezarDeNuevo = () => {
    clearConversationId()
    setConversacion(null)
    setMensajes([])
    setError(null)
    historialVolcado.current = true
    entradaRef.current?.focus()
  }

  const ultimaConsulta = [...mensajes].reverse().find((m) => m.role === 'USER')?.content ?? ''
  const ultimoEsDegradado = mensajes.at(-1)?.degradado === true
  const cargandoHistorial = conversacion !== null && historial.isPending

  return (
    <section className="pagina chat">
      <div className="pagina__encabezado">
        <div>
          <h1>Asistente</h1>
          <p className="pagina__subtitulo">
            Preguntale sobre tus movimientos. Solo responde con datos tuyos.
          </p>
        </div>
        {mensajes.length > 0 && (
          <button type="button" className="boton boton--secundario" onClick={empezarDeNuevo}>
            Nueva conversación
          </button>
        )}
      </div>

      {cargandoHistorial && <Cargando mensaje="Cargando la conversación…" />}

      {historial.isError && (
        <ErrorVisible
          mensaje="No se pudo cargar la conversación anterior. Podés empezar una nueva."
          onReintentar={empezarDeNuevo}
        />
      )}

      {/*
        `role="log"` con `aria-live="polite"` para que un lector de pantalla
        anuncie los mensajes nuevos sin interrumpir lo que se esté leyendo.
      */}
      <ol
        ref={listaRef}
        className="chat__historial"
        role="log"
        aria-live="polite"
        aria-label="Conversación con el asistente"
      >
        {mensajes.map((mensaje, indice) => (
          <MessageBubble key={`${mensaje.created_at}-${indice}`} mensaje={mensaje} />
        ))}

        {preguntar.isPending && (
          <li className="chat__mensaje chat__mensaje--asistente">
            <div className="chat__burbuja chat__burbuja--escribiendo">
              <span className="chat__puntos" aria-hidden="true">
                <span />
                <span />
                <span />
              </span>
              <span className="visualmente-oculto">El asistente está escribiendo…</span>
            </div>
          </li>
        )}
      </ol>

      {mensajes.length === 0 && !cargandoHistorial && (
        <div className="chat__sugerencias">
          <p className="chat__sugerencias-titulo">Probá con alguna de estas:</p>
          <div className="chat__sugerencias-lista">
            {SUGERENCIAS.map((sugerencia) => (
              <button
                key={sugerencia}
                type="button"
                className="chat__sugerencia"
                onClick={() => void enviar(sugerencia)}
              >
                {sugerencia}
              </button>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className={`aviso ${error.esCupo ? 'aviso--alerta' : ''}`.trim()} role="alert">
          {error.mensaje}
        </div>
      )}

      {ultimoEsDegradado && !error && (
        <div className="chat__reintento">
          <button
            type="button"
            className="boton boton--secundario boton--chico"
            onClick={() => void enviar(ultimaConsulta)}
          >
            Reintentar la última pregunta
          </button>
        </div>
      )}

      <form
        className="chat__envio"
        onSubmit={(evento) => {
          evento.preventDefault()
          void enviar(texto)
        }}
      >
        <label className="visualmente-oculto" htmlFor="chat-mensaje">
          Tu consulta
        </label>
        <textarea
          id="chat-mensaje"
          ref={entradaRef}
          className="chat__entrada"
          rows={2}
          maxLength={LARGO_MAXIMO}
          placeholder="¿Cuánto gasté en comida este mes?"
          value={texto}
          onChange={(evento) => setTexto(evento.target.value)}
          onKeyDown={(evento) => {
            // Enter manda y Shift+Enter hace salto de línea, que es lo que
            // espera cualquiera que haya usado un chat.
            if (evento.key === 'Enter' && !evento.shiftKey) {
              evento.preventDefault()
              void enviar(texto)
            }
          }}
        />
        <button
          type="submit"
          className="boton boton--primario"
          disabled={preguntar.isPending || texto.trim() === ''}
        >
          {preguntar.isPending ? 'Consultando…' : 'Enviar'}
        </button>
      </form>
    </section>
  )
}
