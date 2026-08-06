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

function abrirRecurrentes() {
  return renderConProviders(<App />, { ruta: '/recurring' })
}

async function esperarLaPantalla() {
  return screen.findByRole('heading', { name: /movimientos recurrentes/i })
}

function dialogo() {
  return within(screen.getByRole('dialog'))
}

describe('RecurringPage', () => {
  beforeEach(conSesion)

  it('lista las reglas con su periodicidad en castellano', async () => {
    // Arrange / Act
    abrirRecurrentes()
    await esperarLaPantalla()

    // Assert
    expect(await screen.findByText('Alquiler')).toBeVisible()
    expect(screen.getByText(/todos los meses el día 10/i)).toBeVisible()
    expect(screen.getByText(/45\.000,00/)).toBeVisible()
  })

  it('muestra las próximas fechas que la regla va a generar', async () => {
    // Arrange / Act
    abrirRecurrentes()
    await esperarLaPantalla()

    // Assert: es el feedback de que la regla quedó bien configurada, y lo
    // calcula el backend para que no haya dos versiones del calendario.
    expect(await screen.findByText(/próximas:.*10\/09\/2026/i)).toBeVisible()
  })

  it('muestra un estado vacío cuando no hay reglas', async () => {
    // Arrange
    store.reglas = []

    // Act
    abrirRecurrentes()
    await esperarLaPantalla()

    // Assert
    expect(await screen.findByText(/todavía no tenés reglas/i)).toBeVisible()
  })

  it('ofrece reintentar si el listado falla', async () => {
    // Arrange
    server.use(
      http.get(`${BASE}/recurring-rules`, () =>
        HttpResponse.json({ code: 'internal_error', message: 'Falló.', details: [] }, { status: 500 }),
      ),
    )

    // Act
    abrirRecurrentes()
    await esperarLaPantalla()

    // Assert
    expect(await screen.findByRole('button', { name: /reintentar/i })).toBeVisible()
  })
})

describe('RecurringPage: pausar y reactivar', () => {
  beforeEach(conSesion)

  it('pausa una regla y avisa que no va a haber backfill', async () => {
    // Arrange
    abrirRecurrentes()
    await esperarLaPantalla()
    await screen.findByText('Alquiler')

    // Act
    await userEvent.setup().click(screen.getByRole('button', { name: /pausar/i }))

    // Assert: el aviso importa porque el comportamiento sorprende —reactivar
    // no genera lo del período pausado—.
    expect(await screen.findByRole('button', { name: /reactivar/i })).toBeVisible()
    expect(screen.getByText(/no se generan los movimientos del período pausado/i)).toBeVisible()
  })

  it('una regla pausada deja de mostrar próximas fechas', async () => {
    // Arrange
    abrirRecurrentes()
    await esperarLaPantalla()
    await screen.findByText('Alquiler')

    // Act
    await userEvent.setup().click(screen.getByRole('button', { name: /pausar/i }))

    // Assert
    await screen.findByRole('button', { name: /reactivar/i })
    expect(screen.queryByText(/próximas:/i)).not.toBeInTheDocument()
  })
})

describe('RecurringPage: alta', () => {
  beforeEach(conSesion)

  it('crea una regla mensual', async () => {
    // Arrange
    const enviados: Record<string, unknown>[] = []
    server.use(
      http.post(`${BASE}/recurring-rules`, async ({ request }) => {
        const cuerpo = (await request.json()) as Record<string, unknown>
        enviados.push(cuerpo)
        return HttpResponse.json({ ...store.reglas[0], id: 999 }, { status: 201 })
      }),
    )
    abrirRecurrentes()
    await esperarLaPantalla()
    const usuario = userEvent.setup()

    // Act
    await usuario.click(screen.getByRole('button', { name: /nueva regla/i }))
    await usuario.selectOptions(dialogo().getByLabelText(/^categoría$/i), '20')
    await usuario.type(dialogo().getByLabelText(/^monto$/i), '45000')
    await usuario.type(dialogo().getByLabelText(/descripción/i), 'Internet')
    await usuario.click(dialogo().getByRole('button', { name: /guardar/i }))

    // Assert
    await waitFor(() => expect(enviados).toHaveLength(1))
    expect(enviados[0]).toMatchObject({
      category_id: 20,
      type: 'EXPENSE',
      frequency: 'MONTHLY',
      day_of_month: 1,
      description: 'Internet',
    })
  })

  it('manda day_of_week y no day_of_month cuando la regla es semanal', async () => {
    // Arrange
    const enviados: Record<string, unknown>[] = []
    server.use(
      http.post(`${BASE}/recurring-rules`, async ({ request }) => {
        enviados.push((await request.json()) as Record<string, unknown>)
        return HttpResponse.json({ ...store.reglas[0], id: 999 }, { status: 201 })
      }),
    )
    abrirRecurrentes()
    await esperarLaPantalla()
    const usuario = userEvent.setup()

    // Act
    await usuario.click(screen.getByRole('button', { name: /nueva regla/i }))
    await usuario.selectOptions(dialogo().getByLabelText(/^categoría$/i), '20')
    await usuario.type(dialogo().getByLabelText(/^monto$/i), '3000')
    await usuario.selectOptions(dialogo().getByLabelText(/frecuencia/i), 'WEEKLY')
    await usuario.selectOptions(dialogo().getByLabelText(/día de la semana/i), '2')
    await usuario.click(dialogo().getByRole('button', { name: /guardar/i }))

    // Assert: el backend rechaza con 422 los parámetros que la frecuencia no
    // usa, así que mandar los dos rompería el alta.
    await waitFor(() => expect(enviados).toHaveLength(1))
    expect(enviados[0]).toMatchObject({ frequency: 'WEEKLY', day_of_week: 2, day_of_month: null })
  })

  it('explica el ajuste del día 31 antes de guardar', async () => {
    // Arrange
    abrirRecurrentes()
    await esperarLaPantalla()

    // Act
    await userEvent.setup().click(screen.getByRole('button', { name: /nueva regla/i }))

    // Assert
    expect(dialogo().getByText(/el 31 en febrero cae el 28/i)).toBeVisible()
  })

  it('no envía si falta la categoría', async () => {
    // Arrange
    abrirRecurrentes()
    await esperarLaPantalla()
    const usuario = userEvent.setup()

    // Act
    await usuario.click(screen.getByRole('button', { name: /nueva regla/i }))
    await usuario.type(dialogo().getByLabelText(/^monto$/i), '1000')
    await usuario.click(dialogo().getByRole('button', { name: /guardar/i }))

    // Assert: se busca por rol y no por texto, porque el placeholder del
    // select dice exactamente lo mismo.
    expect(await dialogo().findByRole('alert')).toHaveTextContent(/elegí una categoría/i)
  })

  it('muestra el error del backend si la categoría no corresponde al tipo', async () => {
    // Arrange
    server.use(
      http.post(`${BASE}/recurring-rules`, () =>
        HttpResponse.json(
          { code: 'invalid_reference', message: 'Es de ingreso.', details: [] },
          { status: 422 },
        ),
      ),
    )
    abrirRecurrentes()
    await esperarLaPantalla()
    const usuario = userEvent.setup()

    // Act
    await usuario.click(screen.getByRole('button', { name: /nueva regla/i }))
    await usuario.selectOptions(dialogo().getByLabelText(/^categoría$/i), '20')
    await usuario.type(dialogo().getByLabelText(/^monto$/i), '1000')
    await usuario.click(dialogo().getByRole('button', { name: /guardar/i }))

    // Assert: el mapeo va por `code`, no por el texto del mensaje.
    expect(await dialogo().findByText(/mismo tipo que la regla/i)).toBeVisible()
  })
})

describe('RecurringPage: historial y borrado', () => {
  beforeEach(conSesion)

  it('distingue una ocurrencia generada de una salteada', async () => {
    // Arrange
    abrirRecurrentes()
    await esperarLaPantalla()
    await screen.findByText('Alquiler')

    // Act
    await userEvent.setup().click(screen.getByRole('button', { name: /historial/i }))

    // Assert: "salteada" explica por qué el job no la va a volver a crear.
    expect(await dialogo().findByText('10/08/2026')).toBeVisible()
    expect(dialogo().getByText('generada')).toBeVisible()
    expect(dialogo().getByText('salteada')).toBeVisible()
  })

  it('avisa que borrar la regla no borra los movimientos ya generados', async () => {
    // Arrange
    abrirRecurrentes()
    await esperarLaPantalla()
    await screen.findByText('Alquiler')

    // Act
    await userEvent.setup().click(screen.getByRole('button', { name: /borrar/i }))

    // Assert
    expect(await dialogo().findByText(/no se borran/i)).toBeVisible()
  })

  it('borra la regla al confirmar', async () => {
    // Arrange
    abrirRecurrentes()
    await esperarLaPantalla()
    await screen.findByText('Alquiler')
    const usuario = userEvent.setup()

    // Act
    await usuario.click(screen.getByRole('button', { name: /borrar/i }))
    await usuario.click(dialogo().getByRole('button', { name: /^borrar$/i }))

    // Assert
    expect(await screen.findByText(/todavía no tenés reglas/i)).toBeVisible()
  })
})

describe('DashboardPage: próximos vencimientos', () => {
  beforeEach(conSesion)

  it('los muestra aclarando que son una proyección', async () => {
    // Arrange / Act
    renderConProviders(<App />, { ruta: '/dashboard' })
    await screen.findByRole('heading', { name: /hola, damián/i })

    // Assert: sin la aclaración, la diferencia con el balance parece un error
    // de cuentas.
    const seccion = (await screen.findByRole('heading', { name: /próximos vencimientos/i }))
      .closest('div') as HTMLElement
    expect(within(seccion).getByText(/todavía no forman parte del balance/i)).toBeVisible()
    expect(within(seccion).getByText(/alquiler/i)).toBeVisible()
  })

  it('no muestra la sección si no hay vencimientos', async () => {
    // Arrange
    store.vencimientos = { ...store.vencimientos, entries: [] }

    // Act
    renderConProviders(<App />, { ruta: '/dashboard' })
    await screen.findByRole('heading', { name: /hola, damián/i })

    // Assert
    await waitFor(() =>
      expect(
        screen.queryByRole('heading', { name: /próximos vencimientos/i }),
      ).not.toBeInTheDocument(),
    )
  })
})
