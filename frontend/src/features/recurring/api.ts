import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { request } from '@/services/api'
import type {
  Occurrence,
  RecurrenceFrequency,
  RecurringRule,
  TransactionType,
  UpcomingSummary,
} from '@/types/api'

export const CLAVE_RECURRENTES = ['recurring'] as const

export interface DatosDeRegla {
  category_id: number
  type: TransactionType
  amount: string
  frequency: RecurrenceFrequency
  starts_on: string
  description?: string
  day_of_month?: number | null
  day_of_week?: number | null
  ends_on?: string | null
}

export function useReglas(soloActivas?: boolean) {
  return useQuery({
    queryKey: [...CLAVE_RECURRENTES, 'lista', soloActivas ?? 'todas'],
    queryFn: () =>
      request<RecurringRule[]>('/recurring-rules', {
        params: { is_active: soloActivas },
      }),
  })
}

export function useOcurrencias(ruleId: number | null) {
  return useQuery({
    queryKey: [...CLAVE_RECURRENTES, 'ocurrencias', ruleId],
    queryFn: () => request<Occurrence[]>(`/recurring-rules/${ruleId}/occurrences`),
    enabled: ruleId !== null,
  })
}

export function useProximosVencimientos(dias = 30) {
  return useQuery({
    queryKey: [...CLAVE_RECURRENTES, 'upcoming', dias],
    queryFn: () => request<UpcomingSummary>('/recurring-rules/upcoming', { params: { days: dias } }),
  })
}

/**
 * Invalida todo lo que depende de las reglas.
 *
 * Incluye los movimientos: pausar o borrar una regla no cambia el historial,
 * pero reactivarla sí escribe en el libro mayor, y el listado de ocurrencias
 * quedaría mostrando el estado anterior.
 */
function useInvalidarRecurrentes() {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: CLAVE_RECURRENTES })
  }
}

export function useCrearRegla() {
  const invalidar = useInvalidarRecurrentes()
  return useMutation({
    mutationFn: (datos: DatosDeRegla) =>
      request<RecurringRule>('/recurring-rules', { method: 'POST', body: datos }),
    onSuccess: invalidar,
  })
}

export function useEditarRegla() {
  const invalidar = useInvalidarRecurrentes()
  return useMutation({
    mutationFn: ({ id, ...cambios }: Partial<DatosDeRegla> & { id: number; is_active?: boolean }) =>
      request<RecurringRule>(`/recurring-rules/${id}`, { method: 'PATCH', body: cambios }),
    onSuccess: invalidar,
  })
}

export function useBorrarRegla() {
  const invalidar = useInvalidarRecurrentes()
  return useMutation({
    mutationFn: (id: number) => request<void>(`/recurring-rules/${id}`, { method: 'DELETE' }),
    onSuccess: invalidar,
  })
}
