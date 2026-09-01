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

async function abrirAlertas() {
  renderConProviders(<App />, { ruta: '/alerts' })
  await screen.findByRole('heading', { name: /^alertas$/i })
  return userEvent.setup()
}

// `getAllByRole(...)[0]` es `HTMLElement | undefined` con
// `noUncheckedIndexedAccess`. Cortar acá con un mensaje propio es mejor que
// castear: si la lista viniera vacía, el test dice por qué falló.
function primerBotonDeLeida() {
  const [boton] = screen.getAllByRole('button', { name: /marcar como leída/i })
  if (!boton) throw new Error('No hay ninguna alerta que se pueda marcar como leída.')
  return boton
}

describe('Bandeja de alertas', () => {
  beforeEach(conSesion)

  it('arranca mostrando las sin leer', async () => {
    // Arrange / Act
    await abrirAlertas()

    // Assert: la resuelta de julio no aparece con el filtro por defecto.
    expect(await screen.findByText(/te pasaste del presupuesto de alimentación/i)).toBeVisible()
    expect(screen.getByText(/vas camino a pasarte/i)).toBeVisible()
    expect(screen.queryByText(/transporte/i)).not.toBeInTheDocument()
  })

  it('muestra la recomendación que escribió el agente', async () => {
    // Arrange / Act
    await abrirAlertas()

    // Assert: es lo que distingue la alerta de una regla que solo informa.
    expect(await screen.findByText(/qué podés hacer/i)).toBeVisible()
    expect(screen.getByText(/cociná en casa/i)).toBeVisible()
  })

  it('una alerta sin recomendación se muestra igual', async () => {
    // Arrange / Act
    await abrirAlertas()

    // Assert: si el proveedor no respondió, la alerta vale lo mismo.
    const alerta = (await screen.findByText(/vas camino a pasarte/i)).closest('li')
    expect(within(alerta as HTMLElement).queryByText(/qué podés hacer/i)).not.toBeInTheDocument()
  })

  it('aclara que la proyección es un ritmo y no una predicción', async () => {
    // Arrange / Act
    await abrirAlertas()

    // Assert: presentar una regla de tres como predicción de IA es justo lo
    // que la especificación pide no hacer.
    expect(await screen.findByText(/186,0%/)).toBeVisible()
    expect(screen.getByText(/no una predicción/i)).toBeVisible()
  })

  it('deja ver las resueltas con el filtro', async () => {
    // Arrange
    const usuario = await abrirAlertas()

    // Act
    await usuario.click(screen.getByRole('radio', { name: /resueltas/i }))

    // Assert
    expect(await screen.findByText(/transporte/i)).toBeVisible()
  })

  it('el estado vacío no deja la pantalla en blanco', async () => {
    // Arrange
    store.alertas = []

    // Act
    await abrirAlertas()

    // Assert
    expect(await screen.findByText(/no tenés alertas sin leer/i)).toBeVisible()
  })

  it('ofrece reintentar si el listado falla', async () => {
    // Arrange
    server.use(
      http.get(`${BASE}/alerts`, () =>
        HttpResponse.json(
          { code: 'internal_error', message: 'Falló.', details: [] },
          { status: 500 },
        ),
      ),
    )

    // Act
    await abrirAlertas()

    // Assert
    expect(await screen.findByRole('button', { name: /reintentar/i })).toBeVisible()
  })
})

describe('Alertas: marcar como leída', () => {
  beforeEach(conSesion)

  it('la saca de las sin leer', async () => {
    // Arrange
    const usuario = await abrirAlertas()
    await screen.findByText(/te pasaste del presupuesto de alimentación/i)

    // Act
    await usuario.click(primerBotonDeLeida())

    // Assert
    await waitFor(() =>
      expect(
        screen.queryByText(/te pasaste del presupuesto de alimentación/i),
      ).not.toBeInTheDocument(),
    )
  })

  it('manda read en true', async () => {
    // Arrange
    const enviados: unknown[] = []
    server.use(
      http.patch(`${BASE}/alerts/:id`, async ({ request }) => {
        enviados.push(await request.json())
        return HttpResponse.json({ ...store.alertas[0], status: 'READ' })
      }),
    )
    const usuario = await abrirAlertas()
    await screen.findByText(/te pasaste del presupuesto de alimentación/i)

    // Act
    await usuario.click(primerBotonDeLeida())

    // Assert: el backend solo acepta `true`; no existe "desleer".
    await waitFor(() => expect(enviados).toEqual([{ read: true }]))
  })

  it('una alerta resuelta no ofrece marcarla como leída', async () => {
    // Arrange
    const usuario = await abrirAlertas()

    // Act
    await usuario.click(screen.getByRole('radio', { name: /resueltas/i }))
    await screen.findByText(/transporte/i)

    // Assert
    expect(
      screen.queryByRole('button', { name: /marcar como leída/i }),
    ).not.toBeInTheDocument()
  })
})

describe('Indicador de alertas en el menú', () => {
  beforeEach(conSesion)

  it('muestra cuántas hay sin leer', async () => {
    // Arrange / Act
    renderConProviders(<App />, { ruta: '/dashboard' })
    await screen.findByRole('heading', { name: /hola, damián/i })

    // Assert: es lo que hace que la alerta te encuentre a vos en vez de
    // esperar a que la vayas a buscar.
    const enlace = await screen.findByRole('link', { name: /alertas.*2 sin leer/i })
    expect(enlace).toBeVisible()
  })

  it('sin alertas sin leer no muestra nada', async () => {
    // Arrange
    store.alertas = []

    // Act
    renderConProviders(<App />, { ruta: '/dashboard' })
    await screen.findByRole('heading', { name: /hola, damián/i })

    // Assert: un contador en cero es ruido.
    expect(await screen.findByRole('link', { name: /^alertas$/i })).toBeVisible()
  })

  it('baja al marcar una como leída', async () => {
    // Arrange
    const usuario = await abrirAlertas()
    await screen.findByRole('link', { name: /alertas.*2 sin leer/i })

    // Act
    await usuario.click(primerBotonDeLeida())

    // Assert: sin invalidar el contador, el menú seguiría diciendo 2.
    expect(await screen.findByRole('link', { name: /alertas.*1 sin leer/i })).toBeVisible()
  })
})
