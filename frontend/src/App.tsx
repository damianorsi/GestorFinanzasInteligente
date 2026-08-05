import { useEffect, useState } from 'react'

export interface HealthPayload {
  status: string
  environment: string
  timezone: string
  default_currency: string
  database: string
  scheduler: string
}

type EstadoConexion = 'cargando' | 'ok' | 'degradado' | 'sin-conexion'

const ETIQUETAS: Record<EstadoConexion, string> = {
  cargando: 'Verificando conexión con el backend…',
  ok: 'Backend conectado',
  degradado: 'Backend accesible, base de datos con problemas',
  'sin-conexion': 'No se pudo contactar al backend',
}

export function App() {
  const [estado, setEstado] = useState<EstadoConexion>('cargando')
  const [detalle, setDetalle] = useState<HealthPayload | null>(null)

  useEffect(() => {
    let cancelado = false

    const consultar = async () => {
      try {
        const respuesta = await fetch('/health')
        const cuerpo = (await respuesta.json()) as HealthPayload
        if (cancelado) return
        setDetalle(cuerpo)
        setEstado(respuesta.ok ? 'ok' : 'degradado')
      } catch {
        if (!cancelado) setEstado('sin-conexion')
      }
    }

    void consultar()
    return () => {
      cancelado = true
    }
  }, [])

  return (
    <main className="contenedor">
      <h1>Gestor Inteligente de Finanzas Personales</h1>
      <p className="subtitulo">Fase 1 — scaffolding del proyecto</p>

      <section className="tarjeta" aria-live="polite">
        <h2>Estado del sistema</h2>
        <p data-testid="estado-conexion" className={`estado estado--${estado}`}>
          {ETIQUETAS[estado]}
        </p>

        {detalle && (
          <dl className="detalle">
            <dt>Entorno</dt>
            <dd>{detalle.environment}</dd>
            <dt>Base de datos</dt>
            <dd>{detalle.database}</dd>
            <dt>Zona horaria</dt>
            <dd>{detalle.timezone}</dd>
            <dt>Moneda</dt>
            <dd>{detalle.default_currency}</dd>
            <dt>Scheduler</dt>
            <dd>{detalle.scheduler}</dd>
          </dl>
        )}
      </section>
    </main>
  )
}

export default App
