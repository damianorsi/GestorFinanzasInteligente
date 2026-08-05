import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="auth">
      <div className="auth__form">
        <h1>Página no encontrada</h1>
        <p>La dirección a la que entraste no existe.</p>
        <Link className="boton boton--primario" to="/dashboard">
          Ir al resumen
        </Link>
      </div>
    </div>
  )
}
