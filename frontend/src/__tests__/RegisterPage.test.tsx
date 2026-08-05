import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'

import { RegisterPage } from '@/pages/RegisterPage'
import { getAccessToken } from '@/services/session'
import { BASE } from '@/test/handlers'
import { renderConProviders } from '@/test/render'
import { server } from '@/test/server'

async function completarYEnviar(
  email = 'damian@ejemplo.com',
  password = 'una-contrasena-larga',
  nombre = 'Damián Orsi',
) {
  const usuario = userEvent.setup()
  await usuario.type(screen.getByLabelText(/nombre y apellido/i), nombre)
  await usuario.type(screen.getByLabelText(/email/i), email)
  await usuario.type(screen.getByLabelText(/contraseña/i), password)
  await usuario.click(screen.getByRole('button', { name: /crear cuenta/i }))
}

describe('RegisterPage', () => {
  it('crea la cuenta e inicia sesión de una', async () => {
    // Arrange
    renderConProviders(<RegisterPage />)

    // Act
    await completarYEnviar()

    // Assert
    await waitFor(() => expect(getAccessToken()).toBe('access-1'))
  })

  it('valida el largo de la contraseña sin ir al servidor', async () => {
    // Arrange
    let llamadas = 0
    server.use(
      http.post(`${BASE}/auth/register`, () => {
        llamadas += 1
        return HttpResponse.json({}, { status: 201 })
      }),
    )
    renderConProviders(<RegisterPage />)

    // Act
    await completarYEnviar('damian@ejemplo.com', 'corta')

    // Assert
    expect(await screen.findByRole('alert')).toHaveTextContent(/al menos 8 caracteres/i)
    expect(llamadas).toBe(0)
  })

  it('marca el campo email cuando ya existe la cuenta', async () => {
    // Arrange
    renderConProviders(<RegisterPage />)

    // Act
    await completarYEnviar('repetido@ejemplo.com')

    // Assert
    const error = await screen.findByRole('alert')
    expect(error).toHaveTextContent(/ya existe una cuenta con ese email/i)
    expect(screen.getByLabelText(/email/i)).toHaveAttribute('aria-invalid', 'true')
  })

  it('mapea los errores de validación campo por campo', async () => {
    // Arrange
    server.use(
      http.post(`${BASE}/auth/register`, () =>
        HttpResponse.json(
          {
            code: 'validation_error',
            message: 'Los datos enviados no son válidos.',
            details: [{ field: 'email', reason: 'No es un email válido' }],
          },
          { status: 422 },
        ),
      ),
    )
    renderConProviders(<RegisterPage />)

    // Act
    await completarYEnviar()

    // Assert
    expect(await screen.findByRole('alert')).toHaveTextContent(/no es un email válido/i)
    expect(screen.getByLabelText(/email/i)).toHaveAttribute('aria-invalid', 'true')
  })

  it('el mapeo va por code y no por el texto del mensaje', async () => {
    /*
     * El mismo 409 con otro texto tiene que seguir marcando el campo: si el
     * frontend mirara el mensaje, cambiar una palabra en el backend rompería
     * el formulario sin que ningún test del backend lo note.
     */
    // Arrange
    server.use(
      http.post(`${BASE}/auth/register`, () =>
        HttpResponse.json(
          {
            code: 'email_already_registered',
            message: 'Texto completamente distinto.',
            details: [],
          },
          { status: 409 },
        ),
      ),
    )
    renderConProviders(<RegisterPage />)

    // Act
    await completarYEnviar()

    // Assert
    await waitFor(() =>
      expect(screen.getByLabelText(/email/i)).toHaveAttribute('aria-invalid', 'true'),
    )
  })
})
