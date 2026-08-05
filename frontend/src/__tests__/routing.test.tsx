import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'

import App from '@/App'
import { BASE, TOKENS } from '@/test/handlers'
import { renderConProviders } from '@/test/render'
import { server } from '@/test/server'

function conSesionGuardada() {
  localStorage.setItem('gfp.refresh_token', TOKENS.refresh_token)
}

describe('ruteo y guards', () => {
  it('manda al login si se entra a una ruta privada sin sesión', async () => {
    // Arrange / Act
    renderConProviders(<App />, { ruta: '/dashboard' })

    // Assert
    expect(await screen.findByRole('heading', { name: /iniciar sesión/i })).toBeVisible()
  })

  it('restaura la sesión guardada y muestra el resumen', async () => {
    // Arrange
    conSesionGuardada()

    // Act
    renderConProviders(<App />, { ruta: '/dashboard' })

    // Assert
    expect(await screen.findByRole('heading', { name: /hola, damián/i })).toBeVisible()
  })

  it('no expulsa al login mientras verifica la sesión', async () => {
    /*
     * El access token vive en memoria, así que al refrescar la página hay un
     * instante sin sesión resuelta. Si el guard decidiera ahí, mandaría al
     * login a alguien autenticado en cada F5.
     */
    // Arrange
    conSesionGuardada()

    // Act
    renderConProviders(<App />, { ruta: '/dashboard' })

    // Assert
    expect(screen.getByRole('status')).toHaveTextContent(/verificando tu sesión/i)
    expect(screen.queryByRole('heading', { name: /iniciar sesión/i })).not.toBeInTheDocument()
    await screen.findByRole('heading', { name: /hola, damián/i })
  })

  it('manda al login si el refresh guardado ya no sirve', async () => {
    // Arrange
    conSesionGuardada()
    server.use(
      http.post(`${BASE}/auth/refresh`, () =>
        HttpResponse.json(
          { code: 'invalid_token', message: 'Revocado.', details: [] },
          { status: 401 },
        ),
      ),
    )

    // Act
    renderConProviders(<App />, { ruta: '/dashboard' })

    // Assert
    expect(await screen.findByRole('heading', { name: /iniciar sesión/i })).toBeVisible()
  })

  it('vuelve a la ruta que se quería abrir después de iniciar sesión', async () => {
    // Arrange
    renderConProviders(<App />, { ruta: '/budgets' })
    await screen.findByRole('heading', { name: /iniciar sesión/i })

    // Act
    const usuario = userEvent.setup()
    await usuario.type(screen.getByLabelText(/email/i), 'damian@ejemplo.com')
    await usuario.type(screen.getByLabelText(/contraseña/i), 'una-contrasena-larga')
    await usuario.click(screen.getByRole('button', { name: /ingresar/i }))

    // Assert
    expect(await screen.findByRole('heading', { name: /presupuestos/i })).toBeVisible()
  })

  it('no deja volver al login con la sesión ya iniciada', async () => {
    // Arrange
    conSesionGuardada()

    // Act
    renderConProviders(<App />, { ruta: '/login' })

    // Assert
    expect(await screen.findByRole('heading', { name: /hola, damián/i })).toBeVisible()
  })

  it('muestra una página propia para una ruta inexistente', async () => {
    // Arrange / Act
    renderConProviders(<App />, { ruta: '/no-existe' })

    // Assert
    expect(await screen.findByRole('heading', { name: /no encontrada/i })).toBeVisible()
  })

  it('cerrar sesión vuelve al login', async () => {
    // Arrange
    conSesionGuardada()
    renderConProviders(<App />, { ruta: '/dashboard' })
    await screen.findByRole('heading', { name: /hola, damián/i })

    // Act
    await userEvent.setup().click(screen.getByRole('button', { name: /cerrar sesión/i }))

    // Assert
    expect(await screen.findByRole('heading', { name: /iniciar sesión/i })).toBeVisible()
  })
})

describe('DashboardPage', () => {
  it('muestra los totales formateados en es-AR', async () => {
    // Arrange
    conSesionGuardada()

    // Act
    renderConProviders(<App />, { ruta: '/dashboard' })

    // Assert
    await screen.findByRole('heading', { name: /hola, damián/i })
    await waitFor(() => expect(screen.getByText(/850\.000,00/)).toBeVisible())
    expect(screen.getByText(/450\.000,50/)).toBeVisible()
  })

  it('ofrece reintentar si el resumen falla', async () => {
    // Arrange
    conSesionGuardada()
    server.use(
      http.get(`${BASE}/reports/summary`, () =>
        HttpResponse.json(
          { code: 'internal_error', message: 'Falló.', details: [] },
          { status: 500 },
        ),
      ),
    )

    // Act
    renderConProviders(<App />, { ruta: '/dashboard' })

    // Assert
    expect(await screen.findByRole('button', { name: /reintentar/i })).toBeVisible()
  })
})
