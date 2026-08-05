import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { Cargando } from '@/components/Feedback'
import { useAuth } from '@/features/auth/useAuth'

/**
 * Deja pasar solo a quien tiene sesión.
 *
 * Mientras el estado es `cargando` no decide nada: al abrir la aplicación hay
 * que canjear el refresh token antes de saber si hay sesión, y redirigir en ese
 * instante expulsaría al login a alguien que sí está autenticado cada vez que
 * refresca la página.
 */
export function RutaPrivada() {
  const { estado } = useAuth()
  const ubicacion = useLocation()

  if (estado === 'cargando') return <Cargando mensaje="Verificando tu sesión…" />
  if (estado === 'anonimo') {
    // Se guarda a dónde quería ir para volver ahí después del login.
    return <Navigate to="/login" replace state={{ desde: ubicacion.pathname }} />
  }
  return <Outlet />
}

/** Impide volver al login o al registro con la sesión ya iniciada. */
export function RutaPublica() {
  const { estado } = useAuth()

  if (estado === 'cargando') return <Cargando mensaje="Verificando tu sesión…" />
  if (estado === 'autenticado') return <Navigate to="/dashboard" replace />
  return <Outlet />
}
