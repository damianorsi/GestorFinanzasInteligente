/** Llamadas a los endpoints de autenticación. */

import type { TokenResponse, User } from '@/types/api'

import { request } from './api'
import { clearSession, getRefreshToken, saveSession } from './session'

export async function login(email: string, password: string): Promise<TokenResponse> {
  const tokens = await request<TokenResponse>('/auth/login', {
    method: 'POST',
    body: { email, password },
    anonymous: true,
  })
  saveSession(tokens)
  return tokens
}

export async function register(
  email: string,
  password: string,
  fullName: string,
): Promise<User> {
  return request<User>('/auth/register', {
    method: 'POST',
    body: { email, password, full_name: fullName },
    anonymous: true,
  })
}

export async function fetchCurrentUser(): Promise<User> {
  return request<User>('/users/me')
}

/**
 * Cierra la sesión.
 *
 * La sesión local se limpia pase lo que pase con el request: si el servidor no
 * responde, dejar a la persona "logueada" en el navegador es peor que no haber
 * podido revocar el token, que además vence solo.
 */
export async function logout(): Promise<void> {
  const refreshToken = getRefreshToken()
  try {
    if (refreshToken) {
      await request<void>('/auth/logout', {
        method: 'POST',
        body: { refresh_token: refreshToken },
        anonymous: true,
      })
    }
  } catch {
    // Ignorado a propósito: ver el comentario de arriba.
  } finally {
    clearSession()
  }
}
