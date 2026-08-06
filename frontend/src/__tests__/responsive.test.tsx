import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import App from '@/App'
import { TOKENS } from '@/test/handlers'
import { renderConProviders } from '@/test/render'

/*
 * Lo que se puede testear del responsive en jsdom es el comportamiento y la
 * estructura: que el menú se abra y se cierre, que el foco vuelva donde
 * corresponde, que la sesión esté dentro del panel y que el atajo al asistente
 * lleve al chat. El layout en sí lo decide el CSS, y jsdom no calcula estilos
 * ni resuelve media queries: eso se verifica en un navegador real.
 */

function conSesion() {
  localStorage.setItem('gfp.refresh_token', TOKENS.refresh_token)
}

function menu() {
  return screen.getByRole('navigation', { name: /secciones/i })
}

function botonDelMenu() {
  return screen.getByRole('button', { name: /abrir menú|cerrar menú/i })
}

describe('Menú hamburguesa', () => {
  beforeEach(conSesion)

  it('arranca cerrado', async () => {
    // Arrange / Act
    renderConProviders(<App />, { ruta: '/dashboard' })
    await screen.findByRole('heading', { name: /hola, damián/i })

    // Assert
    expect(botonDelMenu()).toHaveAttribute('aria-expanded', 'false')
    expect(botonDelMenu()).toHaveAccessibleName(/abrir menú/i)
  })

  it('el botón controla el panel de navegación', async () => {
    // Arrange
    renderConProviders(<App />, { ruta: '/dashboard' })
    await screen.findByRole('heading', { name: /hola, damián/i })

    // Assert: sin `aria-controls`, un lector de pantalla no puede relacionar
    // el botón con lo que abre.
    expect(botonDelMenu()).toHaveAttribute('aria-controls', menu().id)
  })

  it('se abre al tocar la hamburguesa', async () => {
    // Arrange
    renderConProviders(<App />, { ruta: '/dashboard' })
    await screen.findByRole('heading', { name: /hola, damián/i })

    // Act
    await userEvent.setup().click(botonDelMenu())

    // Assert
    expect(botonDelMenu()).toHaveAttribute('aria-expanded', 'true')
    expect(botonDelMenu()).toHaveAccessibleName(/cerrar menú/i)
  })

  it('el nombre y la salida están dentro del panel, no sueltos en la barra', async () => {
    // Arrange
    renderConProviders(<App />, { ruta: '/dashboard' })
    await screen.findByRole('heading', { name: /hola, damián/i })

    // Act
    await userEvent.setup().click(botonDelMenu())

    // Assert: es lo que se pidió del diseño. Si estuvieran fuera del `nav`,
    // en celular quedarían en la barra superior en vez de al pie del menú.
    const panel = within(menu())
    expect(panel.getByText('Damián Orsi')).toBeVisible()
    expect(panel.getByRole('button', { name: /cerrar sesión/i })).toBeVisible()
  })

  it('el panel tiene todas las secciones', async () => {
    // Arrange
    renderConProviders(<App />, { ruta: '/dashboard' })
    await screen.findByRole('heading', { name: /hola, damián/i })

    // Act
    await userEvent.setup().click(botonDelMenu())

    // Assert
    const panel = within(menu())
    for (const seccion of [
      'Resumen',
      'Movimientos',
      'Categorías',
      'Presupuestos',
      'Reportes',
      'Recurrentes',
      'Asistente',
    ]) {
      expect(panel.getByRole('link', { name: seccion })).toBeVisible()
    }
  })

  it('se cierra solo al navegar a una sección', async () => {
    // Arrange
    renderConProviders(<App />, { ruta: '/dashboard' })
    await screen.findByRole('heading', { name: /hola, damián/i })
    const usuario = userEvent.setup()
    await usuario.click(botonDelMenu())

    // Act
    await usuario.click(within(menu()).getByRole('link', { name: 'Categorías' }))

    // Assert: si quedara abierto, taparía la pantalla que se acaba de abrir.
    await screen.findByRole('heading', { name: /categorías/i })
    await waitFor(() => expect(botonDelMenu()).toHaveAttribute('aria-expanded', 'false'))
  })

  it('Escape lo cierra y devuelve el foco al botón', async () => {
    // Arrange
    renderConProviders(<App />, { ruta: '/dashboard' })
    await screen.findByRole('heading', { name: /hola, damián/i })
    const usuario = userEvent.setup()
    await usuario.click(botonDelMenu())

    // Act
    await usuario.keyboard('{Escape}')

    // Assert: quien navega con teclado tiene que poder salir sin recorrer
    // todo el menú, y no quedar con el foco perdido en la nada.
    expect(botonDelMenu()).toHaveAttribute('aria-expanded', 'false')
    expect(botonDelMenu()).toHaveFocus()
  })

  it('tocar fuera del panel también lo cierra', async () => {
    // Arrange
    renderConProviders(<App />, { ruta: '/dashboard' })
    await screen.findByRole('heading', { name: /hola, damián/i })
    const usuario = userEvent.setup()
    await usuario.click(botonDelMenu())
    const telon = document.querySelector('.layout__telon')

    // Act
    await usuario.click(telon as HTMLElement)

    // Assert
    expect(botonDelMenu()).toHaveAttribute('aria-expanded', 'false')
  })

  it('cerrar sesión desde el panel funciona', async () => {
    // Arrange
    renderConProviders(<App />, { ruta: '/dashboard' })
    await screen.findByRole('heading', { name: /hola, damián/i })
    const usuario = userEvent.setup()
    await usuario.click(botonDelMenu())

    // Act
    await usuario.click(within(menu()).getByRole('button', { name: /cerrar sesión/i }))

    // Assert
    expect(await screen.findByRole('heading', { name: /iniciar sesión/i })).toBeVisible()
  })
})

describe('Atajo al asistente en el Resumen', () => {
  beforeEach(conSesion)

  it('está en el resumen y lleva al chat', async () => {
    // Arrange
    renderConProviders(<App />, { ruta: '/dashboard' })
    await screen.findByRole('heading', { name: /hola, damián/i })
    const atajo = screen.getByRole('link', { name: /abrir el asistente/i })

    // Act
    await userEvent.setup().click(atajo)

    // Assert
    expect(await screen.findByRole('heading', { name: /asistente/i })).toBeVisible()
  })

  it('no aparece en las demás pantallas', async () => {
    // Arrange / Act
    renderConProviders(<App />, { ruta: '/transactions' })
    await screen.findByRole('heading', { name: /movimientos/i })

    // Assert: es un atajo del resumen, no un elemento global.
    expect(screen.queryByRole('link', { name: /abrir el asistente/i })).not.toBeInTheDocument()
  })
})

describe('Tabla de movimientos en celular', () => {
  beforeEach(conSesion)

  it('cada celda lleva su encabezado en data-label', async () => {
    // Arrange / Act
    renderConProviders(<App />, { ruta: '/transactions' })
    await screen.findByRole('heading', { name: /movimientos/i })
    await screen.findByText('Supermercado')

    // Assert: en celular la tabla se muestra como tarjetas y el encabezado de
    // columna sale de `data-label`. Sin el atributo, la tarjeta quedaría con
    // valores sueltos sin decir de qué son.
    const celda = screen.getByText('Supermercado').closest('td')
    expect(celda).toHaveAttribute('data-label', 'Descripción')
  })

  it('conserva la semántica de tabla', async () => {
    // Arrange / Act
    renderConProviders(<App />, { ruta: '/transactions' })
    await screen.findByRole('heading', { name: /movimientos/i })

    // Assert: cambiar el `display` de los elementos de tabla borra su
    // semántica implícita; los `role` explícitos la sostienen.
    const tabla = await screen.findByRole('table', { name: /movimientos registrados/i })
    expect(tabla).toHaveClass('tabla--tarjetas')
    expect(within(tabla).getAllByRole('row').length).toBeGreaterThan(1)
  })
})
