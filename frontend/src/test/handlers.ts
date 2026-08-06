import { HttpResponse, http } from 'msw'

import type {
  Budget,
  BudgetProgress,
  Category,
  CategoryBreakdown,
  ChatMessage,
  MonthlyTrend,
  Occurrence,
  PeriodSummary,
  RecurringRule,
  TokenResponse,
  Transaction,
  UpcomingSummary,
  User,
} from '@/types/api'

export const BASE = '/api/v1'

export const USUARIO: User = {
  id: 1,
  email: 'damian@ejemplo.com',
  full_name: 'Damián Orsi',
  is_active: true,
}

export const TOKENS: TokenResponse = {
  access_token: 'access-1',
  refresh_token: 'refresh-1',
  token_type: 'bearer',
  expires_in: 900,
}

export const RESUMEN: PeriodSummary = {
  currency: 'ARS',
  date_from: '2026-08-01',
  date_to: '2026-08-31',
  income: '850000.00',
  expense: '450000.50',
  balance: '399999.50',
}

/** Contador de renovaciones, para verificar que no se dispare más de una. */
export const contadores = { refresh: 0 }

/**
 * Store en memoria.
 *
 * Los handlers de CRUD operan sobre esto en vez de devolver constantes: así un
 * test puede crear algo y verificar que aparece en el listado, que es
 * exactamente lo que hace la persona usuaria.
 */
interface Store {
  categorias: Category[]
  movimientos: Transaction[]
  presupuestos: Budget[]
  desglose: CategoryBreakdown
  tendencia: MonthlyTrend
  progreso: BudgetProgress
  /** Mensajes del asistente, indexados por `conversation_id`. */
  conversaciones: Record<string, ChatMessage[]>
  reglas: RecurringRule[]
  /** Ocurrencias por `rule_id`. */
  ocurrencias: Record<number, Occurrence[]>
  vencimientos: UpcomingSummary
}

function estadoInicial(): Store {
  return {
    categorias: [
      { id: 10, name: 'Sueldo', type: 'INCOME', color: '#1c9e6f', is_default: true },
      { id: 20, name: 'Alimentación', type: 'EXPENSE', color: '#d1603d', is_default: true },
      { id: 21, name: 'Ocio', type: 'EXPENSE', color: '#7a5ba6', is_default: true },
    ],
    movimientos: [
      {
        id: 100,
        type: 'EXPENSE',
        amount: '1234.56',
        currency: 'ARS',
        occurred_on: '2026-08-05',
        category_id: 20,
        description: 'Supermercado',
        is_recurring: false,
      },
      {
        id: 101,
        type: 'INCOME',
        amount: '850000.00',
        currency: 'ARS',
        occurred_on: '2026-08-01',
        category_id: 10,
        description: 'Sueldo agosto',
        is_recurring: true,
      },
    ],
    presupuestos: [
      { id: 200, category_id: 20, period_month: '2026-08', amount: '100000.00', currency: 'ARS' },
    ],
    desglose: {
      currency: 'ARS',
      date_from: '2026-08-01',
      date_to: '2026-08-31',
      entries: [
        {
          category_id: 20,
          category_name: 'Alimentación',
          type: 'EXPENSE',
          total: '85000.00',
          percentage: '75.00',
          transaction_count: 4,
        },
        {
          category_id: 21,
          category_name: 'Ocio',
          type: 'EXPENSE',
          total: '28333.33',
          percentage: '25.00',
          transaction_count: 2,
        },
      ],
    },
    tendencia: {
      currency: 'ARS',
      entries: [
        { period: '2026-07', income: '800000.00', expense: '400000.00', balance: '400000.00' },
        { period: '2026-08', income: '850000.00', expense: '450000.50', balance: '399999.50' },
      ],
    },
    progreso: {
      currency: 'ARS',
      period_month: '2026-08',
      entries: [
        {
          budget_id: 200,
          category_id: 20,
          category_name: 'Alimentación',
          budgeted: '100000.00',
          spent: '130000.00',
          remaining: '-30000.00',
          percentage: '130.00',
          status: 'EXCEEDED',
        },
        {
          budget_id: 201,
          category_id: 21,
          category_name: 'Ocio',
          budgeted: '50000.00',
          spent: '42000.00',
          remaining: '8000.00',
          percentage: '84.00',
          status: 'WARNING',
        },
      ],
      unbudgeted: [{ category_id: 22, category_name: 'Transporte', spent: '40000.00' }],
      exceeded_count: 1,
    },
    conversaciones: {},
    reglas: [
      {
        id: 300,
        category_id: 20,
        type: 'EXPENSE',
        amount: '45000.00',
        currency: 'ARS',
        description: 'Alquiler',
        frequency: 'MONTHLY',
        day_of_month: 10,
        day_of_week: null,
        starts_on: '2026-01-10',
        ends_on: null,
        is_active: true,
        next_dates: ['2026-09-10', '2026-10-10', '2026-11-10'],
      },
    ],
    ocurrencias: {
      300: [
        { id: 400, occurred_on: '2026-08-10', status: 'GENERATED', transaction_id: 900 },
        // Generada y borrada después: el job no la vuelve a crear.
        { id: 401, occurred_on: '2026-07-10', status: 'SKIPPED', transaction_id: null },
      ],
    },
    vencimientos: {
      date_from: '2026-08-06',
      date_to: '2026-09-05',
      currency: 'ARS',
      entries: [
        {
          rule_id: 300,
          category_id: 20,
          description: 'Alquiler',
          amount: '45000.00',
          currency: 'ARS',
          type: 'EXPENSE',
          due_on: '2026-09-10',
        },
      ],
      projected_income: '0.00',
      projected_expense: '45000.00',
    },
  }
}

export let store: Store = estadoInicial()

export function reiniciarContadores(): void {
  contadores.refresh = 0
  store = estadoInicial()
}

let siguienteId = 1000
const nuevoId = () => (siguienteId += 1)

export const handlers = [
  // --- Autenticación -------------------------------------------------------
  http.post(`${BASE}/auth/login`, async ({ request }) => {
    const cuerpo = (await request.json()) as { password: string }
    if (cuerpo.password === 'incorrecta') {
      return HttpResponse.json(
        { code: 'invalid_credentials', message: 'Email o contraseña incorrectos.', details: [] },
        { status: 401 },
      )
    }
    return HttpResponse.json(TOKENS)
  }),

  http.post(`${BASE}/auth/register`, async ({ request }) => {
    const cuerpo = (await request.json()) as { email: string }
    if (cuerpo.email === 'repetido@ejemplo.com') {
      return HttpResponse.json(
        {
          code: 'email_already_registered',
          message: 'Ya existe una cuenta con ese email.',
          details: [],
        },
        { status: 409 },
      )
    }
    return HttpResponse.json(USUARIO, { status: 201 })
  }),

  http.post(`${BASE}/auth/refresh`, () => {
    contadores.refresh += 1
    return HttpResponse.json({ ...TOKENS, access_token: 'access-2', refresh_token: 'refresh-2' })
  }),

  http.post(`${BASE}/auth/logout`, () => new HttpResponse(null, { status: 204 })),

  http.get(`${BASE}/users/me`, ({ request }) => {
    if (!request.headers.get('Authorization')) {
      return HttpResponse.json(
        { code: 'invalid_token', message: 'Falta el token de acceso.', details: [] },
        { status: 401 },
      )
    }
    return HttpResponse.json(USUARIO)
  }),

  // --- Categorías ----------------------------------------------------------
  http.get(`${BASE}/categories`, ({ request }) => {
    const tipo = new URL(request.url).searchParams.get('type')
    return HttpResponse.json(
      tipo ? store.categorias.filter((categoria) => categoria.type === tipo) : store.categorias,
    )
  }),

  http.post(`${BASE}/categories`, async ({ request }) => {
    const cuerpo = (await request.json()) as Omit<Category, 'id' | 'is_default'>
    const repetida = store.categorias.some(
      (categoria) => categoria.name === cuerpo.name && categoria.type === cuerpo.type,
    )
    if (repetida) {
      return HttpResponse.json(
        {
          code: 'duplicate_resource',
          message: `Ya tenés una categoría llamada «${cuerpo.name}».`,
          details: [],
        },
        { status: 409 },
      )
    }
    const creada: Category = { ...cuerpo, id: nuevoId(), is_default: false }
    store.categorias.push(creada)
    return HttpResponse.json(creada, { status: 201 })
  }),

  http.patch(`${BASE}/categories/:id`, async ({ params, request }) => {
    const cuerpo = (await request.json()) as { name?: string; color?: string }
    const categoria = store.categorias.find((c) => c.id === Number(params.id))
    if (!categoria) return new HttpResponse(null, { status: 404 })
    Object.assign(categoria, cuerpo)
    return HttpResponse.json(categoria)
  }),

  http.delete(`${BASE}/categories/:id`, ({ params }) => {
    const id = Number(params.id)
    if (store.movimientos.some((movimiento) => movimiento.category_id === id)) {
      return HttpResponse.json(
        {
          code: 'resource_in_use',
          message:
            'No se puede borrar «Alimentación»: tiene 1 movimiento asociados. ' +
            'Reasignalos o borralos antes.',
          details: [],
        },
        { status: 409 },
      )
    }
    store.categorias = store.categorias.filter((categoria) => categoria.id !== id)
    return new HttpResponse(null, { status: 204 })
  }),

  // --- Movimientos ---------------------------------------------------------
  http.get(`${BASE}/transactions`, ({ request }) => {
    const params = new URL(request.url).searchParams
    let resultado = [...store.movimientos]

    const tipo = params.get('type')
    if (tipo) resultado = resultado.filter((movimiento) => movimiento.type === tipo)

    const categoria = params.get('category_id')
    if (categoria) resultado = resultado.filter((m) => m.category_id === Number(categoria))

    const texto = params.get('q')
    if (texto) {
      resultado = resultado.filter((m) =>
        m.description.toLowerCase().includes(texto.toLowerCase()),
      )
    }

    const offset = Number(params.get('offset') ?? 0)
    const limit = Number(params.get('limit') ?? 20)
    return HttpResponse.json({
      entries: resultado.slice(offset, offset + limit),
      offset,
      limit,
      totalCount: resultado.length,
    })
  }),

  http.post(`${BASE}/transactions`, async ({ request }) => {
    const cuerpo = (await request.json()) as Omit<Transaction, 'id' | 'currency' | 'is_recurring'>
    const creado: Transaction = { ...cuerpo, id: nuevoId(), currency: 'ARS', is_recurring: false }
    store.movimientos.unshift(creado)
    return HttpResponse.json(creado, { status: 201 })
  }),

  http.patch(`${BASE}/transactions/:id`, async ({ params, request }) => {
    const cuerpo = (await request.json()) as Partial<Transaction>
    const movimiento = store.movimientos.find((m) => m.id === Number(params.id))
    if (!movimiento) return new HttpResponse(null, { status: 404 })
    Object.assign(movimiento, cuerpo)
    return HttpResponse.json(movimiento)
  }),

  http.delete(`${BASE}/transactions/:id`, ({ params }) => {
    store.movimientos = store.movimientos.filter((m) => m.id !== Number(params.id))
    return new HttpResponse(null, { status: 204 })
  }),

  http.get(`${BASE}/transactions/export`, () =>
    HttpResponse.text('id,fecha\n1,2026-08-05\n', {
      headers: {
        'Content-Type': 'text/csv',
        'Content-Disposition': 'attachment; filename="movimientos.csv"',
      },
    }),
  ),

  // --- Reportes ------------------------------------------------------------
  http.get(`${BASE}/reports/summary`, () => HttpResponse.json(RESUMEN)),
  http.get(`${BASE}/reports/by-category`, () => HttpResponse.json(store.desglose)),
  http.get(`${BASE}/reports/monthly-trend`, () => HttpResponse.json(store.tendencia)),

  // --- Presupuestos --------------------------------------------------------
  http.get(`${BASE}/budgets`, ({ request }) => {
    const periodo = new URL(request.url).searchParams.get('period_month')
    return HttpResponse.json(
      store.presupuestos.filter((presupuesto) => presupuesto.period_month === periodo),
    )
  }),

  http.get(`${BASE}/budgets/progress`, () => HttpResponse.json(store.progreso)),

  http.post(`${BASE}/budgets`, async ({ request }) => {
    const cuerpo = (await request.json()) as Omit<Budget, 'id' | 'currency'>
    const creado: Budget = { ...cuerpo, id: nuevoId(), currency: 'ARS' }
    store.presupuestos.push(creado)
    return HttpResponse.json(creado, { status: 201 })
  }),

  http.patch(`${BASE}/budgets/:id`, async ({ params, request }) => {
    const cuerpo = (await request.json()) as { amount: string }
    const presupuesto = store.presupuestos.find((p) => p.id === Number(params.id))
    if (!presupuesto) return new HttpResponse(null, { status: 404 })
    presupuesto.amount = cuerpo.amount
    return HttpResponse.json(presupuesto)
  }),

  http.delete(`${BASE}/budgets/:id`, ({ params }) => {
    store.presupuestos = store.presupuestos.filter((p) => p.id !== Number(params.id))
    return new HttpResponse(null, { status: 204 })
  }),

  http.post(`${BASE}/budgets/copy-from`, async ({ request }) => {
    const cuerpo = (await request.json()) as { from_period: string; to_period: string }
    return HttpResponse.json(
      {
        ...cuerpo,
        currency: 'ARS',
        created: 2,
        skipped: [{ category_id: 20, category_name: 'Alimentación' }],
      },
      { status: 201 },
    )
  }),

  /*
   * Reglas recurrentes. `next_dates` lo calcula el backend, así que el doble
   * lo devuelve fijo: duplicar acá la aritmética de calendario sería tener dos
   * fuentes de verdad, que es justo lo que el diseño evita.
   */
  http.get(`${BASE}/recurring-rules/upcoming`, () => HttpResponse.json(store.vencimientos)),

  http.get(`${BASE}/recurring-rules`, ({ request }) => {
    const activas = new URL(request.url).searchParams.get('is_active')
    if (activas === null) return HttpResponse.json(store.reglas)
    const esperado = activas === 'true'
    return HttpResponse.json(store.reglas.filter((r) => r.is_active === esperado))
  }),

  http.post(`${BASE}/recurring-rules`, async ({ request }) => {
    const cuerpo = (await request.json()) as Partial<RecurringRule>
    const creada: RecurringRule = {
      id: nuevoId(),
      category_id: cuerpo.category_id ?? 0,
      type: cuerpo.type ?? 'EXPENSE',
      amount: cuerpo.amount ?? '0.00',
      currency: 'ARS',
      description: cuerpo.description ?? '',
      frequency: cuerpo.frequency ?? 'MONTHLY',
      day_of_month: cuerpo.day_of_month ?? null,
      day_of_week: cuerpo.day_of_week ?? null,
      starts_on: cuerpo.starts_on ?? '2026-08-01',
      ends_on: cuerpo.ends_on ?? null,
      is_active: true,
      next_dates: ['2026-09-10', '2026-10-10', '2026-11-10'],
    }
    store.reglas.push(creada)
    return HttpResponse.json(creada, { status: 201 })
  }),

  http.patch(`${BASE}/recurring-rules/:id`, async ({ params, request }) => {
    const cuerpo = (await request.json()) as Partial<RecurringRule>
    const regla = store.reglas.find((r) => r.id === Number(params.id))
    if (!regla) return new HttpResponse(null, { status: 404 })
    Object.assign(regla, cuerpo)
    // Una regla pausada no proyecta: el backend devuelve `next_dates` vacío.
    regla.next_dates = regla.is_active ? ['2026-09-10', '2026-10-10', '2026-11-10'] : []
    return HttpResponse.json(regla)
  }),

  http.delete(`${BASE}/recurring-rules/:id`, ({ params }) => {
    store.reglas = store.reglas.filter((r) => r.id !== Number(params.id))
    return new HttpResponse(null, { status: 204 })
  }),

  http.get(`${BASE}/recurring-rules/:id/occurrences`, ({ params }) =>
    HttpResponse.json(store.ocurrencias[Number(params.id)] ?? []),
  ),

  /*
   * Asistente. Guarda las dos puntas de la conversación igual que el backend,
   * para que un test pueda mandar un mensaje, recargar y verificar que el
   * historial lo devuelve.
   */
  http.post(`${BASE}/chat`, async ({ request }) => {
    const cuerpo = (await request.json()) as { message: string; conversation_id?: string }
    const conversacion = cuerpo.conversation_id ?? `conv-${nuevoId()}`
    // La respuesta no repite la consulta a propósito: si la contuviera, una
    // aserción sobre el texto de la pregunta encontraría dos elementos y no se
    // podría distinguir la burbuja propia de la del asistente.
    const respuesta = 'Gastaste 450.000,50 ARS este mes.'

    store.conversaciones[conversacion] = [
      ...(store.conversaciones[conversacion] ?? []),
      { role: 'USER', content: cuerpo.message, created_at: '2026-08-05T14:30:00' },
      { role: 'ASSISTANT', content: respuesta, created_at: '2026-08-05T14:30:02' },
    ]

    return HttpResponse.json({
      conversation_id: conversacion,
      content: respuesta,
      degraded: false,
    })
  }),

  http.get(`${BASE}/chat/history`, ({ request }) => {
    const conversacion = new URL(request.url).searchParams.get('conversation_id') ?? ''
    return HttpResponse.json(store.conversaciones[conversacion] ?? [])
  }),
]
