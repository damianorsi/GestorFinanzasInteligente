import { createContext } from 'react'

import type { User } from '@/types/api'

/**
 * `cargando` es un tercer estado y no un booleano: al abrir la aplicación hay
 * que canjear el refresh token antes de saber si hay sesión. Sin ese estado, el
 * guard vería `usuario === null` durante ese instante y mandaría al login a
 * alguien que sí está autenticado.
 */
export type EstadoDeSesion = 'cargando' | 'autenticado' | 'anonimo'

export interface AuthContextValue {
  estado: EstadoDeSesion
  usuario: User | null
  iniciarSesion: (email: string, password: string) => Promise<void>
  registrarse: (email: string, password: string, fullName: string) => Promise<void>
  cerrarSesion: () => Promise<void>
}

/**
 * El contexto vive en su propio módulo, separado del provider: un archivo que
 * exporta un componente y algo que no lo es rompe el fast refresh de Vite.
 */
export const AuthContext = createContext<AuthContextValue | null>(null)
