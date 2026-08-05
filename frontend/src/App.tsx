import { Navigate, Route, Routes } from 'react-router-dom'

import { AppLayout } from '@/layout/AppLayout'
import { DashboardPage } from '@/pages/DashboardPage'
import { EnConstruccionPage } from '@/pages/EnConstruccionPage'
import { LoginPage } from '@/pages/LoginPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { RegisterPage } from '@/pages/RegisterPage'
import { RutaPrivada, RutaPublica } from '@/routes/guards'

export function App() {
  return (
    <Routes>
      {/* Públicas: si ya hay sesión, redirigen al resumen. */}
      <Route element={<RutaPublica />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      {/* Privadas: el guard resuelve la sesión antes de decidir. */}
      <Route element={<RutaPrivada />}>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route
            path="/transactions"
            element={<EnConstruccionPage titulo="Movimientos" fase="fase 9" />}
          />
          <Route
            path="/categories"
            element={<EnConstruccionPage titulo="Categorías" fase="fase 9" />}
          />
          <Route
            path="/budgets"
            element={<EnConstruccionPage titulo="Presupuestos" fase="fase 9" />}
          />
          <Route
            path="/reports"
            element={<EnConstruccionPage titulo="Reportes" fase="fase 9" />}
          />
          <Route
            path="/recurring"
            element={<EnConstruccionPage titulo="Movimientos recurrentes" fase="fase 13" />}
          />
          <Route
            path="/chat"
            element={<EnConstruccionPage titulo="Asistente" fase="fase 11" />}
          />
        </Route>
      </Route>

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

export default App
