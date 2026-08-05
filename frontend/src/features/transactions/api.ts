import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { download, request } from '@/services/api'
import type { Paginated, Transaction, TransactionType } from '@/types/api'

export const CLAVE_MOVIMIENTOS = ['transactions'] as const

export interface FiltrosDeMovimientos {
  date_from?: string
  date_to?: string
  category_id?: number
  type?: TransactionType
  min_amount?: string
  max_amount?: string
  q?: string
  is_recurring?: boolean
  sort?: string
}

export const FILTROS_VACIOS: FiltrosDeMovimientos = {}

export function useMovimientos(
  filtros: FiltrosDeMovimientos,
  pagina: { offset: number; limit: number },
) {
  return useQuery({
    queryKey: [...CLAVE_MOVIMIENTOS, filtros, pagina],
    queryFn: () =>
      request<Paginated<Transaction>>('/transactions', {
        params: { ...filtros, ...pagina },
      }),
    // Mantiene la página anterior mientras carga la nueva, para que la tabla
    // no colapse a vacío y la pantalla no salte al paginar.
    placeholderData: (anterior) => anterior,
  })
}

export interface DatosDeMovimiento {
  type: TransactionType
  amount: string
  occurred_on: string
  category_id: number
  description: string
}

/**
 * Un movimiento cambia el balance, los reportes y el avance de los
 * presupuestos, así que todo eso se invalida junto. Refrescar solo la tabla
 * dejaría las tarjetas del resumen con números viejos.
 */
function useInvalidarMovimientos() {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: CLAVE_MOVIMIENTOS })
    void queryClient.invalidateQueries({ queryKey: ['reports'] })
    void queryClient.invalidateQueries({ queryKey: ['budgets'] })
  }
}

export function useCrearMovimiento() {
  const invalidar = useInvalidarMovimientos()
  return useMutation({
    mutationFn: (datos: DatosDeMovimiento) =>
      request<Transaction>('/transactions', { method: 'POST', body: datos }),
    onSuccess: invalidar,
  })
}

export function useEditarMovimiento() {
  const invalidar = useInvalidarMovimientos()
  return useMutation({
    mutationFn: ({ id, ...datos }: { id: number } & Partial<DatosDeMovimiento>) =>
      request<Transaction>(`/transactions/${id}`, { method: 'PATCH', body: datos }),
    onSuccess: invalidar,
  })
}

export function useBorrarMovimiento() {
  const invalidar = useInvalidarMovimientos()
  return useMutation({
    mutationFn: (id: number) => request<void>(`/transactions/${id}`, { method: 'DELETE' }),
    onSuccess: invalidar,
  })
}

/** Descarga el CSV respetando los filtros activos. */
export async function exportarMovimientos(
  filtros: FiltrosDeMovimientos,
  formato: 'standard' | 'excel_es',
): Promise<void> {
  const { blob, filename } = await download('/transactions/export', {
    ...filtros,
    format: formato,
  })

  const url = URL.createObjectURL(blob)
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = filename
  document.body.appendChild(enlace)
  enlace.click()
  enlace.remove()
  // Sin revoke, el blob queda retenido en memoria hasta recargar la página.
  URL.revokeObjectURL(url)
}
