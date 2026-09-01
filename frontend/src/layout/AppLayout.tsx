import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

import { useAlertasSinLeer } from '@/features/alerts/api'
import { useAuth } from '@/features/auth/useAuth'

const SECCIONES = [
  { to: '/dashboard', etiqueta: 'Resumen' },
  { to: '/transactions', etiqueta: 'Movimientos' },
  { to: '/categories', etiqueta: 'Categorías' },
  { to: '/budgets', etiqueta: 'Presupuestos' },
  { to: '/alerts', etiqueta: 'Alertas' },
  { to: '/savings-goals', etiqueta: 'Metas' },
  { to: '/reports', etiqueta: 'Reportes' },
  { to: '/recurring', etiqueta: 'Recurrentes' },
  { to: '/chat', etiqueta: 'Asistente' },
]

const ID_DEL_MENU = 'menu-principal'

export function AppLayout() {
  const { usuario, cerrarSesion } = useAuth()
  const sinLeer = useAlertasSinLeer()
  const [abierto, setAbierto] = useState(false)
  const { pathname } = useLocation()
  const botonRef = useRef<HTMLButtonElement>(null)

  // Al navegar se cierra solo. Sin esto, tocar una sección en el celular deja
  // el panel tapando la pantalla que se acaba de abrir.
  useEffect(() => {
    setAbierto(false)
  }, [pathname])

  // Escape cierra y devuelve el foco al botón: quien navega con teclado tiene
  // que poder salir sin recorrer todo el menú.
  useEffect(() => {
    if (!abierto) return
    const alPresionar = (evento: KeyboardEvent) => {
      if (evento.key === 'Escape') {
        setAbierto(false)
        botonRef.current?.focus()
      }
    }
    document.addEventListener('keydown', alPresionar)
    return () => document.removeEventListener('keydown', alPresionar)
  }, [abierto])

  return (
    <div className="layout">
      <header className="layout__header">
        <button
          ref={botonRef}
          type="button"
          className="layout__hamburguesa"
          aria-expanded={abierto}
          aria-controls={ID_DEL_MENU}
          aria-label={abierto ? 'Cerrar menú' : 'Abrir menú'}
          onClick={() => setAbierto((previo) => !previo)}
        >
          <span className="layout__hamburguesa-icono" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
        </button>

        <span className="layout__marca">Finanzas</span>

        {/*
          Un solo DOM para las dos disposiciones: en escritorio es una barra
          horizontal y en celular un panel vertical. Duplicar el markup
          significaría duplicar también los links y el botón de salir, y que
          un lector de pantalla los anuncie dos veces.
        */}
        <nav
          id={ID_DEL_MENU}
          className={`layout__nav ${abierto ? 'layout__nav--abierto' : ''}`.trim()}
          aria-label="Secciones"
        >
          <div className="layout__links">
            {SECCIONES.map((seccion) => (
              <NavLink
                key={seccion.to}
                to={seccion.to}
                className={({ isActive }) =>
                  isActive ? 'layout__link layout__link--activo' : 'layout__link'
                }
              >
                {seccion.etiqueta}
                {/*
                  El contador es lo que hace que una alerta te encuentre a vos
                  en vez de esperar a que la vayas a buscar. Sin esto, la
                  feature sería tan pasiva como la pantalla de presupuestos.

                  El número va `aria-hidden` y al lado se pone el texto
                  completo: un lector de pantalla leyendo "Alertas 2" no dice
                  qué son esos dos.
                */}
                {seccion.to === '/alerts' && sinLeer > 0 && (
                  <>
                    <span className="layout__contador" aria-hidden="true">
                      {sinLeer}
                    </span>
                    <span className="visualmente-oculto">{sinLeer} sin leer</span>
                  </>
                )}
              </NavLink>
            ))}
          </div>

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
        </nav>
      </header>

      {/* Tocar fuera del panel también lo cierra. `aria-hidden` porque el
          botón de la hamburguesa ya expone la acción de cerrar. */}
      {abierto && (
        <div
          className="layout__telon"
          aria-hidden="true"
          onClick={() => setAbierto(false)}
        />
      )}

      <main className="layout__main">
        <Outlet />
      </main>
    </div>
  )
}
