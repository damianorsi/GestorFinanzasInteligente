import { NavLink, Outlet } from 'react-router-dom'

import { useAuth } from '@/features/auth/useAuth'

const SECCIONES = [
  { to: '/dashboard', etiqueta: 'Resumen' },
  { to: '/transactions', etiqueta: 'Movimientos' },
  { to: '/categories', etiqueta: 'Categorías' },
  { to: '/budgets', etiqueta: 'Presupuestos' },
  { to: '/reports', etiqueta: 'Reportes' },
  { to: '/recurring', etiqueta: 'Recurrentes' },
  { to: '/chat', etiqueta: 'Asistente' },
]

export function AppLayout() {
  const { usuario, cerrarSesion } = useAuth()

  return (
    <div className="layout">
      <header className="layout__header">
        <span className="layout__marca">Finanzas</span>
        {/* `aria-label` porque hay más de una navegación posible en la página. */}
        <nav className="layout__nav" aria-label="Secciones">
          {SECCIONES.map((seccion) => (
            <NavLink
              key={seccion.to}
              to={seccion.to}
              className={({ isActive }) =>
                isActive ? 'layout__link layout__link--activo' : 'layout__link'
              }
            >
              {seccion.etiqueta}
            </NavLink>
          ))}
        </nav>
        <div className="layout__sesion">
          {usuario && <span className="layout__usuario">{usuario.full_name}</span>}
          <button
            type="button"
            className="boton boton--secundario"
            onClick={() => void cerrarSesion()}
          >
            Cerrar sesión
          </button>
        </div>
      </header>

      <main className="layout__main">
        <Outlet />
      </main>
    </div>
  )
}
