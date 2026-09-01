import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { request } from '@/services/api'
import type { SavingsGoal, SavingsGoalProgress } from '@/types/api'

export const CLAVE_METAS = ['savings-goals'] as const

export function useMetas() {
  return useQuery({
    queryKey: [...CLAVE_METAS, 'lista'],
    queryFn: () => request<SavingsGoal[]>('/savings-goals'),
  })
}

export function useAvanceDeMetas() {
  return useQuery({
    queryKey: [...CLAVE_METAS, 'progreso'],
    queryFn: () => request<SavingsGoalProgress[]>('/savings-goals/progress'),
  })
}

function useInvalidarMetas() {
  const queryClient = useQueryClient()
  return () => {
    // Se invalida la clave entera: crear o editar una meta cambia tanto el
    // listado como el avance, y refrescar solo uno dejaría la pantalla
    // mostrando dos verdades distintas.
    void queryClient.invalidateQueries({ queryKey: CLAVE_METAS })
  }
}

export interface DatosDeMeta {
  name: string
  target_amount: string
  starts_on?: string
  target_date?: string | null
}

export function useCrearMeta() {
  const invalidar = useInvalidarMetas()
  return useMutation({
    mutationFn: (datos: DatosDeMeta) =>
      request<SavingsGoal>('/savings-goals', { method: 'POST', body: datos }),
    onSuccess: invalidar,
  })
}

export function useEditarMeta() {
  const invalidar = useInvalidarMetas()
  return useMutation({
    mutationFn: ({
      id,
      ...datos
    }: Partial<DatosDeMeta> & {
      id: number
      is_active?: boolean
      /** `target_date: null` significa «no lo toques»; para sacarla va este flag. */
      clear_target_date?: boolean
    }) => request<SavingsGoal>(`/savings-goals/${id}`, { method: 'PATCH', body: datos }),
    onSuccess: invalidar,
  })
}

export function useBorrarMeta() {
  const invalidar = useInvalidarMetas()
  return useMutation({
    mutationFn: (id: number) =>
      request<void>(`/savings-goals/${id}`, { method: 'DELETE' }),
    onSuccess: invalidar,
  })
}
