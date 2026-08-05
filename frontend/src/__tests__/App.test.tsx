import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App, { type HealthPayload } from '../App'

const SALUD_OK: HealthPayload = {
  status: 'ok',
  environment: 'test',
  timezone: 'America/Argentina/Buenos_Aires',
  default_currency: 'ARS',
  database: 'ok',
  scheduler: 'disabled',
}

function mockearFetch(respuesta: Partial<Response> & { json: () => Promise<unknown> }) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta))
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('App', () => {
  it('muestra el título de la aplicación', async () => {
    // Arrange
    mockearFetch({ ok: true, json: () => Promise.resolve(SALUD_OK) })

    // Act
    render(<App />)

    // Assert
    expect(
      screen.getByRole('heading', { name: /gestor inteligente de finanzas personales/i }),
    ).toBeInTheDocument()
    // Se espera a que el fetch se resuelva: si el test termina antes, el
    // setState posterior queda fuera de act() y React emite un warning.
    await waitFor(() => {
      expect(screen.getByTestId('estado-conexion')).toHaveTextContent('Backend conectado')
    })
  })

  it('informa que el backend está conectado cuando /health responde 200', async () => {
    // Arrange
    mockearFetch({ ok: true, json: () => Promise.resolve(SALUD_OK) })

    // Act
    render(<App />)

    // Assert
    await waitFor(() => {
      expect(screen.getByTestId('estado-conexion')).toHaveTextContent('Backend conectado')
    })
    expect(screen.getByText('America/Argentina/Buenos_Aires')).toBeInTheDocument()
    expect(screen.getByText('ARS')).toBeInTheDocument()
  })

  it('informa estado degradado cuando /health responde 503', async () => {
    // Arrange
    mockearFetch({
      ok: false,
      json: () => Promise.resolve({ ...SALUD_OK, status: 'degraded', database: 'error' }),
    })

    // Act
    render(<App />)

    // Assert
    await waitFor(() => {
      expect(screen.getByTestId('estado-conexion')).toHaveTextContent(
        'base de datos con problemas',
      )
    })
  })

  it('informa sin conexión cuando el fetch falla', async () => {
    // Arrange
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')))

    // Act
    render(<App />)

    // Assert
    await waitFor(() => {
      expect(screen.getByTestId('estado-conexion')).toHaveTextContent(
        'No se pudo contactar al backend',
      )
    })
  })
})
