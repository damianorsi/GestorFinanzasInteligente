import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { request } from '@/services/api'
import type { Category, TransactionType } from '@/types/api'

export const CLAVE_CATEGORIAS = ['categories'] as const

export function useCategorias(tipo?: TransactionType) {
  return useQuery({
    queryKey: [...CLAVE_CATEGORIAS, tipo ?? 'todas'],
    queryFn: () => request<Category[]>('/categories', { params: { type: tipo } }),
  })
}

export interface DatosDeCategoria {
  name: string
  type: TransactionType
  color?: string | null
}

/**
 * Invalida todo lo que depende de las categorías.
 *
 * No alcanza con refrescar el listado: los movimientos y los presupuestos
 * muestran el nombre de la categoría, así que renombrar una y no invalidarlos
 * dejaría el nombre viejo en pantalla hasta el próximo refetch.
 */
function useInvalidarCategorias() {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: CLAVE_CATEGORIAS })
    void queryClient.invalidateQueries({ queryKey: ['transactions'] })
    void queryClient.invalidateQueries({ queryKey: ['budgets'] })
    void queryClient.invalidateQueries({ queryKey: ['reports'] })
  }
}

export function useCrearCategoria() {
  const invalidar = useInvalidarCategorias()
  return useMutation({
    mutationFn: (datos: DatosDeCategoria) =>
      request<Category>('/categories', { method: 'POST', body: datos }),
    onSuccess: invalidar,
  })
}

export function useEditarCategoria() {
  const invalidar = useInvalidarCategorias()
  return useMutation({
    mutationFn: ({ id, ...datos }: { id: number; name?: string; color?: string | null }) =>
      request<Category>(`/categories/${id}`, { method: 'PATCH', body: datos }),
    onSuccess: invalidar,
  })
}

export function useBorrarCategoria() {
  const invalidar = useInvalidarCategorias()
  return useMutation({
    mutationFn: (id: number) => request<void>(`/categories/${id}`, { method: 'DELETE' }),
    onSuccess: invalidar,
  })
}
