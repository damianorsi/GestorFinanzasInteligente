import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'

import { FormField } from '@/components/FormField'
import { SelectField } from '@/components/SelectField'
import { useCategorias } from '@/features/categories/api'
import type { Budget } from '@/types/api'
import { aErroresDeFormulario } from '@/utils/apiErrors'
import type { ErroresDeFormulario } from '@/utils/apiErrors'

import { useCrearPresupuesto, useEditarPresupuesto } from './api'

interface BudgetFormProps {
  periodo: string
  presupuesto?: Budget
  /** Categorías que ya tienen presupuesto en el período, para no ofrecerlas. */
  categoriasOcupadas: number[]
  onListo: () => void
}

export function BudgetForm({
  periodo,
  presupuesto,
  categoriasOcupadas,
  onListo,
}: BudgetFormProps) {
  const esEdicion = presupuesto !== undefined

  const [categoryId, setCategoryId] = useState<number | ''>(presupuesto?.category_id ?? '')
  const [amount, setAmount] = useState(presupuesto?.amount ?? '')
  const [errores, setErrores] = useState<ErroresDeFormulario>({
    general: null,
    porCampo: {},
  })

  // Solo gastos: un presupuesto es un tope de gasto y el backend rechaza los
  // ingresos con 422. Ofrecerlos sería invitar a un error evitable.
  const categorias = useCategorias('EXPENSE')
  const crear = useCrearPresupuesto()
  const editar = useEditarPresupuesto()
  const enviando = crear.isPending || editar.isPending

  const disponibles = useMemo(
    () => (categorias.data ?? []).filter((c) => !categoriasOcupadas.includes(c.id)),
    [categorias.data, categoriasOcupadas],
  )

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault()
    setErrores({ general: null, porCampo: {} })

    if (!esEdicion && categoryId === '') {
      setErrores({ general: null, porCampo: { category_id: 'Elegí una categoría.' } })
      return
    }

    try {
      if (esEdicion) {
        await editar.mutateAsync({ id: presupuesto.id, amount })
      } else {
        await crear.mutateAsync({
          category_id: categoryId as number,
          period_month: periodo,
          amount,
        })
      }
      onListo()
    } catch (excepcion) {
      setErrores(
        aErroresDeFormulario(excepcion, {
          porCodigo: {
            duplicate_resource: {
              campo: 'category_id',
              mensaje: 'Ya tenés un presupuesto de esa categoría para este mes.',
            },
            invalid_reference: {
              campo: 'category_id',
              mensaje: 'Los presupuestos solo aplican a categorías de gasto.',
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

      {esEdicion ? (
        <p className="campo__ayuda">
          Solo se puede cambiar el tope. La categoría y el mes identifican al
          presupuesto.
        </p>
      ) : (
        <SelectField
          id="presupuesto-categoria"
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
      )}

      <FormField
        id="presupuesto-monto"
        label="Tope mensual"
        type="number"
        inputMode="decimal"
        step="0.01"
        min="0.01"
        value={amount}
        onChange={(evento) => setAmount(evento.target.value)}
        error={errores.porCampo.amount}
        required
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
