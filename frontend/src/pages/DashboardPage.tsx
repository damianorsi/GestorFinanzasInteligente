import { useQuery } from '@tanstack/react-query'

import { Cargando, ErrorVisible } from '@/components/Feedback'
import { useAuth } from '@/features/auth/useAuth'
import { request } from '@/services/api'
import type { PeriodSummary } from '@/types/api'
import { formatDate, formatMoney, isNegative } from '@/utils/format'

export function DashboardPage() {
  const { usuario } = useAuth()

  const resumen = useQuery({
    queryKey: ['reports', 'summary'],
    queryFn: () => request<PeriodSummary>('/reports/summary'),
  })

  return (
    <section className="pagina">
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
    </section>
  )
}
