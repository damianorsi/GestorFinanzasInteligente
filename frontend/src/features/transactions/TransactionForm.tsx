import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'

import { FormField } from '@/components/FormField'
import { SelectField } from '@/components/SelectField'
import { useCategorias } from '@/features/categories/api'
import type { Transaction, TransactionType } from '@/types/api'
import { aErroresDeFormulario } from '@/utils/apiErrors'
import type { ErroresDeFormulario } from '@/utils/apiErrors'

import { useCrearMovimiento, useEditarMovimiento } from './api'

/**
 * Valores con los que arranca un alta.
 *
 * Los usa la lectura de tickets para precargar el formulario. Es una precarga
 * y no un movimiento: la creación pasa por el mismo `POST /transactions` que
 * el alta manual, con las mismas validaciones (docs/PROMPT.md §21.1).
 */
export interface PrecargaDeMovimiento {
  amount?: string | null
  occurred_on?: string
  category_id?: number | null
  description?: string | null
  /** Campos que el lector marcó como dudosos, para señalarlos en el formulario. */
  camposDudosos?: string[]
}

interface TransactionFormProps {
  movimiento?: Transaction
  precarga?: PrecargaDeMovimiento
  onListo: () => void
}

function hoyEnIso(): string {
  const ahora = new Date()
  const mes = String(ahora.getMonth() + 1).padStart(2, '0')
  const dia = String(ahora.getDate()).padStart(2, '0')
  return `${ahora.getFullYear()}-${mes}-${dia}`
}

export function TransactionForm({ movimiento, precarga, onListo }: TransactionFormProps) {
  const esEdicion = movimiento !== undefined

  const [type, setType] = useState<TransactionType>(movimiento?.type ?? 'EXPENSE')
  const [amount, setAmount] = useState(movimiento?.amount ?? precarga?.amount ?? '')
  const [occurredOn, setOccurredOn] = useState(
    movimiento?.occurred_on ?? precarga?.occurred_on ?? hoyEnIso(),
  )
  const [categoryId, setCategoryId] = useState<number | ''>(
    movimiento?.category_id ?? precarga?.category_id ?? '',
  )
  const [description, setDescription] = useState(
    movimiento?.description ?? precarga?.description ?? '',
  )

  const dudosos = new Set(precarga?.camposDudosos ?? [])
  const [errores, setErrores] = useState<ErroresDeFormulario>({
    general: null,
    porCampo: {},
  })

  const categorias = useCategorias()
  const crear = useCrearMovimiento()
  const editar = useEditarMovimiento()
  const enviando = crear.isPending || editar.isPending

  // Solo las categorías del tipo elegido: ofrecer las otras invitaría a un 422
  // que el formulario puede evitar.
  const disponibles = useMemo(
    () => (categorias.data ?? []).filter((categoria) => categoria.type === type),
    [categorias.data, type],
  )

  const cambiarTipo = (nuevo: TransactionType) => {
    setType(nuevo)
    // La categoría elegida puede no servir para el tipo nuevo; se limpia en vez
    // de dejar una selección inválida escondida en el select.
    const sigueSirviendo = (categorias.data ?? []).some(
      (categoria) => categoria.id === categoryId && categoria.type === nuevo,
    )
    if (!sigueSirviendo) setCategoryId('')
  }

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault()
    setErrores({ general: null, porCampo: {} })

    if (categoryId === '') {
      setErrores({ general: null, porCampo: { category_id: 'Elegí una categoría.' } })
      return
    }

    const datos = {
      type,
      amount,
      occurred_on: occurredOn,
      category_id: categoryId,
      description,
    }

    try {
      if (esEdicion) {
        await editar.mutateAsync({ id: movimiento.id, ...datos })
      } else {
        await crear.mutateAsync(datos)
      }
      onListo()
    } catch (excepcion) {
      setErrores(
        aErroresDeFormulario(excepcion, {
          porCodigo: {
            invalid_reference: {
              campo: 'category_id',
              mensaje: 'Esa categoría no sirve para este tipo de movimiento.',
            },
          },
        }),
      )
    }
  }

  return (
    <form className="formulario" onSubmit={(evento) => void enviar(evento)} noValidate>
      {errores.general && (
        <p className="formulario__error" role="alert">
          {errores.general}
        </p>
      )}

      <SelectField
        id="mov-tipo"
        label="Tipo"
        value={type}
        onChange={(evento) => cambiarTipo(evento.target.value as TransactionType)}
      >
        <option value="EXPENSE">Gasto</option>
        <option value="INCOME">Ingreso</option>
      </SelectField>

      {/* El aviso de campo dudoso va como `hint` y no como error: el valor es
          usable, solo que el lector no estaba seguro. Marcarlo como error
          impediría distinguirlo de una validación que falló de verdad. */}
      <FormField
        id="mov-monto"
        label="Monto"
        type="number"
        inputMode="decimal"
        step="0.01"
        min="0.01"
        value={amount}
        onChange={(evento) => setAmount(evento.target.value)}
        hint={dudosos.has('amount') ? 'El lector no estaba seguro. Revisalo.' : undefined}
        error={errores.porCampo.amount}
        required
      />

      <FormField
        id="mov-fecha"
        label="Fecha"
        type="date"
        value={occurredOn}
        onChange={(evento) => setOccurredOn(evento.target.value)}
        hint={dudosos.has('occurred_on') ? 'El lector no estaba seguro. Revisala.' : undefined}
        error={errores.porCampo.occurred_on}
        required
      />

      <SelectField
        id="mov-categoria"
        label="Categoría"
        value={categoryId}
        onChange={(evento) =>
          setCategoryId(evento.target.value === '' ? '' : Number(evento.target.value))
        }
        error={errores.porCampo.category_id}
        required
      >
        <option value="">Elegí una categoría</option>
        {disponibles.map((categoria) => (
          <option key={categoria.id} value={categoria.id}>
            {categoria.name}
          </option>
        ))}
      </SelectField>

      <FormField
        id="mov-descripcion"
        label="Descripción"
        value={description}
        onChange={(evento) => setDescription(evento.target.value)}
        error={errores.porCampo.description}
        maxLength={255}
      />

      <div className="modal__acciones">
        <button type="button" className="boton boton--secundario" onClick={onListo}>
          Cancelar
        </button>
        <button type="submit" className="boton boton--primario" disabled={enviando}>
          {enviando ? 'Guardando…' : 'Guardar'}
        </button>
      </div>
    </form>
  )
}
