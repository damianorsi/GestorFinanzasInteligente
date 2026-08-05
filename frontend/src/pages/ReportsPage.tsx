import { useState } from 'react'

import { Cargando, ErrorVisible, SinDatos } from '@/components/Feedback'
import { FormField } from '@/components/FormField'
import { SelectField } from '@/components/SelectField'

import {
  CategoryPieChartLazy,
  MonthlyTrendChartLazy,
} from '@/features/reports/LazyCharts'
import {
  useDesglosePorCategoria,
  useResumen,
  useTendenciaMensual,
} from '@/features/reports/api'
import { formatMoney, isNegative } from '@/utils/format'
import { periodoActual, primerDiaDe, ultimoDiaDe } from '@/utils/periods'

const MESES_DISPONIBLES = [3, 6, 12, 24]

export function ReportsPage() {
  const mesEnCurso = periodoActual()
  const [desde, setDesde] = useState(primerDiaDe(mesEnCurso))
  const [hasta, setHasta] = useState(ultimoDiaDe(mesEnCurso))
  const [meses, setMeses] = useState(6)

  const periodo = { date_from: desde, date_to: hasta }
  const resumen = useResumen(periodo)
  const desglose = useDesglosePorCategoria(periodo)
  const tendencia = useTendenciaMensual(meses)

  const gastos = (desglose.data?.entries ?? []).filter((e) => e.type === 'EXPENSE')
  const ingresos = (desglose.data?.entries ?? []).filter((e) => e.type === 'INCOME')

  return (
    <section className="pagina">
      <h1>Reportes</h1>

      <section className="filtros" aria-label="Período">
        <div className="filtros__campos">
          <FormField
            id="reporte-desde"
            label="Desde"
            type="date"
            value={desde}
            onChange={(evento) => setDesde(evento.target.value)}
          />
          <FormField
            id="reporte-hasta"
            label="Hasta"
            type="date"
            value={hasta}
            onChange={(evento) => setHasta(evento.target.value)}
          />
        </div>
      </section>

      {resumen.isError && (
        <ErrorVisible
          mensaje="No se pudo cargar el resumen."
          onReintentar={() => void resumen.refetch()}
        />
      )}

      {resumen.isSuccess && (
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
      )}

      {desglose.isPending && <Cargando mensaje="Cargando el desglose…" />}

      {desglose.isSuccess && desglose.data.entries.length === 0 && (
        <SinDatos
          titulo="No hay movimientos en el período"
          detalle="Ampliá el rango de fechas o registrá movimientos."
        />
      )}

      {desglose.isSuccess && gastos.length > 0 && (
        <CategoryPieChartLazy
          entradas={gastos}
          moneda={desglose.data.currency}
          titulo="Gastos por categoría"
        />
      )}

      {desglose.isSuccess && ingresos.length > 0 && (
        <CategoryPieChartLazy
          entradas={ingresos}
          moneda={desglose.data.currency}
          titulo="Ingresos por categoría"
        />
      )}

      <div className="grupo">
        <SelectField
          id="reporte-meses"
          label="Meses en la tendencia"
          value={meses}
          onChange={(evento) => setMeses(Number(evento.target.value))}
        >
          {MESES_DISPONIBLES.map((cantidad) => (
            <option key={cantidad} value={cantidad}>
              Últimos {cantidad} meses
            </option>
          ))}
        </SelectField>
      </div>

      {tendencia.isPending && <Cargando mensaje="Cargando la tendencia…" />}

      {tendencia.isError && (
        <ErrorVisible
          mensaje="No se pudo cargar la tendencia mensual."
          onReintentar={() => void tendencia.refetch()}
        />
      )}

      {tendencia.isSuccess && (
        <MonthlyTrendChartLazy
          entradas={tendencia.data.entries}
          moneda={tendencia.data.currency}
        />
      )}
    </section>
  )
}
