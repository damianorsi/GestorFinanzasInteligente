import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { request } from '@/services/api'
import type { AlertStatus, BudgetAlert } from '@/types/api'

export const CLAVE_ALERTAS = ['alerts'] as const

export function useAlertas(status?: AlertStatus) {
  return useQuery({
    queryKey: [...CLAVE_ALERTAS, status ?? 'todas'],
    queryFn: () => request<BudgetAlert[]>('/alerts', { params: { status } }),
  })
}

/**
 * Cuántas alertas hay sin leer.
 *
 * Va aparte del listado para poder pedirla desde el layout sin traer el
 * detalle de cada una: lo único que necesita el indicador es el número.
 */
export function useAlertasSinLeer() {
  const consulta = useAlertas('OPEN')
  return consulta.data?.length ?? 0
}

export function useMarcarAlertaLeida() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      request<BudgetAlert>(`/alerts/${id}`, { method: 'PATCH', body: { read: true } }),
    onSuccess: () => {
      // Se invalidan todas las variantes: al leer una, cambia tanto el listado
      // completo como el contador de sin leer del menú.
      void queryClient.invalidateQueries({ queryKey: CLAVE_ALERTAS })
    },
  })
}
