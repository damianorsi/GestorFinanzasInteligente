import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { Modal } from '@/components/Modal'

function Anfitrion() {
  const [abierto, setAbierto] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setAbierto(true)}>
        Abrir
      </button>
      <Modal titulo="Título del modal" abierto={abierto} onCerrar={() => setAbierto(false)}>
        <input aria-label="Primero" />
        <input aria-label="Segundo" />
      </Modal>
    </>
  )
}

describe('Modal', () => {
  it('se anuncia como diálogo y toma su nombre del título', async () => {
    // Arrange
    render(<Anfitrion />)

    // Act
    await userEvent.setup().click(screen.getByRole('button', { name: 'Abrir' }))

    // Assert
    const dialogo = screen.getByRole('dialog')
    expect(dialogo).toHaveAttribute('aria-modal', 'true')
    expect(dialogo).toHaveAccessibleName('Título del modal')
  })

  it('mueve el foco adentro al abrirse', async () => {
    // Arrange
    render(<Anfitrion />)

    // Act
    await userEvent.setup().click(screen.getByRole('button', { name: 'Abrir' }))

    // Assert: sin esto, tabular seguiría recorriendo el contenido de atrás.
    expect(screen.getByRole('dialog')).toContainElement(
      document.activeElement as HTMLElement,
    )
  })

  it('atrapa el foco: tabular desde el último control vuelve al primero', async () => {
    // Arrange
    const usuario = userEvent.setup()
    render(<Anfitrion />)
    await usuario.click(screen.getByRole('button', { name: 'Abrir' }))

    // Act: se enfoca el último control del modal y se tabula una vez más.
    screen.getByLabelText('Segundo').focus()
    await usuario.tab()

    // Assert
    expect(screen.getByRole('dialog')).toContainElement(
      document.activeElement as HTMLElement,
    )
  })

  it('se cierra con Escape', async () => {
    // Arrange
    const usuario = userEvent.setup()
    render(<Anfitrion />)
    await usuario.click(screen.getByRole('button', { name: 'Abrir' }))

    // Act
    await usuario.keyboard('{Escape}')

    // Assert
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('devuelve el foco al botón que lo abrió', async () => {
    // Arrange
    const usuario = userEvent.setup()
    render(<Anfitrion />)
    const disparador = screen.getByRole('button', { name: 'Abrir' })
    await usuario.click(disparador)

    // Act
    await usuario.keyboard('{Escape}')

    // Assert: sin esto, quien navega con teclado queda al principio de la página.
    expect(disparador).toHaveFocus()
  })

  it('no renderiza nada mientras está cerrado', () => {
    // Arrange / Act
    render(
      <Modal titulo="X" abierto={false} onCerrar={vi.fn()}>
        <p>contenido</p>
      </Modal>,
    )

    // Assert
    expect(screen.queryByText('contenido')).not.toBeInTheDocument()
  })
})
