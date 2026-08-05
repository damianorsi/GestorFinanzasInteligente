import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'

import { LoginPage } from '@/pages/LoginPage'
import { getAccessToken } from '@/services/session'
import { BASE } from '@/test/handlers'
import { renderConProviders } from '@/test/render'
import { server } from '@/test/server'

async function completarYEnviar(email: string, password: string) {
  const usuario = userEvent.setup()
  await usuario.type(screen.getByLabelText(/email/i), email)
  await usuario.type(screen.getByLabelText(/contraseña/i), password)
  await usuario.click(screen.getByRole('button', { name: /ingresar/i }))
}

describe('LoginPage', () => {
  it('guarda la sesión con credenciales válidas', async () => {
    // Arrange
    renderConProviders(<LoginPage />)

    // Act
    await completarYEnviar('damian@ejemplo.com', 'una-contrasena-larga')

    // Assert
    await waitFor(() => expect(getAccessToken()).toBe('access-1'))
  })

  it('muestra el mensaje del servidor si las credenciales son inválidas', async () => {
    // Arrange
    renderConProviders(<LoginPage />)

    // Act
    await completarYEnviar('damian@ejemplo.com', 'incorrecta')

    // Assert
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /email o contraseña incorrectos/i,
    )
    expect(getAccessToken()).toBeNull()
  })

  it('avisa cuando no hay conexión, sin confundirlo con credenciales malas', async () => {
    // Arrange
    server.use(http.post(`${BASE}/auth/login`, () => HttpResponse.error()))
    renderConProviders(<LoginPage />)

    // Act
    await completarYEnviar('damian@ejemplo.com', 'una-contrasena-larga')

    // Assert
    expect(await screen.findByRole('alert')).toHaveTextContent(/no se pudo conectar/i)
  })

  it('deshabilita el botón mientras envía, para no duplicar el intento', async () => {
    // Arrange
    server.use(
      http.post(`${BASE}/auth/login`, async () => {
        await new Promise((resolver) => setTimeout(resolver, 50))
        return HttpResponse.json({
          access_token: 'a',
          refresh_token: 'r',
          token_type: 'bearer',
          expires_in: 900,
        })
      }),
    )
    renderConProviders(<LoginPage />)

    // Act
    await completarYEnviar('damian@ejemplo.com', 'una-contrasena-larga')

    // Assert
    expect(screen.getByRole('button', { name: /ingresando/i })).toBeDisabled()
  })

  it('asocia cada etiqueta con su campo', () => {
    // Arrange / Act
    renderConProviders(<LoginPage />)

    // Assert: getByLabelText falla si el label no está asociado.
    expect(screen.getByLabelText(/email/i)).toHaveAttribute('type', 'email')
    expect(screen.getByLabelText(/contraseña/i)).toHaveAttribute('type', 'password')
  })
})
