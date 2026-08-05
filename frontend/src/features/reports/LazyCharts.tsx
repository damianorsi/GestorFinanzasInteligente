import { Suspense, lazy } from 'react'
import type { ComponentProps } from 'react'

import { Cargando } from '@/components/Feedback'

import type { CategoryPieChart as CategoryPieChartTipo } from './CategoryPieChart'
import type { MonthlyTrendChart as MonthlyTrendChartTipo } from './MonthlyTrendChart'

/**
 * Los gráficos se cargan aparte del bundle principal.
 *
 * Recharts pesa más que todo el resto de la aplicación junta. Cargándolo con
 * el resto, alguien que entra a ver sus movimientos descarga la librería de
 * gráficos sin necesitarla. Así las tarjetas y las tablas aparecen enseguida y
 * el gráfico llega unos milisegundos después.
 */
const PieChart = lazy(async () => ({
  default: (await import('./CategoryPieChart')).CategoryPieChart,
}))

const TrendChart = lazy(async () => ({
  default: (await import('./MonthlyTrendChart')).MonthlyTrendChart,
}))

export function CategoryPieChartLazy(props: ComponentProps<typeof CategoryPieChartTipo>) {
  return (
    <Suspense fallback={<Cargando mensaje="Cargando el gráfico…" />}>
      <PieChart {...props} />
    </Suspense>
  )
}

export function MonthlyTrendChartLazy(props: ComponentProps<typeof MonthlyTrendChartTipo>) {
  return (
    <Suspense fallback={<Cargando mensaje="Cargando el gráfico…" />}>
      <TrendChart {...props} />
    </Suspense>
  )
}
