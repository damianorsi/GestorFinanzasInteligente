import type { ReactNode } from 'react'

/** Indicador de carga con texto para lectores de pantalla. */
export function Cargando({ mensaje = 'Cargando…' }: { mensaje?: string }) {
  return (
    <div className="estado estado--cargando" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{mensaje}</span>
    </div>
  )
}

/**
 * Error visible.
 *
 * `role="alert"` para que se anuncie apenas aparece: un error que solo se ve
 * es invisible para quien navega con lector de pantalla.
 */
export function ErrorVisible({
  mensaje,
  onReintentar,
}: {
  mensaje: string
  onReintentar?: () => void
}) {
  return (
    <div className="estado estado--error" role="alert">
      <p>{mensaje}</p>
      {onReintentar && (
        <button type="button" className="boton boton--secundario" onClick={onReintentar}>
          Reintentar
        </button>
      )}
    </div>
  )
}

/** Estado vacío: nunca dejar una pantalla en blanco. */
export function SinDatos({
  titulo,
  detalle,
  accion,
}: {
  titulo: string
  detalle?: string
  accion?: ReactNode
}) {
  return (
    <div className="estado estado--vacio">
      <p className="estado__titulo">{titulo}</p>
      {detalle && <p className="estado__detalle">{detalle}</p>}
      {accion}
    </div>
  )
}
