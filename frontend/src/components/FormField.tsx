import type { InputHTMLAttributes } from 'react'

interface FormFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  id: string
  label: string
  /** Mensaje de error del campo; si está presente, marca el input como inválido. */
  error?: string
  hint?: string
}

/**
 * Campo de formulario accesible.
 *
 * El `label` está asociado por `htmlFor`, y el error se enlaza con
 * `aria-describedby` para que un lector de pantalla lo anuncie al enfocar el
 * campo en vez de dejarlo como texto suelto al lado.
 */
export function FormField({ id, label, error, hint, ...props }: FormFieldProps) {
  const idError = `${id}-error`
  const idAyuda = `${id}-hint`
  const descritoPor = [error ? idError : null, hint ? idAyuda : null]
    .filter(Boolean)
    .join(' ')

  return (
    <div className="campo">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={descritoPor || undefined}
        {...props}
      />
      {hint && !error && (
        <p id={idAyuda} className="campo__ayuda">
          {hint}
        </p>
      )}
      {error && (
        <p id={idError} className="campo__error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
