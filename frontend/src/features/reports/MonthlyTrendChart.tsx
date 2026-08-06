import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { MonthlyTotal } from '@/types/api'
import { formatCompact, formatMoney, formatPeriod } from '@/utils/format'

const COLOR_INGRESOS = '#16794a'
const COLOR_GASTOS = '#b3261e'

interface Props {
  entradas: MonthlyTotal[]
  moneda: string
}

export function MonthlyTrendChart({ entradas, moneda }: Props) {
  const datos = entradas.map((entrada) => ({
    periodo: entrada.period,
    Ingresos: Number(entrada.income),
    Gastos: Number(entrada.expense),
  }))

  return (
    <figure className="grafico">
      <figcaption>Ingresos y gastos por mes</figcaption>

      <div aria-hidden="true" className="grafico__lienzo">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={datos} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="periodo"
              tickFormatter={(valor: string) => valor.slice(5)}
              tick={{ fontSize: 12 }}
            />
            {/* Eje compacto y angosto: con los montos completos, el eje se
                llevaba un tercio del ancho en un celular. El valor exacto sigue
                estando en el tooltip y en la tabla equivalente. */}
            <YAxis width={44} tick={{ fontSize: 12 }} tickFormatter={formatCompact} />
            <Tooltip formatter={(valor: number) => formatMoney(String(valor), moneda)} />
            <Legend wrapperStyle={{ fontSize: '0.8rem' }} />
            <Bar dataKey="Ingresos" fill={COLOR_INGRESOS} />
            <Bar dataKey="Gastos" fill={COLOR_GASTOS} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Cuatro columnas de montos no entran en 375px. Scrollean acá adentro:
          la página nunca desborda en horizontal. */}
      <div className="tabla__scroll">
        <table className="tabla tabla--compacta">
          <caption className="visualmente-oculto">Ingresos y gastos por mes, detalle</caption>
          <thead>
            <tr>
              <th scope="col">Mes</th>
              <th scope="col" className="tabla__numero">
                Ingresos
              </th>
              <th scope="col" className="tabla__numero">
                Gastos
              </th>
              <th scope="col" className="tabla__numero">
                Balance
              </th>
            </tr>
          </thead>
          <tbody>
            {entradas.map((entrada) => (
              <tr key={entrada.period}>
                <th scope="row">{formatPeriod(entrada.period)}</th>
                <td className="tabla__numero">{formatMoney(entrada.income, moneda)}</td>
                <td className="tabla__numero">{formatMoney(entrada.expense, moneda)}</td>
                <td className="tabla__numero">{formatMoney(entrada.balance, moneda)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  )
}
