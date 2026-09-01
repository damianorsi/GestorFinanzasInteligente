import { useState } from 'react'
import { Link } from 'react-router-dom'

import { Cargando, ErrorVisible, SinDatos } from '@/components/Feedback'
import { useAlertas, useMarcarAlertaLeida } from '@/features/alerts/api'
import { useCategorias } from '@/features/categories/api'
import type { AlertStatus, AlertType, BudgetAlert } from '@/types/api'
import { formatPercent, formatPeriod } from '@/utils/format'

const FILTROS: { valor: AlertStatus | 'todas'; etiqueta: string }[] = [
  { valor: 'OPEN', etiqueta: 'Sin leer' },
  { valor: 'todas', etiqueta: 'Todas' },
  { valor: 'RESOLVED', etiqueta: 'Resueltas' },
]

/**
 * Etiqueta corta del tipo.
 *
 * No repite el texto del mensaje: si dijeran lo mismo, la etiqueta sería una
 * línea de ruido en vez de un rótulo que se lee de un vistazo.
 */
const ETIQUETA_DE_TIPO: Record<AlertType, string> = {
  BUDGET_EXCEEDED: 'Excedido',
  BUDGET_AT_RISK: 'En riesgo',
  UNBUDGETED_SPENDING: 'Sin tope',
}

export function AlertsPage() {
  const [filtro, setFiltro] = useState<AlertStatus | 'todas'>('OPEN')
  const alertas = useAlertas(filtro === 'todas' ? undefined : filtro)
  const categorias = useCategorias()
  const marcarLeida = useMarcarAlertaLeida()

  const nombreDeCategoria = (id: number) =>
    (categorias.data ?? []).find((categoria) => categoria.id === id)?.name

  return (
    <section className="pagina">
      <div className="pagina__encabezado">
        <div>
          <h1>Alertas</h1>
          <p className="pagina__subtitulo">
            Desvíos que detectó la revisión diaria de tus presupuestos.
          </p>
        </div>
      </div>

      {/* `radiogroup` y no botones sueltos: son opciones excluyentes de un
          mismo filtro, y así se recorren con las flechas del teclado. */}
      <div className="filtro-de-alertas" role="radiogroup" aria-label="Filtrar alertas">
        {FILTROS.map((opcion) => (
          <button
            key={opcion.valor}
            type="button"
            role="radio"
            aria-checked={filtro === opcion.valor}
            className={
              filtro === opcion.valor
                ? 'filtro-de-alertas__opcion filtro-de-alertas__opcion--activa'
                : 'filtro-de-alertas__opcion'
            }
            onClick={() => setFiltro(opcion.valor)}
          >
            {opcion.etiqueta}
          </button>
        ))}
      </div>

      {alertas.isPending && <Cargando mensaje="Cargando tus alertas…" />}

      {alertas.isError && (
        <ErrorVisible
          mensaje="No se pudieron cargar las alertas."
          onReintentar={() => void alertas.refetch()}
        />
      )}

      {alertas.isSuccess && alertas.data.length === 0 && (
        <SinDatos
          titulo={filtro === 'OPEN' ? 'No tenés alertas sin leer' : 'No hay alertas'}
          detalle="Se revisan todos los días. Si un presupuesto se desvía, va a aparecer acá."
          accion={
            <Link className="boton boton--secundario" to="/budgets">
              Ver presupuestos
            </Link>
          }
        />
      )}

      {alertas.isSuccess && alertas.data.length > 0 && (
        <ul className="alertas">
          {alertas.data.map((alerta) => (
            <Alerta
              key={alerta.id}
              alerta={alerta}
              categoria={nombreDeCategoria(alerta.category_id)}
              enProceso={marcarLeida.isPending}
              onLeer={() => void marcarLeida.mutateAsync(alerta.id)}
            />
          ))}
        </ul>
      )}
    </section>
  )
}

function Alerta({
  alerta,
  categoria,
  enProceso,
  onLeer,
}: {
  alerta: BudgetAlert
  categoria: string | undefined
  enProceso: boolean
  onLeer: () => void
}) {
  const severa = alerta.type === 'BUDGET_EXCEEDED'

  return (
    <li
      className={`alerta ${severa ? 'alerta--severa' : ''} ${
        alerta.status === 'RESOLVED' ? 'alerta--resuelta' : ''
      }`.trim()}
    >
      <div className="alerta__cabecera">
        <span className="etiqueta">{ETIQUETA_DE_TIPO[alerta.type]}</span>
        <span className="alerta__periodo">{formatPeriod(alerta.period_month)}</span>
        {alerta.status === 'OPEN' && <span className="alerta__punto" aria-label="Sin leer" />}
        {alerta.status === 'RESOLVED' && <span className="etiqueta">resuelta</span>}
      </div>

      <p className="alerta__mensaje">{alerta.message}</p>

      {alerta.projected_percentage && (
        <p className="alerta__proyeccion">
          Proyección a fin de mes: {formatPercent(alerta.projected_percentage)} del tope.{' '}
          <span className="alerta__aclaracion">
            Es tu ritmo actual llevado a fin de mes, no una predicción.
          </span>
        </p>
      )}

      {alerta.recommendation && (
        <div className="alerta__recomendacion">
          <p className="alerta__recomendacion-titulo">Qué podés hacer</p>
          <p className="alerta__recomendacion-texto">{alerta.recommendation}</p>
        </div>
      )}

      <div className="alerta__acciones">
        {categoria && (
          <Link className="boton boton--secundario boton--chico" to="/budgets">
            Ver {categoria}
          </Link>
        )}
        {alerta.status === 'OPEN' && (
          <button
            type="button"
            className="boton boton--secundario boton--chico"
            onClick={onLeer}
            disabled={enProceso}
          >
            Marcar como leída
          </button>
        )}
      </div>
    </li>
  )
}
