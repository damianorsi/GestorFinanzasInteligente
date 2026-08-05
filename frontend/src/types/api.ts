/**
 * Tipos del contrato de la API.
 *
 * Los montos son `string` y no `number` a propósito: un número JSON lo parsea
 * el navegador como float de doble precisión y 1234.56 deja de ser exactamente
 * 1234.56. Se formatean para mostrar y nunca se opera aritméticamente con
 * ellos en el frontend.
 */

export type TransactionType = 'INCOME' | 'EXPENSE'
export type BudgetStatus = 'OK' | 'WARNING' | 'EXCEEDED'

/** Contrato de error: `code` estable en inglés, `message` en español. */
export interface ApiErrorBody {
  code: string
  message: string
  details: { field: string; reason: string }[]
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface User {
  id: number
  email: string
  full_name: string
  is_active: boolean
}

export interface Category {
  id: number
  name: string
  type: TransactionType
  color: string | null
  is_default: boolean
}

export interface Transaction {
  id: number
  type: TransactionType
  amount: string
  currency: string
  occurred_on: string
  category_id: number
  description: string
  is_recurring: boolean
}

export interface Paginated<T> {
  entries: T[]
  offset: number
  limit: number
  totalCount: number
}

export interface PeriodSummary {
  currency: string
  date_from: string
  date_to: string
  income: string
  expense: string
  balance: string
}

export interface CategoryTotal {
  category_id: number
  category_name: string
  type: TransactionType
  total: string
  percentage: string
  transaction_count: number
}

export interface CategoryBreakdown {
  currency: string
  date_from: string
  date_to: string
  entries: CategoryTotal[]
}

export interface MonthlyTotal {
  period: string
  income: string
  expense: string
  balance: string
}

export interface MonthlyTrend {
  currency: string
  entries: MonthlyTotal[]
}

export interface Budget {
  id: number
  category_id: number
  period_month: string
  amount: string
  currency: string
}

export interface BudgetProgressEntry {
  budget_id: number
  category_id: number
  category_name: string
  budgeted: string
  spent: string
  /** Negativo si se excedió el tope. */
  remaining: string
  percentage: string
  status: BudgetStatus
}

export interface UnbudgetedSpending {
  category_id: number
  category_name: string
  spent: string
}

export interface BudgetProgress {
  currency: string
  period_month: string
  entries: BudgetProgressEntry[]
  unbudgeted: UnbudgetedSpending[]
  exceeded_count: number
}
