import { useState } from 'react'
import type { FormEvent } from 'react'

import { FormField } from '@/components/FormField'
import type { SavingsGoal } from '@/types/api'
import { aErroresDeFormulario } from '@/utils/apiErrors'
import type { ErroresDeFormulario } from '@/utils/apiErrors'

import { useCrearMeta, useEditarMeta } from './api'

interface GoalFormProps {
  meta?: SavingsGoal
  onListo: () => void
}

export function GoalForm({ meta, onListo }: GoalFormProps) {
  const esEdicion = meta !== undefined

  const [name, setName] = useState(meta?.name ?? '')
  const [targetAmount, setTargetAmount] = useState(meta?.target_amount ?? '')
  const [startsOn, setStartsOn] = useState(meta?.starts_on ?? '')
  const [targetDate, setTargetDate] = useState(meta?.target_date ?? '')
  const [errores, setErrores] = useState<ErroresDeFormulario>({
    general: null,
    porCampo: {},
  })

  const crear = useCrearMeta()
  const editar = useEditarMeta()
  const enviando = crear.isPending || editar.isPending

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault()
    setErrores({ general: null, porCampo: {} })

    try {
      if (esEdicion) {
        await editar.mutateAsync({
          id: meta.id,
          name,
          target_amount: targetAmount,
          starts_on: startsOn,
          // Vaciar el campo tiene que sacar la fecha, no dejarla como estaba.
          // Mandar `target_date: null` significaría «no la toques».
          ...(targetDate === ''
            ? { clear_target_date: true }
            : { target_date: targetDate }),
        })
      } else {
        await crear.mutateAsync({
          name,
          target_amount: targetAmount,
          ...(startsOn === '' ? {} : { starts_on: startsOn }),
          ...(targetDate === '' ? {} : { target_date: targetDate }),
        })
      }
      onListo()
    } catch (excepcion) {
      setErrores(
        aErroresDeFormulario(excepcion, {
          porCodigo: {
            duplicate_resource: {
              campo: 'name',
              mensaje: 'Ya tenés una meta con ese nombre.',
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
        id="meta-nombre"
        label="Nombre"
        value={name}
        onChange={(evento) => setName(evento.target.value)}
        error={errores.porCampo.name}
        maxLength={120}
        required
      />

      <FormField
        id="meta-objetivo"
        label="Cuánto querés juntar"
        type="number"
        inputMode="decimal"
        step="0.01"
        min="0.01"
        value={targetAmount}
        onChange={(evento) => setTargetAmount(evento.target.value)}
        error={errores.porCampo.target_amount}
        required
      />

      <FormField
        id="meta-inicio"
        label="Desde cuándo cuenta"
        type="date"
        value={startsOn}
        onChange={(evento) => setStartsOn(evento.target.value)}
        error={errores.porCampo.starts_on}
        hint={
          esEdicion
            ? 'Define qué movimientos cuentan para el avance.'
            : 'Si lo dejás vacío, la meta arranca hoy.'
        }
      />

      <FormField
        id="meta-fecha-objetivo"
        label="Para cuándo (opcional)"
        type="date"
        value={targetDate}
        onChange={(evento) => setTargetDate(evento.target.value)}
        error={errores.porCampo.target_date}
        hint="Sin fecha no se avisa si vas tarde, solo si no llegás nunca."
      />

      <div className="formulario__acciones">
        <button type="submit" className="boton" disabled={enviando}>
          {enviando ? 'Guardando…' : esEdicion ? 'Guardar' : 'Crear meta'}
        </button>
      </div>
    </form>
  )
}
