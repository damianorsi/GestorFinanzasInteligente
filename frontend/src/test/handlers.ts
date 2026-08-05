import { HttpResponse, http } from 'msw'

import type { PeriodSummary, TokenResponse, User } from '@/types/api'

export const BASE = '/api/v1'

export const USUARIO: User = {
  id: 1,
  email: 'damian@ejemplo.com',
  full_name: 'Damián Orsi',
  is_active: true,
}

export const TOKENS: TokenResponse = {
  access_token: 'access-1',
  refresh_token: 'refresh-1',
  token_type: 'bearer',
  expires_in: 900,
}

export const RESUMEN: PeriodSummary = {
  currency: 'ARS',
  date_from: '2026-08-01',
  date_to: '2026-08-31',
  income: '850000.00',
  expense: '450000.50',
  balance: '399999.50',
}

/** Contador de renovaciones, para verificar que no se dispare más de una. */
export const contadores = { refresh: 0 }

export function reiniciarContadores(): void {
  contadores.refresh = 0
}

export const handlers = [
  http.post(`${BASE}/auth/login`, async ({ request }) => {
    const cuerpo = (await request.json()) as { email: string; password: string }
    if (cuerpo.password === 'incorrecta') {
      return HttpResponse.json(
        { code: 'invalid_credentials', message: 'Email o contraseña incorrectos.', details: [] },
        { status: 401 },
      )
    }
    return HttpResponse.json(TOKENS)
  }),

  http.post(`${BASE}/auth/register`, async ({ request }) => {
    const cuerpo = (await request.json()) as { email: string }
    if (cuerpo.email === 'repetido@ejemplo.com') {
      return HttpResponse.json(
        {
          code: 'email_already_registered',
          message: 'Ya existe una cuenta con ese email.',
          details: [],
        },
        { status: 409 },
      )
    }
    return HttpResponse.json(USUARIO, { status: 201 })
  }),

  http.post(`${BASE}/auth/refresh`, () => {
    contadores.refresh += 1
    return HttpResponse.json({ ...TOKENS, access_token: 'access-2', refresh_token: 'refresh-2' })
  }),

  http.post(`${BASE}/auth/logout`, () => new HttpResponse(null, { status: 204 })),

  http.get(`${BASE}/users/me`, ({ request }) => {
    if (!request.headers.get('Authorization')) {
      return HttpResponse.json(
        { code: 'invalid_token', message: 'Falta el token de acceso.', details: [] },
        { status: 401 },
      )
    }
    return HttpResponse.json(USUARIO)
  }),

  http.get(`${BASE}/reports/summary`, () => HttpResponse.json(RESUMEN)),
]
