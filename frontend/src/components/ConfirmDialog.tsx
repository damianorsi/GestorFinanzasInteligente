import { Modal } from './Modal'

interface ConfirmDialogProps {
  abierto: boolean
  titulo: string
  mensaje: string
  textoConfirmar?: string
  enProceso?: boolean
  onConfirmar: () => void
  onCancelar: () => void
}

/** Confirmación para acciones destructivas. */
export function ConfirmDialog({
  abierto,
  titulo,
  mensaje,
  textoConfirmar = 'Borrar',
  enProceso = false,
  onConfirmar,
  onCancelar,
}: ConfirmDialogProps) {
  return (
    <Modal titulo={titulo} abierto={abierto} onCerrar={onCancelar}>
      <p className="modal__mensaje">{mensaje}</p>
      <div className="modal__acciones">
        {/* Cancelar va primero en el DOM para que sea lo primero que recibe el
            foco al abrirse: la opción segura no debería requerir apuntar. */}
        <button type="button" className="boton boton--secundario" onClick={onCancelar}>
          Cancelar
        </button>
        <button
          type="button"
          className="boton boton--peligro"
          onClick={onConfirmar}
          disabled={enProceso}
        >
          {enProceso ? 'Borrando…' : textoConfirmar}
        </button>
      </div>
    </Modal>
  )
}
