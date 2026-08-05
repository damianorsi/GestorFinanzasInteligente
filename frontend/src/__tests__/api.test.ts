import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'

import { ApiError, NetworkError, request } from '@/services/api'
import { getAccessToken, saveSession } from '@/services/session'
import { BASE, TOKENS, contadores } from '@/test/handlers'
import { server } from '@/test/server'

describe('cliente HTTP', () => {
  it('adjunta el token de acceso', async () => {
    // Arrange
    saveSession(TOKENS)
    let autorizacion: string | null = null
    server.use(
      http.get(`${BASE}/ping`, ({ request: peticion }) => {
        autorizacion = peticion.headers.get('Authorization')
        return HttpResponse.json({ ok: true })
      }),
    )

    // Act
    await request('/ping')

    // Assert
    expect(autorizacion).toBe(`Bearer ${TOKENS.access_token}`)
  })

  it('no adjunta token en los endpoints anónimos', async () => {
    // Arrange
    saveSession(TOKENS)
    let autorizacion: string | null = 'sin-leer'
    server.use(
      http.get(`${BASE}/publico`, ({ request: peticion }) => {
        autorizacion = peticion.headers.get('Authorization')
        return HttpResponse.json({ ok: true })
      }),
    )

    // Act
    await request('/publico', { anonymous: true })

    // Assert
    expect(autorizacion).toBeNull()
  })

  it('renueva la sesión y reintenta cuando recibe 401', async () => {
    // Arrange
    saveSession(TOKENS)
    let intentos = 0
    server.use(
      http.get(`${BASE}/protegido`, () => {
        intentos += 1
        if (intentos === 1) {
          return HttpResponse.json(
            { code: 'invalid_token', message: 'Vencido.', details: [] },
            { status: 401 },
          )
        }
        return HttpResponse.json({ ok: true })
      }),
    )

    // Act
    const resultado = await request<{ ok: boolean }>('/protegido')

    // Assert
    expect(resultado.ok).toBe(true)
    expect(intentos).toBe(2)
    expect(getAccessToken()).toBe('access-2')
  })

  it('no reintenta en bucle si sigue dando 401 tras renovar', async () => {
    // Arrange
    saveSession(TOKENS)
    let intentos = 0
    server.use(
      http.get(`${BASE}/prohibido`, () => {
        intentos += 1
        return HttpResponse.json(
          { code: 'invalid_token', message: 'No autorizado.', details: [] },
          { status: 401 },
        )
      }),
    )

    // Act / Assert
    await expect(request('/prohibido')).rejects.toBeInstanceOf(ApiError)
    expect(intentos).toBe(2)
  })

  it('renueva una sola vez aunque varios requests fallen a la vez', async () => {
    /*
     * El refresh token rota: si tres requests reciben 401 y cada uno dispara su
     * propia renovación, la primera invalida el token y las otras dos cierran
     * la sesión de alguien que estaba usando la aplicación normalmente.
     */
    // Arrange
    saveSession(TOKENS)
    const vistos = new Set<string>()
    server.use(
      http.get(`${BASE}/recurso/:id`, ({ params }) => {
        const clave = String(params.id)
        if (!vistos.has(clave)) {
          vistos.add(clave)
          return HttpResponse.json(
            { code: 'invalid_token', message: 'Vencido.', details: [] },
            { status: 401 },
          )
        }
        return HttpResponse.json({ ok: true })
      }),
    )

    // Act
    await Promise.all([
      request('/recurso/1'),
      request('/recurso/2'),
      request('/recurso/3'),
    ])

    // Assert
    expect(contadores.refresh).toBe(1)
  })

  it('expone el code del error para poder mapearlo', async () => {
    // Arrange
    server.use(
      http.get(`${BASE}/conflicto`, () =>
        HttpResponse.json(
          {
            code: 'duplicate_resource',
            message: 'Ya existe.',
            details: [{ field: 'name', reason: 'repetido' }],
          },
          { status: 409 },
        ),
      ),
    )

    // Act
    const error = await request('/conflicto').catch((excepcion: unknown) => excepcion)

    // Assert
    expect(error).toBeInstanceOf(ApiError)
    const apiError = error as ApiError
    expect(apiError.code).toBe('duplicate_resource')
    expect(apiError.status).toBe(409)
    expect(apiError.reasonFor('name')).toBe('repetido')
  })

  it('distingue una caída de red de un error de la API', async () => {
    // Arrange
    server.use(http.get(`${BASE}/caido`, () => HttpResponse.error()))

    // Act / Assert
    await expect(request('/caido')).rejects.toBeInstanceOf(NetworkError)
  })

  it('omite los parámetros vacíos de la query string', async () => {
    // Arrange
    let url = ''
    server.use(
      http.get(`${BASE}/buscar`, ({ request: peticion }) => {
        url = peticion.url
        return HttpResponse.json([])
      }),
    )

    // Act
    await request('/buscar', {
      params: { q: 'pan', categoria: undefined, tipo: null, vacio: '' },
    })

    // Assert
    expect(url).toContain('q=pan')
    expect(url).not.toContain('categoria')
    expect(url).not.toContain('tipo')
    expect(url).not.toContain('vacio')
  })

  it('devuelve undefined en un 204 sin intentar parsear el cuerpo', async () => {
    // Arrange
    server.use(http.delete(`${BASE}/algo`, () => new HttpResponse(null, { status: 204 })))

    // Act / Assert
    await expect(request('/algo', { method: 'DELETE' })).resolves.toBeUndefined()
  })
})
