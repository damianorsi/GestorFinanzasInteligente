import { Navigate, Route, Routes } from 'react-router-dom'

import { AppLayout } from '@/layout/AppLayout'
import { AlertsPage } from '@/pages/AlertsPage'
import { BudgetsPage } from '@/pages/BudgetsPage'
import { CategoriesPage } from '@/pages/CategoriesPage'
import { ChatPage } from '@/pages/ChatPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { LoginPage } from '@/pages/LoginPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { RecurringPage } from '@/pages/RecurringPage'
import { RegisterPage } from '@/pages/RegisterPage'
import { ReportsPage } from '@/pages/ReportsPage'
import { SavingsGoalsPage } from '@/pages/SavingsGoalsPage'
import { TransactionsPage } from '@/pages/TransactionsPage'
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
          <Route path="/transactions" element={<TransactionsPage />} />
          <Route path="/categories" element={<CategoriesPage />} />
          <Route path="/budgets" element={<BudgetsPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/savings-goals" element={<SavingsGoalsPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/recurring" element={<RecurringPage />} />
          <Route path="/chat" element={<ChatPage />} />
        </Route>
      </Route>

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

export default App
