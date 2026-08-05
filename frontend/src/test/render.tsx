import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { RenderResult } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'

import { AuthProvider } from '@/features/auth/AuthProvider'

/**
 * Renderiza con los mismos providers que la aplicación real.
 *
 * El `QueryClient` se crea por test y sin reintentos: compartirlo dejaría
 * cachés de un test filtrándose al siguiente, y los reintentos harían que un
 * test de error tarde segundos en fallar.
 */
export function renderConProviders(
  ui: ReactNode,
  { ruta = '/' }: { ruta?: string } = {},
): RenderResult {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter
        initialEntries={[ruta]}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <AuthProvider>{ui}</AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}
