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

async function abrirMetas() {
  renderConProviders(<App />, { ruta: '/savings-goals' })
  await screen.findByRole('heading', { name: /metas de ahorro/i })
  return userEvent.setup()
}

function tarjetaDe(nombre: string) {
  const titulo = screen.getByRole('heading', { name: nombre })
  return titulo.closest('li') as HTMLElement
}

describe('Metas de ahorro', () => {
  beforeEach(conSesion)

  it('muestra el avance contra el objetivo', async () => {
    // Arrange / Act
    await abrirMetas()

    // Assert
    const viaje = await screen.findByRole('heading', { name: 'Viaje' })
    const tarjeta = within(viaje.closest('li') as HTMLElement)
    expect(tarjeta.getByText(/\$ 500\.000,00 de \$ 2\.000\.000,00/)).toBeVisible()
    expect(tarjeta.getByText(/faltan \$ 1\.500\.000,00/i)).toBeVisible()
  })

  it('dice desde cuándo cuenta el avance', async () => {
    // Arrange / Act
    await abrirMetas()

    // Assert: sin esto, el número no se puede interpretar — no hay una cuenta
    // con plata adentro, es el balance desde una fecha.
    await screen.findByRole('heading', { name: 'Viaje' })
    expect(within(tarjetaDe('Viaje')).getByText(/cuenta tu balance desde el/i)).toBeVisible()
  })

  it('expone el avance como progressbar', async () => {
    // Arrange / Act
    await abrirMetas()

    // Assert
    const barra = await screen.findByRole('progressbar', { name: /viaje/i })
    expect(barra).toHaveAttribute('aria-valuenow', '25')
  })

  it('el estado vacío no deja la pantalla en blanco', async () => {
    // Arrange
    store.avanceDeMetas = []

    // Act
    await abrirMetas()

    // Assert
    expect(await screen.findByText(/no tenés metas de ahorro/i)).toBeVisible()
  })

  it('ofrece reintentar si el avance falla', async () => {
    // Arrange
    server.use(
      http.get(`${BASE}/savings-goals/progress`, () =>
        HttpResponse.json(
          { code: 'internal_error', message: 'Falló.', details: [] },
          { status: 500 },
        ),
      ),
    )

    // Act
    await abrirMetas()

    // Assert
    expect(await screen.findByRole('button', { name: /reintentar/i })).toBeVisible()
  })
})

describe('Metas: la proyección se presenta como estimación', () => {
  beforeEach(conSesion)

  it('nunca muestra una fecha sin decir sobre cuántos meses se calculó', async () => {
    // Arrange / Act
    await abrirMetas()
    await screen.findByRole('heading', { name: 'Viaje' })

    // Assert: es lo que separa una regla de tres de una predicción de IA.
    const tarjeta = within(tarjetaDe('Viaje'))
    expect(tarjeta.getByText(/te faltan 6 meses/i)).toBeVisible()
    expect(tarjeta.getByText(/promedio de 5 meses, no una predicción/i)).toBeVisible()
  })

  it('sin historial suficiente lo dice en vez de estimar', async () => {
    // Arrange / Act
    await abrirMetas()
    await screen.findByRole('heading', { name: 'Colchón' })

    // Assert
    const tarjeta = within(tarjetaDe('Colchón'))
    expect(tarjeta.getByText(/al menos dos meses cerrados/i)).toBeVisible()
    expect(tarjeta.queryByText(/te faltan/i)).not.toBeInTheDocument()
  })

  it('sin historial no arriesga un estado', async () => {
    // Arrange / Act
    await abrirMetas()
    await screen.findByRole('heading', { name: 'Colchón' })

    // Assert: "no sabemos" no es lo mismo que "vas tarde".
    const tarjeta = within(tarjetaDe('Colchón'))
    expect(tarjeta.getByText(/sin datos/i)).toBeVisible()
    expect(tarjeta.queryByText(/vas tarde/i)).not.toBeInTheDocument()
  })

  it('avisa cuando a ese ritmo no se llega nunca', async () => {
    // Arrange
    const [primera] = store.avanceDeMetas
    if (primera?.projection) {
      primera.projection.months_to_target = null
      primera.projection.projected_date = null
    }

    // Act
    await abrirMetas()
    await screen.findByRole('heading', { name: 'Viaje' })

    // Assert
    expect(within(tarjetaDe('Viaje')).getByText(/no llegás a juntarla/i)).toBeVisible()
  })

  it('una meta alcanzada no proyecta nada', async () => {
    // Arrange
    const [primera] = store.avanceDeMetas
    if (primera) {
      primera.status = 'ACHIEVED'
      primera.saved = '2000000.00'
      primera.remaining = '0.00'
      primera.percentage = '100.00'
      primera.projection = null
    }

    // Act
    await abrirMetas()
    await screen.findByRole('heading', { name: 'Viaje' })

    // Assert: ya está; no queda nada que estimar.
    const tarjeta = within(tarjetaDe('Viaje'))
    expect(tarjeta.getByText(/alcanzada/i)).toBeVisible()
    expect(tarjeta.getByText(/ya la juntaste/i)).toBeVisible()
    expect(tarjeta.queryByText(/al menos dos meses cerrados/i)).not.toBeInTheDocument()
  })
})

describe('Metas: ABM', () => {
  beforeEach(conSesion)

  it('crea una meta desde el formulario', async () => {
    // Arrange
    const usuario = await abrirMetas()
    await usuario.click(screen.getByRole('button', { name: /nueva meta/i }))

    // Act
    await usuario.type(screen.getByLabelText(/nombre/i), 'Auto')
    await usuario.type(screen.getByLabelText(/cuánto querés juntar/i), '5000000')
    await usuario.click(screen.getByRole('button', { name: /crear meta/i }))

    // Assert
    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
    )
    expect(store.metas.some((meta) => meta.name === 'Auto')).toBe(true)
  })

  it('avisa si el nombre ya existe', async () => {
    // Arrange
    const usuario = await abrirMetas()
    await usuario.click(screen.getByRole('button', { name: /nueva meta/i }))

    // Act
    await usuario.type(screen.getByLabelText(/nombre/i), 'Viaje')
    await usuario.type(screen.getByLabelText(/cuánto querés juntar/i), '100000')
    await usuario.click(screen.getByRole('button', { name: /crear meta/i }))

    // Assert
    expect(await screen.findByText(/ya tenés una meta con ese nombre/i)).toBeVisible()
  })

  it('vaciar la fecha objetivo la saca', async () => {
    // Arrange
    const enviados: unknown[] = []
    server.use(
      http.patch(`${BASE}/savings-goals/:id`, async ({ request }) => {
        enviados.push(await request.json())
        return HttpResponse.json({ ...store.metas[0], target_date: null })
      }),
    )
    const usuario = await abrirMetas()
    await screen.findByRole('heading', { name: 'Viaje' })

    // Act
    await usuario.click(within(tarjetaDe('Viaje')).getByRole('button', { name: /editar/i }))
    await usuario.clear(screen.getByLabelText(/para cuándo/i))
    await usuario.click(screen.getByRole('button', { name: /^guardar$/i }))

    // Assert: `target_date: null` significaría "no lo toques", así que sin el
    // flag la fecha se quedaría puesta para siempre.
    await waitFor(() =>
      expect(enviados[0]).toMatchObject({ clear_target_date: true }),
    )
  })

  it('borra una meta después de confirmar', async () => {
    // Arrange
    const usuario = await abrirMetas()
    await screen.findByRole('heading', { name: 'Viaje' })

    // Act
    await usuario.click(within(tarjetaDe('Viaje')).getByRole('button', { name: /borrar/i }))
    const dialogo = await screen.findByRole('dialog')
    await usuario.click(within(dialogo).getByRole('button', { name: /borrar/i }))

    // Assert
    await waitFor(() => expect(store.metas.some((meta) => meta.id === 900)).toBe(false))
  })

  it('aclara que borrar no toca los movimientos', async () => {
    // Arrange
    const usuario = await abrirMetas()
    await screen.findByRole('heading', { name: 'Viaje' })

    // Act
    await usuario.click(within(tarjetaDe('Viaje')).getByRole('button', { name: /borrar/i }))

    // Assert: la meta es una lectura sobre el balance, no una cuenta.
    expect(await screen.findByText(/los movimientos no se tocan/i)).toBeVisible()
  })
})

describe('DashboardPage: resumen de metas', () => {
  beforeEach(conSesion)

  async function abrirDashboard() {
    renderConProviders(<App />, { ruta: '/dashboard' })
    await screen.findByRole('heading', { name: /hola, damián/i })
  }

  function seccionDeMetas() {
    return screen
      .getByRole('heading', { name: /metas de ahorro/i })
      .closest('div') as HTMLElement
  }

  it('muestra cuánto llevás juntado de cada meta', async () => {
    // Arrange / Act
    await abrirDashboard()
    await screen.findByRole('heading', { name: /metas de ahorro/i })

    // Assert
    const seccion = within(seccionDeMetas())
    expect(seccion.getByText('Viaje')).toBeVisible()
    expect(seccion.getByText(/25,0% · faltan \$ 1\.500\.000,00/)).toBeVisible()
  })

  it('no trae la fecha estimada al dashboard', async () => {
    // Arrange / Act
    await abrirDashboard()
    await screen.findByRole('heading', { name: /metas de ahorro/i })

    // Assert: la estimación vive donde entra su aclaración. Traer el "te
    // faltan 6 meses" sin el "promedio de N meses" al lado convertiría una
    // regla de tres en una predicción.
    const seccion = within(seccionDeMetas())
    expect(seccion.queryByText(/te faltan 6 meses/i)).not.toBeInTheDocument()
    expect(seccion.queryByText(/no una predicción/i)).not.toBeInTheDocument()
  })

  it('sin estado no inventa una etiqueta', async () => {
    // Arrange / Act
    await abrirDashboard()
    await screen.findByRole('heading', { name: /metas de ahorro/i })

    // Assert: "Colchón" no tiene historial suficiente, así que no se le puede
    // poner ni "En camino" ni "Vas tarde".
    const fila = within(seccionDeMetas()).getByText('Colchón').closest('li') as HTMLElement
    expect(within(fila).queryByText(/en camino|vas tarde|alcanzada/i)).not.toBeInTheDocument()
    // La que sí tiene estado lo muestra.
    const otra = within(seccionDeMetas()).getByText('Viaje').closest('li') as HTMLElement
    expect(within(otra).getByText(/vas tarde/i)).toBeVisible()
  })

  it('no muestra la sección si no hay metas', async () => {
    // Arrange
    store.avanceDeMetas = []

    // Act
    await abrirDashboard()

    // Assert: un dashboard lleno de secciones vacías esconde las que sí
    // tienen algo.
    await waitFor(() =>
      expect(
        screen.queryByRole('heading', { name: /metas de ahorro/i }),
      ).not.toBeInTheDocument(),
    )
  })
})
