import { ApiError, NetworkError } from '@/services/api'

export interface ErroresDeFormulario {
  /** Error general, para mostrar arriba del formulario. */
  general: string | null
  /** Errores por campo, ya con los nombres que usa el formulario. */
  porCampo: Record<string, string>
}

const SIN_ERRORES: ErroresDeFormulario = { general: null, porCampo: {} }

/**
 * Traduce una excepción del cliente HTTP a errores de formulario.
 *
 * El mapeo se hace por `code`, nunca por el texto de `message`: el texto es
 * para que lo lea una persona y puede cambiar sin aviso; el código es el
 * contrato (docs/PROMPT.md §5.3).
 *
 * `alias` traduce los nombres de campo del backend a los del formulario, para
 * los casos donde no coinciden (`full_name` contra `fullName`).
 */
export function aErroresDeFormulario(
  excepcion: unknown,
  {
    porCodigo = {},
    alias = {},
  }: {
    porCodigo?: Record<string, { campo?: string; mensaje: string }>
    alias?: Record<string, string>
  } = {},
): ErroresDeFormulario {
  if (excepcion instanceof NetworkError) {
    return { ...SIN_ERRORES, general: excepcion.message }
  }

  if (!(excepcion instanceof ApiError)) {
    return { ...SIN_ERRORES, general: 'Ocurrió un error inesperado.' }
  }

  const especifico = porCodigo[excepcion.code]
  if (especifico) {
    return especifico.campo
      ? { general: null, porCampo: { [especifico.campo]: especifico.mensaje } }
      : { general: especifico.mensaje, porCampo: {} }
  }

  if (excepcion.code === 'validation_error' && excepcion.details.length > 0) {
    const porCampo: Record<string, string> = {}
    for (const detalle of excepcion.details) {
      porCampo[alias[detalle.field] ?? detalle.field] = detalle.reason
    }
    return { general: null, porCampo }
  }

  // Sin mapeo específico se muestra el mensaje del backend, que ya viene en
  // español y suele ser accionable (por ejemplo, el 409 de borrado enumera qué
  // está bloqueando la operación).
  return { general: excepcion.message, porCampo: {} }
}
