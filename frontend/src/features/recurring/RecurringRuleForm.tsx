import { useState } from 'react'
import type { FormEvent } from 'react'

import { FormField } from '@/components/FormField'
import { SelectField } from '@/components/SelectField'
import { useCategorias } from '@/features/categories/api'
import type { RecurrenceFrequency, RecurringRule, TransactionType } from '@/types/api'
import { aErroresDeFormulario } from '@/utils/apiErrors'
import type { ErroresDeFormulario } from '@/utils/apiErrors'

import { DIAS_DE_LA_SEMANA, FRECUENCIAS } from './labels'
import { useCrearRegla, useEditarRegla } from './api'

interface RecurringRuleFormProps {
  regla?: RecurringRule
  onListo: () => void
}

const HOY = () => new Date().toISOString().slice(0, 10)

export function RecurringRuleForm({ regla, onListo }: RecurringRuleFormProps) {
  const esEdicion = regla !== undefined

  const [tipo, setTipo] = useState<TransactionType>(regla?.type ?? 'EXPENSE')
  const [categoryId, setCategoryId] = useState<number | ''>(regla?.category_id ?? '')
  const [amount, setAmount] = useState(regla?.amount ?? '')
  const [descripcion, setDescripcion] = useState(regla?.description ?? '')
  const [frecuencia, setFrecuencia] = useState<RecurrenceFrequency>(regla?.frequency ?? 'MONTHLY')
  const [diaDelMes, setDiaDelMes] = useState<number | ''>(regla?.day_of_month ?? 1)
  const [diaDeLaSemana, setDiaDeLaSemana] = useState<number | ''>(regla?.day_of_week ?? 0)
  const [startsOn, setStartsOn] = useState(regla?.starts_on ?? HOY())
  const [endsOn, setEndsOn] = useState(regla?.ends_on ?? '')
  const [errores, setErrores] = useState<ErroresDeFormulario>({ general: null, porCampo: {} })

  // El tipo de la regla no se puede cambiar al editar: las ocurrencias ya
  // generadas quedarían describiendo algo distinto de lo que la regla dice.
  const categorias = useCategorias(tipo)
  const crear = useCrearRegla()
  const editar = useEditarRegla()
  const enviando = crear.isPending || editar.isPending

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault()
    setErrores({ general: null, porCampo: {} })

    if (categoryId === '') {
      setErrores({ general: null, porCampo: { category_id: 'Elegí una categoría.' } })
      return
    }

    // Cada frecuencia lleva exactamente los parámetros que usa: el backend
    // rechaza los sobrantes con un 422, así que se mandan solo los que aplican.
    const cuerpo = {
      category_id: categoryId,
      type: tipo,
      amount,
      frequency: frecuencia,
      starts_on: startsOn,
      description: descripcion,
      day_of_month: frecuencia === 'MONTHLY' ? Number(diaDelMes) : null,
      day_of_week: frecuencia === 'WEEKLY' ? Number(diaDeLaSemana) : null,
      ends_on: endsOn === '' ? null : endsOn,
    }

    try {
      if (esEdicion) {
        await editar.mutateAsync({ id: regla.id, ...cuerpo })
      } else {
        await crear.mutateAsync(cuerpo)
      }
      onListo()
    } catch (excepcion) {
      setErrores(
        aErroresDeFormulario(excepcion, {
          porCodigo: {
            invalid_reference: {
              campo: 'category_id',
              mensaje: 'La categoría tiene que ser del mismo tipo que la regla.',
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
        id="regla-tipo"
        label="Tipo"
        value={tipo}
        disabled={esEdicion}
        onChange={(evento) => {
          setTipo(evento.target.value as TransactionType)
          setCategoryId('')
        }}
      >
        <option value="EXPENSE">Gasto</option>
        <option value="INCOME">Ingreso</option>
      </SelectField>

      <SelectField
        id="regla-categoria"
        label="Categoría"
        value={categoryId}
        onChange={(evento) =>
          setCategoryId(evento.target.value === '' ? '' : Number(evento.target.value))
        }
        error={errores.porCampo.category_id}
        required
      >
        <option value="">Elegí una categoría</option>
        {(categorias.data ?? []).map((categoria) => (
          <option key={categoria.id} value={categoria.id}>
            {categoria.name}
          </option>
        ))}
      </SelectField>

      <FormField
        id="regla-monto"
        label="Monto"
        type="number"
        inputMode="decimal"
        step="0.01"
        min="0.01"
        value={amount}
        onChange={(evento) => setAmount(evento.target.value)}
        error={errores.porCampo.amount}
        required
      />

      <FormField
        id="regla-descripcion"
        label="Descripción"
        value={descripcion}
        maxLength={255}
        onChange={(evento) => setDescripcion(evento.target.value)}
        error={errores.porCampo.description}
      />

      <SelectField
        id="regla-frecuencia"
        label="Frecuencia"
        value={frecuencia}
        onChange={(evento) => setFrecuencia(evento.target.value as RecurrenceFrequency)}
      >
        {FRECUENCIAS.map((opcion) => (
          <option key={opcion.valor} value={opcion.valor}>
            {opcion.etiqueta}
          </option>
        ))}
      </SelectField>

      {frecuencia === 'MONTHLY' && (
        <FormField
          id="regla-dia-mes"
          label="Día del mes"
          type="number"
          min="1"
          max="31"
          value={diaDelMes}
          onChange={(evento) =>
            setDiaDelMes(evento.target.value === '' ? '' : Number(evento.target.value))
          }
          hint="Si el mes no tiene ese día, se ajusta al último. El 31 en febrero cae el 28."
          error={errores.porCampo.day_of_month}
          required
        />
      )}

      {frecuencia === 'WEEKLY' && (
        <SelectField
          id="regla-dia-semana"
          label="Día de la semana"
          value={diaDeLaSemana}
          onChange={(evento) => setDiaDeLaSemana(Number(evento.target.value))}
          error={errores.porCampo.day_of_week}
        >
          {DIAS_DE_LA_SEMANA.map((nombre, indice) => (
            <option key={nombre} value={indice}>
              {nombre}
            </option>
          ))}
        </SelectField>
      )}

      <FormField
        id="regla-inicio"
        label="Empieza el"
        type="date"
        value={startsOn}
        onChange={(evento) => setStartsOn(evento.target.value)}
        error={errores.porCampo.starts_on}
        required
      />

      <FormField
        id="regla-fin"
        label="Termina el"
        type="date"
        value={endsOn}
        onChange={(evento) => setEndsOn(evento.target.value)}
        hint="Opcional. Dejalo vacío para que no tenga fin."
        error={errores.porCampo.ends_on}
      />

      <p className="campo__ayuda">
        Al guardar vas a ver las próximas fechas que la regla va a generar. Los movimientos
        se crean recién el día que corresponde: nunca por adelantado.
      </p>

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
