import { useContext } from 'react'

import { AuthContext } from './context'
import type { AuthContextValue } from './context'

export function useAuth(): AuthContextValue {
  const contexto = useContext(AuthContext)
  if (contexto === null) {
    throw new Error('useAuth tiene que usarse dentro de <AuthProvider>.')
  }
  return contexto
}
