import { useRef, useState } from 'react'
import type { ChangeEvent } from 'react'

import { Cargando } from '@/components/Feedback'
import type { ReceiptDraft } from '@/types/api'
import { aErroresDeFormulario } from '@/utils/apiErrors'
import { formatDate, formatMoney } from '@/utils/format'

import { useEscanearTicket } from './api'

/** Los mismos que acepta el backend. Sin esto el 422 llega recién del servidor. */
const TIPOS_ACEPTADOS = 'image/jpeg,image/png,image/webp'

interface ReceiptScannerProps {
  /** Se llama cuando la persona confirma el borrador y quiere cargarlo. */
  onConfirmar: (borrador: ReceiptDraft) => void
  onCancelar: () => void
}

/**
 * Saca la foto de un ticket y muestra lo que el lector entendió.
 *
 * Nunca crea el movimiento: al confirmar, el borrador precarga el formulario
 * de alta de siempre (docs/PROMPT.md §21.1).
 */
export function ReceiptScanner({ onConfirmar, onCancelar }: ReceiptScannerProps) {
  const escanear = useEscanearTicket()
  const [borrador, setBorrador] = useState<ReceiptDraft | null>(null)
  const [error, setError] = useState<string | null>(null)
  const entradaRef = useRef<HTMLInputElement>(null)

  const alElegirArchivo = async (evento: ChangeEvent<HTMLInputElement>) => {
    const archivo = evento.target.files?.[0]
    // Se limpia el input enseguida: si no, elegir la misma foto dos veces
    // seguidas no dispara `change` y parece que la aplicación se colgó.
    evento.target.value = ''
    if (!archivo) return

    setError(null)
    setBorrador(null)
    try {
      setBorrador(await escanear.mutateAsync(archivo))
    } catch (excepcion) {
      setError(
        aErroresDeFormulario(excepcion, {
          porCodigo: {
            assistant_unavailable: {
              mensaje:
                'El lector no está disponible en este momento. Podés cargar el gasto a mano.',
            },
          },
        }).general,
      )
    }
  }

  if (escanear.isPending) {
    return <Cargando mensaje="Leyendo el ticket…" />
  }

  if (borrador) {
    return (
      <ResumenDelBorrador
        borrador={borrador}
        onConfirmar={() => onConfirmar(borrador)}
        onOtraFoto={() => setBorrador(null)}
      />
    )
  }

  return (
    <div className="escaner">
      {error && (
        <p className="formulario__error" role="alert">
          {error}
        </p>
      )}

      <p className="escaner__ayuda">
        Sacale una foto al ticket y te propongo el movimiento. Vas a poder revisarlo antes
        de guardarlo: <strong>no se carga nada sin que lo confirmes</strong>.
      </p>

      <label className="visualmente-oculto" htmlFor="ticket-archivo">
        Foto del ticket
      </label>
      <input
        id="ticket-archivo"
        ref={entradaRef}
        className="escaner__entrada"
        type="file"
        accept={TIPOS_ACEPTADOS}
        // `environment` abre la cámara trasera directamente en el celular, que
        // es donde se saca la foto de un ticket. En escritorio el navegador lo
        // ignora y ofrece el explorador de archivos.
        capture="environment"
        onChange={(evento) => void alElegirArchivo(evento)}
      />

      <div className="modal__acciones">
        <button type="button" className="boton boton--secundario" onClick={onCancelar}>
          Cancelar
        </button>
      </div>
    </div>
  )
}

function ResumenDelBorrador({
  borrador,
  onConfirmar,
  onOtraFoto,
}: {
  borrador: ReceiptDraft
  onConfirmar: () => void
  onOtraFoto: () => void
}) {
  const dudoso = (campo: string) => borrador.low_confidence_fields.includes(campo)

  return (
    <div className="escaner">
      <p className="escaner__ayuda">
        Esto es lo que entendí. Revisalo y confirmá para cargarlo.
      </p>

      <dl className="escaner__lectura">
        <dt>Monto</dt>
        <dd className={dudoso('amount') ? 'escaner__dato escaner__dato--dudoso' : 'escaner__dato'}>
          {borrador.amount ? formatMoney(borrador.amount, borrador.currency) : 'no lo pude leer'}
          {dudoso('amount') && <span className="etiqueta">revisar</span>}
        </dd>

        <dt>Fecha</dt>
        <dd
          className={
            dudoso('occurred_on') ? 'escaner__dato escaner__dato--dudoso' : 'escaner__dato'
          }
        >
          {formatDate(borrador.occurred_on)}
          {dudoso('occurred_on') && <span className="etiqueta">revisar</span>}
        </dd>

        {borrador.merchant && (
          <>
            <dt>Comercio</dt>
            <dd className="escaner__dato">{borrador.merchant}</dd>
          </>
        )}

        <dt>Categoría</dt>
        <dd className="escaner__dato">
          {borrador.category_name ?? 'la elegís vos en el próximo paso'}
        </dd>
      </dl>

      {borrador.low_confidence_fields.length > 0 && (
        <p className="aviso aviso--alerta" role="status">
          Hay datos que no leí con seguridad. Están marcados: revisalos antes de guardar.
        </p>
      )}

      {borrador.possible_duplicates.length > 0 && (
        <p className="aviso aviso--alerta" role="status">
          Ya tenés un movimiento por ese monto y esa fecha. Puede ser que hayas escaneado
          este ticket antes.
        </p>
      )}

      <div className="modal__acciones">
        <button type="button" className="boton boton--secundario" onClick={onOtraFoto}>
          Probar otra foto
        </button>
        <button type="button" className="boton boton--primario" onClick={onConfirmar}>
          Usar estos datos
        </button>
      </div>
    </div>
  )
}
