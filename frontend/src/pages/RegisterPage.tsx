import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { FormField } from '@/components/FormField'
import { useAuth } from '@/features/auth/useAuth'
import { ApiError, NetworkError } from '@/services/api'

const LARGO_MINIMO_CONTRASENA = 8

export function RegisterPage() {
  const { registrarse } = useAuth()
  const navigate = useNavigate()

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [erroresPorCampo, setErroresPorCampo] = useState<Record<string, string>>({})
  const [enviando, setEnviando] = useState(false)

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault()
    setError(null)
    setErroresPorCampo({})

    // Validación de cliente antes de ir al servidor: evita un ida y vuelta
    // para un error que se puede detectar acá.
    if (password.length < LARGO_MINIMO_CONTRASENA) {
      setErroresPorCampo({
        password: `La contraseña necesita al menos ${LARGO_MINIMO_CONTRASENA} caracteres.`,
      })
      return
    }

    setEnviando(true)
    try {
      await registrarse(email, password, fullName)
      navigate('/dashboard', { replace: true })
    } catch (excepcion) {
      if (excepcion instanceof NetworkError) {
        setError(excepcion.message)
      } else if (excepcion instanceof ApiError) {
        // El mapeo va por `code`, nunca por el texto del mensaje: el texto es
        // para leer, el código es el contrato.
        if (excepcion.code === 'email_already_registered') {
          setErroresPorCampo({ email: 'Ya existe una cuenta con ese email.' })
        } else if (excepcion.code === 'validation_error') {
          const porCampo: Record<string, string> = {}
          for (const detalle of excepcion.details) {
            const campo = detalle.field === 'full_name' ? 'fullName' : detalle.field
            porCampo[campo] = detalle.reason
          }
          setErroresPorCampo(porCampo)
          if (Object.keys(porCampo).length === 0) setError(excepcion.message)
        } else {
          setError(excepcion.message)
        }
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
        <h1>Crear cuenta</h1>

        {error && (
          <p className="auth__error" role="alert">
            {error}
          </p>
        )}

        <FormField
          id="fullName"
          label="Nombre y apellido"
          value={fullName}
          onChange={(evento) => setFullName(evento.target.value)}
          error={erroresPorCampo.fullName}
          autoComplete="name"
          required
        />
        <FormField
          id="email"
          label="Email"
          type="email"
          value={email}
          onChange={(evento) => setEmail(evento.target.value)}
          error={erroresPorCampo.email}
          autoComplete="email"
          required
        />
        <FormField
          id="password"
          label="Contraseña"
          type="password"
          value={password}
          onChange={(evento) => setPassword(evento.target.value)}
          error={erroresPorCampo.password}
          hint={`Mínimo ${LARGO_MINIMO_CONTRASENA} caracteres.`}
          autoComplete="new-password"
          required
        />

        <button type="submit" className="boton boton--primario" disabled={enviando}>
          {enviando ? 'Creando…' : 'Crear cuenta'}
        </button>

        <p className="auth__pie">
          ¿Ya tenés cuenta? <Link to="/login">Ingresá</Link>
        </p>
      </form>
    </div>
  )
}
