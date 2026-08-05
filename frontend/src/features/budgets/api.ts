import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { request } from '@/services/api'
import type { Budget, BudgetProgress } from '@/types/api'

export const CLAVE_PRESUPUESTOS = ['budgets'] as const

export function usePresupuestos(periodo: string) {
  return useQuery({
    queryKey: [...CLAVE_PRESUPUESTOS, 'lista', periodo],
    queryFn: () => request<Budget[]>('/budgets', { params: { period_month: periodo } }),
  })
}

export function useAvanceDePresupuestos(periodo: string) {
  return useQuery({
    queryKey: [...CLAVE_PRESUPUESTOS, 'progreso', periodo],
    queryFn: () =>
      request<BudgetProgress>('/budgets/progress', { params: { period_month: periodo } }),
  })
}

function useInvalidarPresupuestos() {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: CLAVE_PRESUPUESTOS })
  }
}

export function useCrearPresupuesto() {
  const invalidar = useInvalidarPresupuestos()
  return useMutation({
    mutationFn: (datos: { category_id: number; period_month: string; amount: string }) =>
      request<Budget>('/budgets', { method: 'POST', body: datos }),
    onSuccess: invalidar,
  })
}

export function useEditarPresupuesto() {
  const invalidar = useInvalidarPresupuestos()
  return useMutation({
    mutationFn: ({ id, amount }: { id: number; amount: string }) =>
      request<Budget>(`/budgets/${id}`, { method: 'PATCH', body: { amount } }),
    onSuccess: invalidar,
  })
}

export function useBorrarPresupuesto() {
  const invalidar = useInvalidarPresupuestos()
  return useMutation({
    mutationFn: (id: number) => request<void>(`/budgets/${id}`, { method: 'DELETE' }),
    onSuccess: invalidar,
  })
}

export interface ResultadoDeCopia {
  from_period: string
  to_period: string
  currency: string
  created: number
  skipped: { category_id: number; category_name: string }[]
}

export function useCopiarPresupuestos() {
  const invalidar = useInvalidarPresupuestos()
  return useMutation({
    mutationFn: (datos: { from_period: string; to_period: string }) =>
      request<ResultadoDeCopia>('/budgets/copy-from', { method: 'POST', body: datos }),
    onSuccess: invalidar,
  })
}
