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

export function clearSession(): void {
  accessToken = null
  try {
    localStorage.removeItem(CLAVE_REFRESH)
  } catch {
    // Nada que hacer.
  }
}

export function hasStoredSession(): boolean {
  return getRefreshToken() !== null
}
