import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { refreshSession } from '@/services/api'
import * as authService from '@/services/auth'
import { hasStoredSession } from '@/services/session'
import type { User } from '@/types/api'

import { AuthContext } from './context'
import type { AuthContextValue, EstadoDeSesion } from './context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [estado, setEstado] = useState<EstadoDeSesion>(
    hasStoredSession() ? 'cargando' : 'anonimo',
  )
  const [usuario, setUsuario] = useState<User | null>(null)

  useEffect(() => {
    if (!hasStoredSession()) return

    let cancelado = false
    const restaurar = async () => {
      // El access token vive en memoria, así que tras un refresh de la página
      // hay que canjear el token de refresco antes de poder pedir /users/me.
      const renovado = await refreshSession()
      if (cancelado) return
      if (!renovado) {
        setEstado('anonimo')
        return
      }
      try {
        const actual = await authService.fetchCurrentUser()
        if (cancelado) return
        setUsuario(actual)
        setEstado('autenticado')
      } catch {
        if (!cancelado) setEstado('anonimo')
      }
    }
    void restaurar()
    return () => {
      cancelado = true
    }
  }, [])

  const iniciarSesion = useCallback(async (email: string, password: string) => {
    await authService.login(email, password)
    setUsuario(await authService.fetchCurrentUser())
    setEstado('autenticado')
  }, [])

  const registrarse = useCallback(
    async (email: string, password: string, fullName: string) => {
      await authService.register(email, password, fullName)
      // Se inicia sesión de una: pedirle a alguien que acaba de crear la cuenta
      // que vuelva a escribir sus credenciales no aporta nada.
      await authService.login(email, password)
      setUsuario(await authService.fetchCurrentUser())
      setEstado('autenticado')
    },
    [],
  )

  const cerrarSesion = useCallback(async () => {
    await authService.logout()
    setUsuario(null)
    setEstado('anonimo')
  }, [])

  const valor = useMemo<AuthContextValue>(
    () => ({ estado, usuario, iniciarSesion, registrarse, cerrarSesion }),
    [estado, usuario, iniciarSesion, registrarse, cerrarSesion],
  )

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>
}
