import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'

import type { CategoryTotal } from '@/types/api'
import { formatMoney, formatPercent } from '@/utils/format'

/** Paleta con contraste suficiente entre porciones contiguas. */
const COLORES = [
  '#2f6fb5',
  '#d1603d',
  '#16794a',
  '#7a5ba6',
  '#a25b00',
  '#3f8fa6',
  '#b3446c',
  '#6b7280',
]

const ALTO = 280

interface Props {
  entradas: CategoryTotal[]
  moneda: string
  titulo: string
}

export function CategoryPieChart({ entradas, moneda, titulo }: Props) {
  const datos = entradas.map((entrada) => ({
    nombre: entrada.category_name,
    valor: Number(entrada.total),
    porcentaje: entrada.percentage,
    total: entrada.total,
  }))

  return (
    <figure className="grafico">
      <figcaption>{titulo}</figcaption>

      {/* El SVG se oculta a la tecnología asistiva y se ofrece la misma
          información como tabla: un gráfico es literalmente invisible para un
          lector de pantalla. */}
      <div aria-hidden="true" style={{ width: '100%', height: ALTO }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={datos} dataKey="valor" nameKey="nombre" outerRadius="75%" label={false}>
              {datos.map((entrada, indice) => (
                <Cell key={entrada.nombre} fill={COLORES[indice % COLORES.length]} />
              ))}
            </Pie>
            <Tooltip formatter={(valor: number) => formatMoney(String(valor), moneda)} />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </div>

      <table className="tabla tabla--compacta">
        <caption className="visualmente-oculto">{titulo}, detalle</caption>
        <thead>
          <tr>
            <th scope="col">Categoría</th>
            <th scope="col" className="tabla__numero">
              Total
            </th>
            <th scope="col" className="tabla__numero">
              Porcentaje
            </th>
          </tr>
        </thead>
        <tbody>
          {datos.map((entrada) => (
            <tr key={entrada.nombre}>
              <th scope="row">{entrada.nombre}</th>
              <td className="tabla__numero">{formatMoney(entrada.total, moneda)}</td>
              <td className="tabla__numero">{formatPercent(entrada.porcentaje)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  )
}
