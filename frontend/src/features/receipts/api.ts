import { useMutation } from '@tanstack/react-query'

import { request } from '@/services/api'
import type { ReceiptDraft } from '@/types/api'

/**
 * Lee un ticket y devuelve el borrador.
 *
 * No invalida ninguna query: el escaneo **no crea nada**. Lo que cambia el
 * estado es la confirmación posterior, que pasa por el alta de movimientos de
 * siempre y ya invalida lo que corresponde.
 */
export function useEscanearTicket() {
  return useMutation({
    mutationFn: (archivo: File) => {
      const cuerpo = new FormData()
      cuerpo.append('file', archivo)
      return request<ReceiptDraft>('/receipts/scan', { method: 'POST', body: cuerpo })
    },
  })
}
