import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { BudgetsPage } from '@/pages/BudgetsPage'
import { renderConProviders } from '@/test/render'

describe('BudgetsPage', () => {
  it('muestra el avance de cada presupuesto', async () => {
    // Arrange / Act
    renderConProviders(<BudgetsPage />)

    // Assert
    expect(await screen.findByText('Alimentación')).toBeVisible()
    expect(screen.getByText(/130.000,00.*de.*100.000,00/)).toBeVisible()
  })

  it('expone el avance como progressbar accesible', async () => {
    // Arrange / Act
    renderConProviders(<BudgetsPage />)

    // Assert
    const barras = await screen.findAllByRole('progressbar')
    expect(barras).toHaveLength(2)
    expect(barras[0]).toHaveAccessibleName(/alimentación.*excedido/i)
    expect(barras[1]).toHaveAccessibleName(/ocio.*cerca del tope/i)
  })

  it('la barra no se pasa del 100 aunque el porcentaje sí', async () => {
    // Arrange / Act
    renderConProviders(<BudgetsPage />)

    // Assert: el exceso se comunica con color y texto, no estirando la barra.
    const barras = await screen.findAllByRole('progressbar')
    expect(barras[0]).toHaveAttribute('aria-valuemax', '100')
    expect(barras[0]).toHaveAttribute('aria-valuenow', '130')
  })

  it('dice cuánto se pasó cuando se excedió el tope', async () => {
    // Arrange / Act
    renderConProviders(<BudgetsPage />)

    // Assert: el pie de la barra, no el aviso de arriba. Se compara el texto
    // completo porque "30.000,00" también aparece dentro de "130.000,00".
    await screen.findByText('Alimentación')
    const barra = screen.getAllByRole('progressbar').at(0)?.closest('li')
    expect(barra).not.toBeNull()
    const pie = within(barra as HTMLElement).getByText(/te pasaste/i)
    expect(pie.textContent).toMatch(/te pasaste\s*\$\s*30\.000,00/i)
  })

  it('resume cuántas categorías están excedidas', async () => {
    // Arrange / Act
    renderConProviders(<BudgetsPage />)

    // Assert
    expect(await screen.findByText(/te pasaste del tope en 1 categoría/i)).toBeVisible()
  })

  it('lista aparte los gastos sin presupuesto', async () => {
    /*
     * Si no se listaran, el mes parecería controlado con el grueso del gasto
     * fuera de todo tope.
     */
    // Arrange / Act
    renderConProviders(<BudgetsPage />)

    // Assert
    expect(await screen.findByRole('heading', { name: /gastos sin presupuesto/i })).toBeVisible()
    expect(screen.getByText('Transporte')).toBeVisible()
  })

  it('permite cambiar de mes', async () => {
    // Arrange
    const usuario = userEvent.setup()
    renderConProviders(<BudgetsPage />)
    const inicial = (await screen.findByText(/\d{4}$/)).textContent

    // Act: nombre exacto, porque "Copiar del mes anterior" también lo contiene.
    await usuario.click(screen.getByRole('button', { name: 'Mes anterior' }))

    // Assert
    await waitFor(() => expect(screen.getByText(/\d{4}$/).textContent).not.toBe(inicial))
  })

  it('informa qué se copió y qué se respetó al copiar del mes anterior', async () => {
    // Arrange
    const usuario = userEvent.setup()
    renderConProviders(<BudgetsPage />)
    await screen.findByText('Alimentación')

    // Act
    await usuario.click(screen.getByRole('button', { name: /copiar del mes anterior/i }))

    // Assert
    const aviso = await screen.findByText(/se copiaron 2 presupuestos/i)
    expect(aviso).toHaveTextContent(/no se tocaron los que ya existían: Alimentación/i)
  })

  it('el formulario solo ofrece categorías de gasto sin presupuesto', async () => {
    // Arrange
    const usuario = userEvent.setup()
    renderConProviders(<BudgetsPage />)
    await screen.findByText('Alimentación')

    // Act
    await usuario.click(screen.getByRole('button', { name: /nuevo presupuesto/i }))

    // Assert: Sueldo es ingreso y Alimentación ya tiene tope este mes.
    const selector = await screen.findByLabelText('Categoría')
    expect(selector).not.toHaveTextContent('Sueldo')
    expect(selector).not.toHaveTextContent('Alimentación')
    expect(selector).toHaveTextContent('Ocio')
  })
})
