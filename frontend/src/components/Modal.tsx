import { useEffect, useId, useRef } from 'react'
import type { ReactNode } from 'react'

const SELECTOR_ENFOCABLES = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ')

interface ModalProps {
  titulo: string
  abierto: boolean
  onCerrar: () => void
  children: ReactNode
}

/**
 * Diálogo modal accesible.
 *
 * Se implementa a mano en vez de con `<dialog>` nativo porque jsdom todavía no
 * implementa `showModal()`, y con el elemento nativo los tests de teclado no
 * podrían ejercitar nada.
 *
 * Cumple lo que un modal tiene que cumplir para ser usable sin mouse: el foco
 * entra al abrirse, queda atrapado adentro mientras está abierto, Escape lo
 * cierra y el foco vuelve al elemento que lo abrió.
 */
export function Modal({ titulo, abierto, onCerrar, children }: ModalProps) {
  const contenedor = useRef<HTMLDivElement>(null)
  const elementoPrevio = useRef<HTMLElement | null>(null)
  const idTitulo = useId()

  useEffect(() => {
    if (!abierto) return

    elementoPrevio.current = document.activeElement as HTMLElement | null
    const enfocables = () =>
      Array.from(
        contenedor.current?.querySelectorAll<HTMLElement>(SELECTOR_ENFOCABLES) ?? [],
      )
    enfocables()[0]?.focus()

    const alPresionar = (evento: KeyboardEvent) => {
      if (evento.key === 'Escape') {
        evento.preventDefault()
        onCerrar()
        return
      }
      if (evento.key !== 'Tab') return

      const lista = enfocables()
      const primero = lista.at(0)
      const ultimo = lista.at(-1)
      if (!primero || !ultimo) return

      // Sin esto, tabular desde el último control saca el foco del modal y lo
      // manda al contenido de atrás, que está tapado y no debería ser operable.
      if (evento.shiftKey && document.activeElement === primero) {
        evento.preventDefault()
        ultimo.focus()
      } else if (!evento.shiftKey && document.activeElement === ultimo) {
        evento.preventDefault()
        primero.focus()
      }
    }

    document.addEventListener('keydown', alPresionar)
    return () => {
      document.removeEventListener('keydown', alPresionar)
      elementoPrevio.current?.focus()
    }
  }, [abierto, onCerrar])

  if (!abierto) return null

  return (
    <div className="modal__fondo" onMouseDown={onCerrar}>
      <div
        ref={contenedor}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={idTitulo}
        // El click dentro no debe cerrar; solo el del fondo.
        onMouseDown={(evento) => evento.stopPropagation()}
      >
        <div className="modal__encabezado">
          <h2 id={idTitulo}>{titulo}</h2>
          <button
            type="button"
            className="modal__cerrar"
            onClick={onCerrar}
            aria-label="Cerrar"
          >
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
