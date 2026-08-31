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

function foto(nombre = 'ticket.jpg', tipo = 'image/jpeg') {
  return new File(['bytes-de-la-foto'], nombre, { type: tipo })
}

function dialogo() {
  return within(screen.getByRole('dialog'))
}

async function abrirElEscaner() {
  renderConProviders(<App />, { ruta: '/transactions' })
  await screen.findByRole('heading', { name: /movimientos/i })
  await userEvent.setup().click(screen.getByRole('button', { name: /escanear ticket/i }))
  return userEvent.setup()
}

describe('Escáner de tickets', () => {
  beforeEach(conSesion)

  it('avisa que no se carga nada sin confirmar', async () => {
    // Arrange / Act
    await abrirElEscaner()

    // Assert: es la promesa que sostiene toda la feature.
    expect(dialogo().getByText(/no se carga nada sin que lo confirmes/i)).toBeVisible()
  })

  it('muestra lo que el lector entendió', async () => {
    // Arrange
    const usuario = await abrirElEscaner()

    // Act
    await usuario.upload(dialogo().getByLabelText(/foto del ticket/i), foto())

    // Assert
    expect(await dialogo().findByText(/12\.345,67/)).toBeVisible()
    expect(dialogo().getByText('03/08/2026')).toBeVisible()
    expect(dialogo().getByText('Supermercado Día')).toBeVisible()
    expect(dialogo().getByText('Alimentación')).toBeVisible()
  })

  it('marca los campos que el lector no leyó con seguridad', async () => {
    // Arrange
    const usuario = await abrirElEscaner()

    // Act
    await usuario.upload(dialogo().getByLabelText(/foto del ticket/i), foto())

    // Assert: esconder la duda es lo que hace que alguien confirme un dato
    // equivocado. La fecha vino con 0.4 de confianza.
    await dialogo().findByText('03/08/2026')
    expect(dialogo().getByText(/datos que no leí con seguridad/i)).toBeVisible()
    expect(dialogo().getByText('revisar')).toBeVisible()
  })

  it('avisa si ya hay un movimiento igual', async () => {
    // Arrange
    store.borradorDeTicket = { ...store.borradorDeTicket, possible_duplicates: [100] }
    const usuario = await abrirElEscaner()

    // Act
    await usuario.upload(dialogo().getByLabelText(/foto del ticket/i), foto())

    // Assert: avisa, no bloquea.
    expect(await dialogo().findByText(/puede ser que hayas escaneado este ticket antes/i)).toBeVisible()
  })
})

describe('Escáner: del borrador al alta', () => {
  beforeEach(conSesion)

  it('el borrador precarga el formulario de alta', async () => {
    // Arrange
    const usuario = await abrirElEscaner()
    await usuario.upload(dialogo().getByLabelText(/foto del ticket/i), foto())
    await dialogo().findByText(/12\.345,67/)

    // Act
    await usuario.click(dialogo().getByRole('button', { name: /usar estos datos/i }))

    // Assert: es el alta de siempre, con los campos ya cargados. La creación
    // sigue pasando por `POST /transactions`.
    expect(await screen.findByRole('heading', { name: /nuevo movimiento/i })).toBeVisible()
    expect(dialogo().getByLabelText(/^monto$/i)).toHaveValue(12345.67)
    expect(dialogo().getByLabelText(/^fecha$/i)).toHaveValue('2026-08-03')
    expect(dialogo().getByLabelText(/descripción/i)).toHaveValue('Supermercado Día')
  })

  it('el formulario señala los campos dudosos', async () => {
    // Arrange
    const usuario = await abrirElEscaner()
    await usuario.upload(dialogo().getByLabelText(/foto del ticket/i), foto())
    await dialogo().findByText(/12\.345,67/)

    // Act
    await usuario.click(dialogo().getByRole('button', { name: /usar estos datos/i }))

    // Assert: la duda viaja con el borrador hasta el formulario.
    await screen.findByRole('heading', { name: /nuevo movimiento/i })
    expect(dialogo().getByText(/el lector no estaba seguro/i)).toBeVisible()
  })

  it('escanear no crea ningún movimiento', async () => {
    // Arrange
    const creados: unknown[] = []
    server.use(
      http.post(`${BASE}/transactions`, async ({ request }) => {
        creados.push(await request.json())
        return HttpResponse.json({}, { status: 201 })
      }),
    )
    const usuario = await abrirElEscaner()

    // Act
    await usuario.upload(dialogo().getByLabelText(/foto del ticket/i), foto())
    await dialogo().findByText(/12\.345,67/)
    await usuario.click(dialogo().getByRole('button', { name: /usar estos datos/i }))

    // Assert: la regla de oro. Llegar al formulario no es haber creado nada.
    await screen.findByRole('heading', { name: /nuevo movimiento/i })
    expect(creados).toEqual([])
  })

  it('un alta manual después de escanear arranca en blanco', async () => {
    // Arrange
    const usuario = await abrirElEscaner()
    await usuario.upload(dialogo().getByLabelText(/foto del ticket/i), foto())
    await dialogo().findByText(/12\.345,67/)
    await usuario.click(dialogo().getByRole('button', { name: /usar estos datos/i }))
    await screen.findByRole('heading', { name: /nuevo movimiento/i })
    await usuario.click(dialogo().getByRole('button', { name: /cancelar/i }))

    // Act
    await usuario.click(screen.getByRole('button', { name: /nuevo movimiento/i }))

    // Assert: sin limpiar la precarga, el alta manual arrastraría los datos
    // del ticket anterior.
    expect(dialogo().getByLabelText(/^monto$/i)).toHaveValue(null)
  })
})

describe('Escáner: errores', () => {
  beforeEach(conSesion)

  it('explica que el lector no está disponible', async () => {
    // Arrange
    server.use(
      http.post(`${BASE}/receipts/scan`, () =>
        HttpResponse.json(
          {
            code: 'assistant_unavailable',
            message: 'No se pudo leer el ticket en este momento.',
            details: [],
          },
          { status: 503 },
        ),
      ),
    )
    const usuario = await abrirElEscaner()

    // Act
    await usuario.upload(dialogo().getByLabelText(/foto del ticket/i), foto())

    // Assert: ofrece la salida manual en vez de dejar a la persona trabada.
    expect(await dialogo().findByRole('alert')).toHaveTextContent(/cargar el gasto a mano/i)
  })

  it('muestra el mensaje del backend si el ticket es ilegible', async () => {
    // Arrange
    server.use(
      http.post(`${BASE}/receipts/scan`, () =>
        HttpResponse.json(
          {
            code: 'receipt_unreadable',
            message: 'No pude leer el ticket. Probá con una foto más nítida.',
            details: [],
          },
          { status: 422 },
        ),
      ),
    )
    const usuario = await abrirElEscaner()

    // Act
    await usuario.upload(dialogo().getByLabelText(/foto del ticket/i), foto())

    // Assert: el mapeo va por `code`; el texto del backend ya es accionable.
    expect(await dialogo().findByRole('alert')).toHaveTextContent(/foto más nítida/i)
  })

  it('avisa cuando se supera el cupo de lecturas', async () => {
    // Arrange
    server.use(
      http.post(`${BASE}/receipts/scan`, () =>
        HttpResponse.json(
          {
            code: 'rate_limit_exceeded',
            message: 'Llegaste al límite de 10 lecturas por hora.',
            details: [],
          },
          { status: 429 },
        ),
      ),
    )
    const usuario = await abrirElEscaner()

    // Act
    await usuario.upload(dialogo().getByLabelText(/foto del ticket/i), foto())

    // Assert
    expect(await dialogo().findByRole('alert')).toHaveTextContent(/límite de 10 lecturas/i)
  })

  it('deja reintentar con otra foto después de un error', async () => {
    // Arrange
    let primera = true
    server.use(
      http.post(`${BASE}/receipts/scan`, () => {
        if (primera) {
          primera = false
          return HttpResponse.json(
            { code: 'receipt_unreadable', message: 'No se lee.', details: [] },
            { status: 422 },
          )
        }
        return HttpResponse.json(store.borradorDeTicket)
      }),
    )
    const usuario = await abrirElEscaner()
    await usuario.upload(dialogo().getByLabelText(/foto del ticket/i), foto())
    await dialogo().findByRole('alert')

    // Act
    await usuario.upload(dialogo().getByLabelText(/foto del ticket/i), foto('otra.jpg'))

    // Assert
    await waitFor(() => expect(dialogo().getByText(/12\.345,67/)).toBeVisible())
  })
})
