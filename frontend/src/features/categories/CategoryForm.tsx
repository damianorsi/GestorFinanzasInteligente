import { useState } from 'react'
import type { FormEvent } from 'react'

import { FormField } from '@/components/FormField'
import { SelectField } from '@/components/SelectField'
import type { Category, TransactionType } from '@/types/api'
import { aErroresDeFormulario } from '@/utils/apiErrors'
import type { ErroresDeFormulario } from '@/utils/apiErrors'

import { useCrearCategoria, useEditarCategoria } from './api'

const COLOR_POR_DEFECTO = '#6b7280'

interface CategoryFormProps {
  /** Si viene, el formulario edita; si no, crea. */
  categoria?: Category
  onListo: () => void
}

export function CategoryForm({ categoria, onListo }: CategoryFormProps) {
  const esEdicion = categoria !== undefined

  const [name, setName] = useState(categoria?.name ?? '')
  const [type, setType] = useState<TransactionType>(categoria?.type ?? 'EXPENSE')
  const [color, setColor] = useState(categoria?.color ?? COLOR_POR_DEFECTO)
  const [errores, setErrores] = useState<ErroresDeFormulario>({
    general: null,
    porCampo: {},
  })

  const crear = useCrearCategoria()
  const editar = useEditarCategoria()
  const enviando = crear.isPending || editar.isPending

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault()
    setErrores({ general: null, porCampo: {} })

    try {
      if (esEdicion) {
        await editar.mutateAsync({ id: categoria.id, name, color })
      } else {
        await crear.mutateAsync({ name, type, color })
      }
      onListo()
    } catch (excepcion) {
      setErrores(
        aErroresDeFormulario(excepcion, {
          porCodigo: {
            duplicate_resource: {
              campo: 'name',
              mensaje: 'Ya tenés una categoría con ese nombre y tipo.',
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

      <FormField
        id="categoria-nombre"
        label="Nombre"
        value={name}
        onChange={(evento) => setName(evento.target.value)}
        error={errores.porCampo.name}
        maxLength={60}
        required
      />

      <SelectField
        id="categoria-tipo"
        label="Tipo"
        value={type}
        onChange={(evento) => setType(evento.target.value as TransactionType)}
        // El tipo es inmutable al editar: cambiarlo convertiría los movimientos
        // históricos en lo contrario de lo que se registró.
        disabled={esEdicion}
      >
        <option value="EXPENSE">Gasto</option>
        <option value="INCOME">Ingreso</option>
      </SelectField>
      {esEdicion && (
        <p className="campo__ayuda">
          El tipo no se puede cambiar. Creá otra categoría y mové los movimientos.
        </p>
      )}

      <FormField
        id="categoria-color"
        label="Color"
        type="color"
        value={color}
        onChange={(evento) => setColor(evento.target.value)}
        error={errores.porCampo.color}
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
