import { Link } from 'react-router-dom'

import { Cargando, ErrorVisible, SinDatos } from '@/components/Feedback'
import { useAuth } from '@/features/auth/useAuth'
import { useAvanceDePresupuestos } from '@/features/budgets/api'

import {
  CategoryPieChartLazy,
  MonthlyTrendChartLazy,
} from '@/features/reports/LazyCharts'
import {
  useDesglosePorCategoria,
  useResumen,
  useTendenciaMensual,
} from '@/features/reports/api'
import { useProximosVencimientos } from '@/features/recurring/api'
import { GoalsSummary } from '@/features/savings/GoalsSummary'
import { formatDate, formatMoney, isNegative } from '@/utils/format'
import { periodoActual } from '@/utils/periods'

/** El dashboard resume: la lista completa está en la pantalla de recurrentes. */
const MAXIMO_EN_EL_DASHBOARD = 5

export function DashboardPage() {
  const { usuario } = useAuth()
  const resumen = useResumen()
  const desglose = useDesglosePorCategoria()
  const tendencia = useTendenciaMensual(6)
  const avance = useAvanceDePresupuestos(periodoActual())
  const vencimientos = useProximosVencimientos(30)

  const gastos = (desglose.data?.entries ?? []).filter((e) => e.type === 'EXPENSE')

  return (
    <section className="pagina pagina--con-fab">
      <h1>Hola, {usuario?.full_name}</h1>

      {resumen.isPending && <Cargando mensaje="Cargando tu resumen…" />}

      {resumen.isError && (
        <ErrorVisible
          mensaje="No se pudo cargar el resumen del mes."
          onReintentar={() => void resumen.refetch()}
        />
      )}

      {resumen.isSuccess && (
        <>
          <p className="pagina__subtitulo">
            Del {formatDate(resumen.data.date_from)} al {formatDate(resumen.data.date_to)}
          </p>
          <div className="tarjetas">
            <article className="tarjeta">
              <h2>Ingresos</h2>
              <p className="tarjeta__monto tarjeta__monto--positivo">
                {formatMoney(resumen.data.income, resumen.data.currency)}
              </p>
            </article>
            <article className="tarjeta">
              <h2>Gastos</h2>
              <p className="tarjeta__monto tarjeta__monto--negativo">
                {formatMoney(resumen.data.expense, resumen.data.currency)}
              </p>
            </article>
            <article className="tarjeta">
              <h2>Balance</h2>
              <p
                className={
                  isNegative(resumen.data.balance)
                    ? 'tarjeta__monto tarjeta__monto--negativo'
                    : 'tarjeta__monto tarjeta__monto--positivo'
                }
              >
                {formatMoney(resumen.data.balance, resumen.data.currency)}
              </p>
            </article>
          </div>
        </>
      )}

      {avance.isSuccess && avance.data.exceeded_count > 0 && (
        <p className="aviso aviso--alerta" role="status">
          Te pasaste del tope en {avance.data.exceeded_count}{' '}
          {avance.data.exceeded_count === 1 ? 'categoría' : 'categorías'}.{' '}
          <Link to="/budgets">Ver presupuestos</Link>
        </p>
      )}

      {desglose.isSuccess && gastos.length === 0 && (
        <SinDatos
          titulo="Todavía no registraste gastos este mes"
          detalle="Cargá tu primer movimiento para ver el desglose."
          accion={
            <Link className="boton boton--primario" to="/transactions">
              Registrar un movimiento
            </Link>
          }
        />
      )}

      {desglose.isSuccess && gastos.length > 0 && (
        <CategoryPieChartLazy
          entradas={gastos}
          moneda={desglose.data.currency}
          titulo="Gastos por categoría"
        />
      )}

      {vencimientos.isSuccess && vencimientos.data.entries.length > 0 && (
        <div className="grupo">
          <h2>Próximos vencimientos</h2>
          {/*
            Se aclara que son proyecciones porque no están en el balance de
            arriba: sin la aclaración, la diferencia parece un error de cuentas.
          */}
          <p className="pagina__subtitulo">
            Proyección de lo que las reglas van a generar hasta el{' '}
            {formatDate(vencimientos.data.date_to)}. Todavía no forman parte del balance.
          </p>
          <ul className="lista">
            {vencimientos.data.entries.slice(0, MAXIMO_EN_EL_DASHBOARD).map((entrada) => (
              <li key={`${entrada.rule_id}-${entrada.due_on}`} className="lista__item">
                <span className="lista__nombre">
                  {formatDate(entrada.due_on)} · {entrada.description || 'sin descripción'}
                </span>
                <span
                  className={
                    entrada.type === 'INCOME'
                      ? 'tabla__numero tabla__numero--positivo'
                      : 'tabla__numero tabla__numero--negativo'
                  }
                >
                  {formatMoney(entrada.amount, entrada.currency)}
                </span>
              </li>
            ))}
          </ul>
          <p className="pagina__subtitulo">
            Total proyectado: {formatMoney(vencimientos.data.projected_expense, vencimientos.data.currency)}{' '}
            en gastos. <Link to="/recurring">Ver las reglas</Link>
          </p>
        </div>
      )}

      <GoalsSummary />

      {tendencia.isSuccess && (
        <MonthlyTrendChartLazy
          entradas={tendencia.data.entries}
          moneda={tendencia.data.currency}
        />
      )}

      {/*
        Atajo al asistente desde el resumen, que es donde se mira el mes y
        surgen las preguntas. En el celular queda solo el ícono; el texto
        volvería a comer el ancho que se acaba de liberar.
      */}
      <Link to="/chat" className="fab-asistente" aria-label="Abrir el asistente">
        <span className="fab-asistente__icono" aria-hidden="true">
          💬
        </span>
        <span className="fab-asistente__texto">Asistente</span>
      </Link>
    </section>
  )
}
