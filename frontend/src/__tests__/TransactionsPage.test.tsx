import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { TransactionsPage } from '@/pages/TransactionsPage'
import { renderConProviders } from '@/test/render'

describe('TransactionsPage', () => {
  it('lista los movimientos con la categoría resuelta y el monto formateado', async () => {
    // Arrange / Act
    renderConProviders(<TransactionsPage />)

    // Assert
    expect(await screen.findByText('Supermercado')).toBeVisible()
    expect(screen.getByText(/1\.234,56/)).toBeVisible()
    const fila = screen.getByText('Supermercado').closest('tr')
    expect(within(fila as HTMLElement).getByText('Alimentación')).toBeVisible()
  })

  it('marca los movimientos generados por una regla', async () => {
    // Arrange / Act
    renderConProviders(<TransactionsPage />)

    // Assert
    const fila = (await screen.findByText('Sueldo agosto')).closest('tr')
    expect(within(fila as HTMLElement).getByText('recurrente')).toBeVisible()
  })

  it('distingue ingresos de gastos con el signo', async () => {
    // Arrange / Act
    renderConProviders(<TransactionsPage />)
    await screen.findByText('Supermercado')

    // Assert
    const gasto = screen.getByText('Supermercado').closest('tr')
    expect(within(gasto as HTMLElement).getByText(/−/)).toBeVisible()
    const ingreso = screen.getByText('Sueldo agosto').closest('tr')
    expect(within(ingreso as HTMLElement).getByText(/\+/)).toBeVisible()
  })

  it('filtra por tipo', async () => {
    // Arrange
    const usuario = userEvent.setup()
    renderConProviders(<TransactionsPage />)
    await screen.findByText('Supermercado')

    // Act
    await usuario.selectOptions(screen.getByLabelText('Tipo'), 'INCOME')

    // Assert
    await waitFor(() => expect(screen.queryByText('Supermercado')).not.toBeInTheDocument())
    expect(screen.getByText('Sueldo agosto')).toBeVisible()
  })

  it('busca por texto en la descripción', async () => {
    // Arrange
    const usuario = userEvent.setup()
    renderConProviders(<TransactionsPage />)
    await screen.findByText('Supermercado')

    // Act
    await usuario.type(screen.getByLabelText('Buscar'), 'Sueldo')

    // Assert
    await waitFor(() => expect(screen.queryByText('Supermercado')).not.toBeInTheDocument())
  })

  it('ofrece limpiar los filtros y vuelve a mostrar todo', async () => {
    // Arrange
    const usuario = userEvent.setup()
    renderConProviders(<TransactionsPage />)
    await screen.findByText('Supermercado')
    await usuario.selectOptions(screen.getByLabelText('Tipo'), 'INCOME')
    await waitFor(() => expect(screen.queryByText('Supermercado')).not.toBeInTheDocument())

    // Act
    await usuario.click(screen.getByRole('button', { name: /limpiar filtros/i }))

    // Assert
    expect(await screen.findByText('Supermercado')).toBeVisible()
  })

  it('crea un movimiento y lo muestra en la tabla', async () => {
    // Arrange
    const usuario = userEvent.setup()
    renderConProviders(<TransactionsPage />)
    await screen.findByText('Supermercado')

    // Act
    await usuario.click(screen.getByRole('button', { name: /nuevo movimiento/i }))
    // Se acota al diálogo: los filtros tienen campos con las mismas etiquetas.
    const formulario = within(screen.getByRole('dialog'))
    await usuario.type(formulario.getByLabelText('Monto'), '999.99')
    await usuario.selectOptions(formulario.getByLabelText('Categoría'), 'Ocio')
    await usuario.type(formulario.getByLabelText('Descripción'), 'Cine con amigos')
    await usuario.click(formulario.getByRole('button', { name: /guardar/i }))

    // Assert
    expect(await screen.findByText('Cine con amigos')).toBeVisible()
  })

  it('el selector de categoría solo ofrece las del tipo elegido', async () => {
    /*
     * Ofrecer las del otro tipo invitaría a un 422 que el formulario puede
     * evitar mostrando solo lo que sirve.
     */
    // Arrange
    const usuario = userEvent.setup()
    renderConProviders(<TransactionsPage />)
    await screen.findByText('Supermercado')
    await usuario.click(screen.getByRole('button', { name: /nuevo movimiento/i }))
    const formulario = within(screen.getByRole('dialog'))

    // Assert: por defecto es gasto, así que "Sueldo" no debería estar.
    const selector = formulario.getByLabelText('Categoría')
    expect(within(selector).queryByRole('option', { name: 'Sueldo' })).not.toBeInTheDocument()

    // Act
    await usuario.selectOptions(formulario.getByLabelText('Tipo'), 'INCOME')

    // Assert
    expect(within(selector).getByRole('option', { name: 'Sueldo' })).toBeInTheDocument()
    expect(
      within(selector).queryByRole('option', { name: 'Alimentación' }),
    ).not.toBeInTheDocument()
  })

  it('pide confirmación antes de borrar', async () => {
    // Arrange
    const usuario = userEvent.setup()
    renderConProviders(<TransactionsPage />)
    await screen.findByText('Supermercado')

    // Act
    const fila = screen.getByText('Supermercado').closest('tr')
    await usuario.click(within(fila as HTMLElement).getByRole('button', { name: /borrar/i }))

    // Assert
    expect(screen.getByRole('dialog')).toHaveTextContent(/no se puede deshacer/i)

    // Act: se acota al diálogo, porque la fila tiene otro botón igual.
    await usuario.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Borrar' }),
    )

    // Assert
    await waitFor(() => expect(screen.queryByText('Supermercado')).not.toBeInTheDocument())
  })

  it('muestra un estado vacío que distingue "sin datos" de "sin resultados"', async () => {
    // Arrange
    const usuario = userEvent.setup()
    renderConProviders(<TransactionsPage />)
    await screen.findByText('Supermercado')

    // Act
    await usuario.type(screen.getByLabelText('Buscar'), 'no-existe-nada-asi')

    // Assert
    expect(await screen.findByText(/probá con otros filtros/i)).toBeVisible()
  })

  it('informa el rango y el total en el paginador', async () => {
    // Arrange / Act
    renderConProviders(<TransactionsPage />)

    // Assert
    expect(await screen.findByText('1–2 de 2')).toBeVisible()
  })
})
