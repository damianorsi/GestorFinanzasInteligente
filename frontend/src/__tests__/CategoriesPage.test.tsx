import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { CategoriesPage } from '@/pages/CategoriesPage'
import { renderConProviders } from '@/test/render'

describe('CategoriesPage', () => {
  it('lista las categorías agrupadas por tipo', async () => {
    // Arrange / Act
    renderConProviders(<CategoriesPage />)

    // Assert
    expect(await screen.findByText('Alimentación')).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Ingresos' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Gastos' })).toBeVisible()
  })

  it('crea una categoría y la muestra en el listado', async () => {
    // Arrange
    const usuario = userEvent.setup()
    renderConProviders(<CategoriesPage />)
    await screen.findByText('Alimentación')

    // Act
    await usuario.click(screen.getByRole('button', { name: /nueva categoría/i }))
    await usuario.type(screen.getByLabelText('Nombre'), 'Mascotas')
    await usuario.click(screen.getByRole('button', { name: /guardar/i }))

    // Assert
    expect(await screen.findByText('Mascotas')).toBeVisible()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('muestra el conflicto si el nombre ya existe', async () => {
    // Arrange
    const usuario = userEvent.setup()
    renderConProviders(<CategoriesPage />)
    await screen.findByText('Ocio')

    // Act
    await usuario.click(screen.getByRole('button', { name: /nueva categoría/i }))
    await usuario.type(screen.getByLabelText('Nombre'), 'Ocio')
    await usuario.click(screen.getByRole('button', { name: /guardar/i }))

    // Assert
    expect(await screen.findByRole('alert')).toHaveTextContent(/ya tenés una categoría/i)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('no deja cambiar el tipo al editar', async () => {
    // Arrange
    const usuario = userEvent.setup()
    renderConProviders(<CategoriesPage />)
    await screen.findByText('Ocio')

    // Act
    const fila = screen.getByText('Ocio').closest('li')
    await usuario.click(within(fila as HTMLElement).getByRole('button', { name: /editar/i }))

    // Assert: cambiar el tipo convertiría los movimientos históricos en lo
    // contrario de lo que se registró.
    expect(screen.getByLabelText('Tipo')).toBeDisabled()
  })

  it('borra una categoría sin uso tras confirmar', async () => {
    // Arrange
    const usuario = userEvent.setup()
    renderConProviders(<CategoriesPage />)
    await screen.findByText('Ocio')

    // Act
    const fila = screen.getByText('Ocio').closest('li')
    await usuario.click(within(fila as HTMLElement).getByRole('button', { name: /borrar/i }))
    // Se acota al diálogo: el botón "Borrar" de la fila tiene el mismo nombre.
    await usuario.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Borrar' }),
    )

    // Assert
    await waitFor(() => expect(screen.queryByText('Ocio')).not.toBeInTheDocument())
  })

  it('muestra el detalle del backend cuando el borrado está bloqueado', async () => {
    /*
     * El 409 enumera qué está bloqueando la operación; mostrar un genérico
     * obligaría a adivinar qué hay que borrar antes.
     */
    // Arrange
    const usuario = userEvent.setup()
    renderConProviders(<CategoriesPage />)
    await screen.findByText('Alimentación')

    // Act
    const fila = screen.getByText('Alimentación').closest('li')
    await usuario.click(within(fila as HTMLElement).getByRole('button', { name: /borrar/i }))
    // Se acota al diálogo: el botón "Borrar" de la fila tiene el mismo nombre.
    await usuario.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Borrar' }),
    )

    // Assert
    expect(await screen.findByText(/1 movimiento asociados/i)).toBeVisible()
    expect(screen.getByText('Alimentación')).toBeVisible()
  })
})
