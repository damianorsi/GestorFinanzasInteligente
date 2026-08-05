import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App'
import { AuthProvider } from './features/auth/AuthProvider'
import { ApiError } from './services/api'
import './styles/global.css'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Un 4xx no se arregla reintentando: el pedido está mal o no hay
      // permiso. Reintentar solo demora el error y multiplica la carga.
      retry: (intentos, error) => {
        if (error instanceof ApiError && error.status < 500) return false
        return intentos < 2
      },
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
})

const contenedor = document.getElementById('root')

if (!contenedor) {
  throw new Error('No se encontró el elemento #root en index.html')
}

createRoot(contenedor).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {/* Se opta por los flags de v7 desde ya: silencian los avisos de
          deprecación y evitan que la migración sea un cambio de comportamiento
          sorpresivo más adelante. */}
      <BrowserRouter
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
