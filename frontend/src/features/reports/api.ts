import { useQuery } from '@tanstack/react-query'

import { request } from '@/services/api'
import type { CategoryBreakdown, MonthlyTrend, PeriodSummary } from '@/types/api'

export const CLAVE_REPORTES = ['reports'] as const

/**
 * Alias de tipo y no `interface`: TypeScript solo le da index signature
 * implícita a los alias, y sin eso no se puede pasar directo como query params.
 */
export type Periodo = {
  date_from?: string
  date_to?: string
}

export function useResumen(periodo: Periodo = {}) {
  return useQuery({
    queryKey: [...CLAVE_REPORTES, 'summary', periodo],
    queryFn: () => request<PeriodSummary>('/reports/summary', { params: periodo }),
  })
}

export function useDesglosePorCategoria(periodo: Periodo = {}) {
  return useQuery({
    queryKey: [...CLAVE_REPORTES, 'by-category', periodo],
    queryFn: () => request<CategoryBreakdown>('/reports/by-category', { params: periodo }),
  })
}

export function useTendenciaMensual(meses = 6) {
  return useQuery({
    queryKey: [...CLAVE_REPORTES, 'monthly-trend', meses],
    queryFn: () => request<MonthlyTrend>('/reports/monthly-trend', { params: { months: meses } }),
  })
}
