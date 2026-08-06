import { useMutation, useQuery } from '@tanstack/react-query'

import { request } from '@/services/api'
import type { ChatAnswer, ChatMessage } from '@/types/api'

export const CLAVE_CHAT = ['chat'] as const

/**
 * Historial de una conversación.
 *
 * Solo se usa al montar la pantalla con una conversación ya empezada (una
 * recarga, típicamente). Durante la charla los mensajes se agregan en local:
 * refetchear el historial después de cada respuesta traería de vuelta lo mismo
 * que ya está en pantalla y haría parpadear la lista.
 */
export function useHistorialDeChat(conversationId: string | null) {
  return useQuery({
    queryKey: [...CLAVE_CHAT, 'historial', conversationId],
    queryFn: () =>
      request<ChatMessage[]>('/chat/history', {
        params: { conversation_id: conversationId },
      }),
    enabled: conversationId !== null,
    staleTime: Infinity,
  })
}

export function usePreguntarAlAsistente() {
  return useMutation({
    mutationFn: ({
      message,
      conversationId,
    }: {
      message: string
      conversationId: string | null
    }) =>
      request<ChatAnswer>('/chat', {
        method: 'POST',
        // El body no lleva `conversation_id` cuando no hay conversación: el
        // schema del backend rechaza campos de más, y mandar null obligaría a
        // que el contrato acepte un valor que no significa nada.
        body: conversationId === null ? { message } : { message, conversation_id: conversationId },
      }),
  })
}
