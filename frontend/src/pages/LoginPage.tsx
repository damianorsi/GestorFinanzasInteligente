import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { FormField } from '@/components/FormField'
import { useAuth } from '@/features/auth/useAuth'
import { ApiError, NetworkError } from '@/services/api'

export function LoginPage() {
  const { iniciarSesion } = useAuth()
  const navigate = useNavigate()
  const ubicacion = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault()
    setError(null)
    setEnviando(true)
    try {
      await iniciarSesion(email, password)
      const destino = (ubicacion.state as { desde?: string } | null)?.desde ?? '/dashboard'
      navigate(destino, { replace: true })
    } catch (excepcion) {
      if (excepcion instanceof NetworkError) {
        setError(excepcion.message)
      } else if (excepcion instanceof ApiError) {
        // Se muestra el `message` del backend, que ya viene en español y es
        // deliberadamente genérico para no revelar si el email existe.
        setError(excepcion.message)
      } else {
        setError('Ocurrió un error inesperado.')
      }
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="auth">
      <form className="auth__form" onSubmit={(evento) => void enviar(evento)} noValidate>
        <h1>Iniciar sesión</h1>

        {error && (
          <p className="auth__error" role="alert">
            {error}
          </p>
        )}

        <FormField
          id="email"
          label="Email"
          type="email"
          value={email}
          onChange={(evento) => setEmail(evento.target.value)}
          autoComplete="email"
          required
        />
        <FormField
          id="password"
          label="Contraseña"
          type="password"
          value={password}
          onChange={(evento) => setPassword(evento.target.value)}
          autoComplete="current-password"
          required
        />

        <button type="submit" className="boton boton--primario" disabled={enviando}>
          {enviando ? 'Ingresando…' : 'Ingresar'}
        </button>

        <p className="auth__pie">
          ¿No tenés cuenta? <Link to="/register">Creá una</Link>
        </p>
      </form>
    </div>
  )
}
