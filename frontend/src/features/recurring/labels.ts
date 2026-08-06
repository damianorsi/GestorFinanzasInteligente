import type { RecurrenceFrequency, RecurringRule } from '@/types/api'

export const FRECUENCIAS: { valor: RecurrenceFrequency; etiqueta: string }[] = [
  { valor: 'MONTHLY', etiqueta: 'Mensual' },
  { valor: 'WEEKLY', etiqueta: 'Semanal' },
  { valor: 'DAILY', etiqueta: 'Diaria' },
  { valor: 'YEARLY', etiqueta: 'Anual' },
]

/** 0 es lunes y 6 es domingo, igual que `date.weekday()` en el backend. */
export const DIAS_DE_LA_SEMANA = [
  'lunes',
  'martes',
  'miércoles',
  'jueves',
  'viernes',
  'sábado',
  'domingo',
]

/**
 * Describe la periodicidad en una frase.
 *
 * Se arma acá y no en cada componente para que el listado, el formulario y el
 * dashboard digan exactamente lo mismo.
 */
export function describirFrecuencia(regla: RecurringRule): string {
  switch (regla.frequency) {
    case 'MONTHLY':
      return `Todos los meses el día ${regla.day_of_month ?? '?'}`
    case 'WEEKLY':
      return `Todas las semanas los ${DIAS_DE_LA_SEMANA[regla.day_of_week ?? 0]}`
    case 'DAILY':
      return 'Todos los días'
    case 'YEARLY':
      return 'Una vez por año'
  }
}
