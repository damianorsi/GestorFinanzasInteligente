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
export type ChatRole = 'USER' | 'ASSISTANT'

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

export interface ChatMessage {
  role: ChatRole
  content: string
  /** ISO con hora, en UTC: es un timestamp de auditoría, no una fecha de negocio. */
  created_at: string
}

export interface ChatAnswer {
  conversation_id: string
  content: string
  /**
   * `true` cuando la respuesta es de fallback: el proveedor falló o el agente
   * no convergió. Sirve para ofrecer reintentar en vez de tomarla como un "no
   * sé" real del asistente.
   */
  degraded: boolean
}

export type RecurrenceFrequency = 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'YEARLY'
export type OccurrenceStatus = 'GENERATED' | 'SKIPPED'

export interface RecurringRule {
  id: number
  category_id: number
  type: TransactionType
  amount: string
  currency: string
  description: string
  frequency: RecurrenceFrequency
  day_of_month: number | null
  day_of_week: number | null
  starts_on: string
  ends_on: string | null
  is_active: boolean
  /** Próximas fechas que la regla va a generar, calculadas por el backend. */
  next_dates: string[]
}

export interface Occurrence {
  id: number
  occurred_on: string
  status: OccurrenceStatus
  /** Null en una GENERATED significa que el movimiento se generó y se borró. */
  transaction_id: number | null
}

export interface UpcomingEntry {
  rule_id: number
  category_id: number
  description: string
  amount: string
  currency: string
  type: TransactionType
  due_on: string
}

/**
 * Vencimientos proyectados.
 *
 * No son movimientos: no entran en el balance, ni en los reportes, ni en el
 * export CSV. La pantalla tiene que dejarlo claro.
 */
export interface UpcomingSummary {
  date_from: string
  date_to: string
  currency: string
  entries: UpcomingEntry[]
  projected_income: string
  projected_expense: string
}

/**
 * Borrador propuesto a partir de la foto de un ticket.
 *
 * **No es un movimiento y no se creó nada**: precarga el formulario de alta, y
 * la creación sigue pasando por `POST /transactions` (docs/PROMPT.md §21.1).
 */
export interface ReceiptDraft {
  scan_id: number
  amount: string | null
  occurred_on: string
  merchant: string | null
  currency: string
  category_id: number | null
  category_name: string | null
  /** Confianza de 0 a 1 por campo leído. */
  confidence: Record<string, number>
  /** Campos que el modelo leyó con dudas; hay que revisarlos antes de confirmar. */
  low_confidence_fields: string[]
  /** Movimientos del mismo monto y fecha que ya existen. No bloquea el alta. */
  possible_duplicates: number[]
}

export type AlertType = 'BUDGET_EXCEEDED' | 'BUDGET_AT_RISK' | 'UNBUDGETED_SPENDING'
export type AlertStatus = 'OPEN' | 'READ' | 'RESOLVED'

/**
 * Desvío presupuestario detectado por el job diario.
 *
 * `recommendation` viene en null cuando el proveedor del modelo no respondió:
 * la alerta se emite igual, porque saber que te estás pasando no depende de
 * eso (docs/PROMPT.md §21.2).
 */
export interface BudgetAlert {
  id: number
  category_id: number
  period_month: string
  type: AlertType
  status: AlertStatus
  message: string
  recommendation: string | null
  /** Solo en las de riesgo: qué porcentaje del tope proyecta consumir el mes. */
  projected_percentage: string | null
}
