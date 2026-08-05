import type { ReactNode, SelectHTMLAttributes } from 'react'

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  id: string
  label: string
  error?: string
  children: ReactNode
}

/** Selector accesible, con el mismo contrato que `FormField`. */
export function SelectField({ id, label, error, children, ...props }: SelectFieldProps) {
  const idError = `${id}-error`

  return (
    <div className="campo">
      <label htmlFor={id}>{label}</label>
      <select
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? idError : undefined}
        {...props}
      >
        {children}
      </select>
      {error && (
        <p id={idError} className="campo__error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
