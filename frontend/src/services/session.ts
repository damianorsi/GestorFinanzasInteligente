/**
 * Almacenamiento de la sesión.
 *
 * **El access token vive solo en memoria** y el refresh token en
 * `localStorage`. La alternativa ideal sería una cookie `httpOnly`, pero el
 * backend devuelve los tokens en el cuerpo de la respuesta y cambiar eso
 * implicaría además resolver CSRF.
 *
 * El trade-off que queda: un XSS puede leer el refresh token de
 * `localStorage`. Se mitiga en parte porque el refresh **rota** —usarlo lo
 * revoca, así que el robo se vuelve detectable— y porque el access token, que
 * es el que abre todos los endpoints, nunca se persiste: cerrar la pestaña lo
 * borra.
 */

import type { TokenResponse } from '@/types/api'

const CLAVE_REFRESH = 'gfp.refresh_token'
/**
 * Conversación abierta del asistente.
 *
 * Va en `sessionStorage` y no en `localStorage`: una conversación pertenece a
 * la pestaña en la que se está hablando, y persistirla para siempre haría que
 * meses después se siguiera escribiendo en el mismo hilo.
 */
const CLAVE_CONVERSACION = 'gfp.conversation_id'

let accessToken: string | null = null

export function getAccessToken(): string | null {
  return accessToken
}

export function getRefreshToken(): string | null {
  try {
    return localStorage.getItem(CLAVE_REFRESH)
  } catch {
    // Modo privado de algunos navegadores, o storage deshabilitado.
    return null
  }
}

export function saveSession(tokens: TokenResponse): void {
  accessToken = tokens.access_token
  try {
    localStorage.setItem(CLAVE_REFRESH, tokens.refresh_token)
  } catch {
    // Sin persistencia la sesión dura lo que dure la pestaña, que es
    // degradado pero usable. No es motivo para romper el login.
  }
}

export function getConversationId(): string | null {
  try {
    return sessionStorage.getItem(CLAVE_CONVERSACION)
  } catch {
    return null
  }
}

export function saveConversationId(id: string): void {
  try {
    sessionStorage.setItem(CLAVE_CONVERSACION, id)
  } catch {
    // Sin persistencia el hilo dura lo que dure la pantalla montada, que es
    // degradado pero usable.
  }
}

export function clearConversationId(): void {
  try {
    sessionStorage.removeItem(CLAVE_CONVERSACION)
  } catch {
    // Nada que hacer.
  }
}

export function clearSession(): void {
  accessToken = null
  try {
    localStorage.removeItem(CLAVE_REFRESH)
  } catch {
    // Nada que hacer.
  }
  // La conversación se borra junto con la sesión: si en la misma pestaña
  // entra otra persona, el identificador guardado sería de un hilo ajeno.
  // El backend igual devolvería vacío —filtra por `user_id`—, pero dos
  // usuarios compartiendo un `conversation_id` es una confusión evitable.
  clearConversationId()
}

export function hasStoredSession(): boolean {
  return getRefreshToken() !== null
}
