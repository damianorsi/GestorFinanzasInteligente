import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { beforeEach, describe, expect, it } from 'vitest'

import App from '@/App'
import { BASE, TOKENS, store } from '@/test/handlers'
import { renderConProviders } from '@/test/render'
import { server } from '@/test/server'

function conSesion() {
  localStorage.setItem('gfp.refresh_token', TOKENS.refresh_token)
}

function abrirChat() {
  return renderConProviders(<App />, { ruta: '/chat' })
}

async function esperarLaPantalla() {
  return screen.findByRole('heading', { name: /asistente/i })
}

async function preguntar(texto: string) {
  const usuario = userEvent.setup()
  await usuario.type(screen.getByLabelText(/tu consulta/i), texto)
  await usuario.click(screen.getByRole('button', { name: /enviar/i }))
}

describe('ChatPage', () => {
  beforeEach(() => {
    conSesion()
    sessionStorage.clear()
  })

  it('muestra sugerencias mientras no hay conversación', async () => {
    // Arrange / Act
    abrirChat()
    await esperarLaPantalla()

    // Assert: una pantalla en blanco no le dice a nadie qué puede preguntar.
    expect(await screen.findByRole('button', { name: '¿Cuánto gasté este mes?' })).toBeVisible()
  })

  it('manda la consulta y muestra la respuesta del asistente', async () => {
    // Arrange
    abrirChat()
    await esperarLaPantalla()

    // Act
    await preguntar('¿cuánto gasté?')

    // Assert
    const conversacion = screen.getByRole('log')
    expect(await within(conversacion).findByText(/¿cuánto gasté\?/)).toBeVisible()
    expect(await within(conversacion).findByText(/450\.000,50 ARS/)).toBeVisible()
  })

  it('una sugerencia manda la consulta sin tener que escribirla', async () => {
    // Arrange
    abrirChat()
    await esperarLaPantalla()

    // Act
    await userEvent
      .setup()
      .click(await screen.findByRole('button', { name: '¿En qué categoría gasto más?' }))

    // Assert
    expect(
      await within(screen.getByRole('log')).findByText(/¿En qué categoría gasto más\?/),
    ).toBeVisible()
  })

  it('avisa que el asistente está escribiendo mientras espera', async () => {
    // Arrange: la respuesta se demora para poder observar el estado intermedio.
    server.use(
      http.post(`${BASE}/chat`, async () => {
        await new Promise((resolver) => setTimeout(resolver, 80))
        return HttpResponse.json({ conversation_id: 'c1', content: 'Listo.', degraded: false })
      }),
    )
    abrirChat()
    await esperarLaPantalla()

    // Act
    await preguntar('hola')

    // Assert
    expect(await screen.findByText(/está escribiendo/i)).toBeInTheDocument()
    await screen.findByText('Listo.')
  })

  it('no deja mandar dos veces mientras hay una consulta en curso', async () => {
    // Arrange
    server.use(
      http.post(`${BASE}/chat`, async () => {
        await new Promise((resolver) => setTimeout(resolver, 80))
        return HttpResponse.json({ conversation_id: 'c1', content: 'Listo.', degraded: false })
      }),
    )
    abrirChat()
    await esperarLaPantalla()

    // Act
    await preguntar('hola')

    // Assert: sin esto, un doble clic gasta dos consultas del cupo por hora.
    expect(screen.getByRole('button', { name: /consultando/i })).toBeDisabled()
    await screen.findByText('Listo.')
  })

  it('el botón de enviar arranca deshabilitado', async () => {
    // Arrange / Act
    abrirChat()
    await esperarLaPantalla()

    // Assert
    expect(screen.getByRole('button', { name: /enviar/i })).toBeDisabled()
  })

  it('Enter manda y Shift+Enter hace salto de línea', async () => {
    // Arrange
    const enviados: string[] = []
    server.use(
      http.post(`${BASE}/chat`, async ({ request }) => {
        const cuerpo = (await request.json()) as { message: string }
        enviados.push(cuerpo.message)
        return HttpResponse.json({ conversation_id: 'c1', content: 'Listo.', degraded: false })
      }),
    )
    abrirChat()
    await esperarLaPantalla()

    // Act
    await userEvent
      .setup()
      .type(screen.getByLabelText(/tu consulta/i), 'primera{Shift>}{Enter}{/Shift}segunda{Enter}')

    // Assert: el Shift+Enter agrega una línea y no dispara un envío suelto.
    await screen.findByText('Listo.')
    expect(enviados).toEqual(['primera\nsegunda'])
  })

  it('recupera la conversación guardada al volver a la pantalla', async () => {
    // Arrange: una charla previa, como después de recargar la página.
    sessionStorage.setItem('gfp.conversation_id', 'conv-previa')
    store.conversaciones['conv-previa'] = [
      { role: 'USER', content: '¿cuánto ahorré?', created_at: '2026-08-05T14:30:00' },
      { role: 'ASSISTANT', content: 'Ahorraste 399.999,50 ARS.', created_at: '2026-08-05T14:30:02' },
    ]

    // Act
    abrirChat()
    await esperarLaPantalla()

    // Assert
    const conversacion = await screen.findByRole('log')
    expect(await within(conversacion).findByText(/¿cuánto ahorré\?/)).toBeVisible()
    expect(within(conversacion).getByText(/399\.999,50 ARS/)).toBeVisible()
  })

  it('«nueva conversación» limpia la pantalla y el identificador guardado', async () => {
    // Arrange
    abrirChat()
    await esperarLaPantalla()
    await preguntar('hola')
    await within(screen.getByRole('log')).findByText(/450\.000,50 ARS/)

    // Act
    await userEvent.setup().click(screen.getByRole('button', { name: /nueva conversación/i }))

    // Assert
    expect(within(screen.getByRole('log')).queryByText(/450\.000,50 ARS/)).not.toBeInTheDocument()
    expect(sessionStorage.getItem('gfp.conversation_id')).toBeNull()
  })

  it('continúa la misma conversación en el segundo mensaje', async () => {
    // Arrange
    const conversacionesPedidas: (string | null)[] = []
    server.use(
      http.post(`${BASE}/chat`, async ({ request }) => {
        const cuerpo = (await request.json()) as { message: string; conversation_id?: string }
        conversacionesPedidas.push(cuerpo.conversation_id ?? null)
        return HttpResponse.json({
          conversation_id: 'conv-fija',
          content: `respuesta a ${cuerpo.message}`,
          degraded: false,
        })
      }),
    )
    abrirChat()
    await esperarLaPantalla()
    await preguntar('primera')
    await screen.findByText('respuesta a primera')

    // Act
    await preguntar('segunda')
    await screen.findByText('respuesta a segunda')

    // Assert: sin el identificador, el asistente perdería el contexto de la
    // pregunta anterior en cada mensaje.
    expect(conversacionesPedidas).toEqual([null, 'conv-fija'])
  })
})

describe('ChatPage: errores', () => {
  beforeEach(() => {
    conSesion()
    sessionStorage.clear()
  })

  it('avisa cuando se supera el cupo por hora', async () => {
    // Arrange
    server.use(
      http.post(`${BASE}/chat`, () =>
        HttpResponse.json(
          {
            code: 'rate_limit_exceeded',
            message: 'Llegaste al límite de 20 consultas por hora. Probá de nuevo más tarde.',
            details: [],
          },
          { status: 429 },
        ),
      ),
    )
    abrirChat()
    await esperarLaPantalla()

    // Act
    await preguntar('hola')

    // Assert: el mapeo va por `code`, y el texto del backend ya es accionable.
    expect(await screen.findByRole('alert')).toHaveTextContent(/límite de 20 consultas por hora/i)
  })

  it('devuelve la consulta al campo cuando el envío falla', async () => {
    // Arrange
    server.use(
      http.post(`${BASE}/chat`, () =>
        HttpResponse.json(
          { code: 'rate_limit_exceeded', message: 'Sin cupo.', details: [] },
          { status: 429 },
        ),
      ),
    )
    abrirChat()
    await esperarLaPantalla()

    // Act
    await preguntar('¿cuánto gasté?')

    // Assert: el 429 no llega a persistirse en el backend, así que dejar la
    // burbuja en pantalla mostraría un mensaje que no existe.
    await screen.findByRole('alert')
    expect(screen.getByLabelText(/tu consulta/i)).toHaveValue('¿cuánto gasté?')
    expect(within(screen.getByRole('log')).queryByText('¿cuánto gasté?')).not.toBeInTheDocument()
  })

  it('ofrece reintentar cuando la respuesta viene degradada', async () => {
    // Arrange
    server.use(
      http.post(`${BASE}/chat`, () =>
        HttpResponse.json({
          conversation_id: 'c1',
          content: 'No pude consultar tus datos en este momento.',
          degraded: true,
        }),
      ),
    )
    abrirChat()
    await esperarLaPantalla()

    // Act
    await preguntar('hola')

    // Assert: `degraded` distingue una caída de OpenAI de un "no sé" real.
    expect(await screen.findByText(/no pude consultar tus datos/i)).toBeVisible()
    expect(screen.getByRole('button', { name: /reintentar la última pregunta/i })).toBeVisible()
  })

  it('no ofrece reintentar cuando la respuesta es normal', async () => {
    // Arrange
    abrirChat()
    await esperarLaPantalla()

    // Act
    await preguntar('hola')
    await within(screen.getByRole('log')).findByText(/450\.000,50 ARS/)

    // Assert
    expect(
      screen.queryByRole('button', { name: /reintentar la última pregunta/i }),
    ).not.toBeInTheDocument()
  })

  it('avisa si no se puede cargar la conversación anterior', async () => {
    // Arrange
    sessionStorage.setItem('gfp.conversation_id', 'conv-rota')
    server.use(
      http.get(`${BASE}/chat/history`, () =>
        HttpResponse.json({ code: 'internal_error', message: 'Falló.', details: [] }, { status: 500 }),
      ),
    )

    // Act
    abrirChat()
    await esperarLaPantalla()

    // Assert
    expect(await screen.findByRole('alert')).toHaveTextContent(/no se pudo cargar la conversación/i)
  })

  it('un fallo de red no rompe la pantalla', async () => {
    // Arrange
    server.use(http.post(`${BASE}/chat`, () => HttpResponse.error()))
    abrirChat()
    await esperarLaPantalla()

    // Act
    await preguntar('hola')

    // Assert
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/no se pudo conectar/i),
    )
    expect(screen.getByLabelText(/tu consulta/i)).toHaveValue('hola')
  })
})
