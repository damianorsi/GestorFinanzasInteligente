/**
 * Única fuente de formateo de la aplicación.
 *
 * Ningún componente formatea montos ni fechas por su cuenta: la API habla ISO
 * —fechas `YYYY-MM-DD`, montos como string con punto decimal— y la conversión
 * a `es-AR` ocurre solo acá. El día que se habilite otra moneda, se toca una
 * función (docs/PROMPT.md §5.1 y §5.3).
 */

const LOCALE = 'es-AR'

/** Formatea un monto que viene de la API como string. */
export function formatMoney(amount: string, currency: string): string {
  const valor = Number(amount)
  if (!Number.isFinite(valor)) return `${amount} ${currency}`

  return new Intl.NumberFormat(LOCALE, {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(valor)
}

/**
 * Formatea una fecha ISO (`2026-08-05`) como `05/08/2026`.
 *
 * Se parsea a mano en vez de con `new Date(iso)`: ese constructor interpreta
 * las fechas sin hora como UTC y las muestra corridas un día en zonas al oeste
 * de Greenwich, que es justo el caso de Argentina.
 */
export function formatDate(iso: string): string {
  const partes = iso.slice(0, 10).split('-')
  if (partes.length !== 3) return iso
  const [anio, mes, dia] = partes
  return `${dia}/${mes}/${anio}`
}

/** Formatea el período `2026-08` como `agosto 2026`. */
export function formatPeriod(period: string): string {
  const partes = period.split('-')
  if (partes.length !== 2) return period
  const [anio, mes] = partes
  const nombre = new Intl.DateTimeFormat(LOCALE, { month: 'long' }).format(
    new Date(Number(anio), Number(mes) - 1, 1),
  )
  return `${nombre} ${anio}`
}

/** Formatea un porcentaje que viene de la API como string. */
export function formatPercent(percentage: string): string {
  const valor = Number(percentage)
  if (!Number.isFinite(valor)) return `${percentage}%`
  return `${new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(valor)}%`
}

/** `true` si el monto de la API es negativo, para decidir el color. */
export function isNegative(amount: string): boolean {
  return Number(amount) < 0
}
