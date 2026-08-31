/**
 * Cliente HTTP centralizado.
 *
 * Adjunta el token de acceso y, ante un 401, renueva la sesión una vez y
 * reintenta el request original.
 */

import type { ApiErrorBody, TokenResponse } from '@/types/api'

import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  saveSession,
} from './session'

const BASE_URL = '/api/v1'

/** Error de la API con el `code` estable ya extraído. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: { field: string; reason: string }[] = [],
  ) {
    super(message)
    this.name = 'ApiError'
  }

  /** Motivo asociado a un campo, para marcarlo en el formulario. */
  reasonFor(field: string): string | undefined {
    return this.details.find((detalle) => detalle.field === field)?.reason
  }
}

export class NetworkError extends Error {
  constructor() {
    super('No se pudo conectar con el servidor. Revisá tu conexión.')
    this.name = 'NetworkError'
  }
}

/**
 * Renovación en curso, compartida por todos los requests.
 *
 * No es una optimización: el refresh token **rota**, así que si tres requests
 * reciben 401 a la vez y cada uno dispara su propia renovación, la primera
 * invalida el token y las otras dos fallan cerrando la sesión de una persona
 * que estaba usando la aplicación con normalidad.
 */
let renovacionEnCurso: Promise<boolean> | null = null

async function renovarSesion(): Promise<boolean> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return false

  try {
    const respuesta = await fetch(`${BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!respuesta.ok) {
      clearSession()
      return false
    }
    saveSession((await respuesta.json()) as TokenResponse)
    return true
  } catch {
    // Un fallo de red al renovar no significa que la sesión sea inválida, así
    // que no se borra: el próximo intento puede funcionar.
    return false
  }
}

export async function refreshSession(): Promise<boolean> {
  renovacionEnCurso ??= renovarSesion().finally(() => {
    renovacionEnCurso = null
  })
  return renovacionEnCurso
}

interface OpcionesDeRequest {
  method?: string
  body?: unknown
  /** Query params; los `undefined` y `null` se omiten. */
  params?: Record<string, string | number | boolean | undefined | null>
  /** Endpoints públicos: no adjuntan token ni intentan renovar. */
  anonymous?: boolean
}

/**
 * `true` si el cuerpo lo tiene que serializar el navegador y no nosotros.
 *
 * Con `FormData` hay que dejar que el navegador ponga el `Content-Type`: lleva
 * el `boundary` que separa las partes, y ponerlo a mano lo omite y el backend
 * no puede parsear nada.
 */
function esFormulario(body: unknown): body is FormData {
  return typeof FormData !== 'undefined' && body instanceof FormData
}

function construirUrl(path: string, params?: OpcionesDeRequest['params']): string {
  const url = `${BASE_URL}${path}`
  if (!params) return url
  const query = new URLSearchParams()
  for (const [clave, valor] of Object.entries(params)) {
    if (valor !== undefined && valor !== null && valor !== '') {
      query.append(clave, String(valor))
    }
  }
  const cadena = query.toString()
  return cadena ? `${url}?${cadena}` : url
}

async function ejecutar(path: string, opciones: OpcionesDeRequest): Promise<Response> {
  const headers: Record<string, string> = {}
  const formulario = esFormulario(opciones.body)
  if (opciones.body !== undefined && !formulario) {
    headers['Content-Type'] = 'application/json'
  }

  const token = getAccessToken()
  if (!opciones.anonymous && token) headers.Authorization = `Bearer ${token}`

  // El guard se llama en línea y no se reusa `formulario`: TypeScript estrecha
  // el tipo por la llamada, no por un booleano guardado antes.
  let cuerpo: BodyInit | undefined
  if (esFormulario(opciones.body)) {
    cuerpo = opciones.body
  } else if (opciones.body !== undefined) {
    cuerpo = JSON.stringify(opciones.body)
  }

  try {
    return await fetch(construirUrl(path, opciones.params), {
      method: opciones.method ?? 'GET',
      headers,
      body: cuerpo,
    })
  } catch {
    throw new NetworkError()
  }
}

async function aError(respuesta: Response): Promise<ApiError> {
  try {
    const cuerpo = (await respuesta.json()) as ApiErrorBody
    return new ApiError(
      respuesta.status,
      cuerpo.code ?? 'unknown',
      cuerpo.message ?? 'Ocurrió un error inesperado.',
      cuerpo.details ?? [],
    )
  } catch {
    // Respuesta sin cuerpo JSON: pasa con un 502 del proxy, por ejemplo.
    return new ApiError(respuesta.status, 'unknown', 'Ocurrió un error inesperado.')
  }
}

/** Hace un request autenticado y devuelve el cuerpo ya parseado. */
export async function request<T>(path: string, opciones: OpcionesDeRequest = {}): Promise<T> {
  let respuesta = await ejecutar(path, opciones)

  if (respuesta.status === 401 && !opciones.anonymous) {
    // Se reintenta una sola vez: si tras renovar sigue dando 401, el problema
    // no es el token vencido y reintentar en bucle solo demoraría el error.
    if (await refreshSession()) {
      respuesta = await ejecutar(path, opciones)
    }
  }

  if (!respuesta.ok) throw await aError(respuesta)

  if (respuesta.status === 204) return undefined as T
  return (await respuesta.json()) as T
}

/** Descarga un archivo; devuelve el blob y el nombre sugerido por el servidor. */
export async function download(
  path: string,
  params?: OpcionesDeRequest['params'],
): Promise<{ blob: Blob; filename: string }> {
  let respuesta = await ejecutar(path, { params })
  if (respuesta.status === 401 && (await refreshSession())) {
    respuesta = await ejecutar(path, { params })
  }
  if (!respuesta.ok) throw await aError(respuesta)

  const disposicion = respuesta.headers.get('content-disposition') ?? ''
  const coincidencia = /filename="?([^";]+)"?/.exec(disposicion)
  return {
    blob: await respuesta.blob(),
    filename: coincidencia?.[1] ?? 'descarga.csv',
  }
}
