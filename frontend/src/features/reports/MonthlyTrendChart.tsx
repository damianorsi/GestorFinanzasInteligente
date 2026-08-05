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
import { formatMoney, formatPeriod } from '@/utils/format'

const ALTO = 300
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

      <div aria-hidden="true" style={{ width: '100%', height: ALTO }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={datos}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="periodo" tickFormatter={(valor: string) => valor.slice(5)} />
            <YAxis width={80} />
            <Tooltip formatter={(valor: number) => formatMoney(String(valor), moneda)} />
            <Legend />
            <Bar dataKey="Ingresos" fill={COLOR_INGRESOS} />
            <Bar dataKey="Gastos" fill={COLOR_GASTOS} />
          </BarChart>
        </ResponsiveContainer>
      </div>

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
    </figure>
  )
}
