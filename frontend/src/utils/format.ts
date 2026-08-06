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

/**
 * Formatea la hora de un timestamp ISO como `14:35`.
 *
 * A diferencia de `formatDate`, acá sí corresponde `new Date`: los timestamps
 * de auditoría vienen con hora en UTC y hay que convertirlos a la zona de quien
 * mira. El bug que evita `formatDate` es el opuesto —tratar como UTC una fecha
 * que no tiene hora—, así que no aplica.
 */
export function formatTime(iso: string): string {
  const momento = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`)
  if (Number.isNaN(momento.getTime())) return ''
  return new Intl.DateTimeFormat(LOCALE, { hour: '2-digit', minute: '2-digit' }).format(momento)
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

/**
 * Formatea un número en notación compacta: `900000` como `900 mil`.
 *
 * Es para los ejes de los gráficos y nada más. En un celular, un eje con
 * `1.200.000` de ancho se lleva un tercio de la pantalla y deja las barras
 * aplastadas contra el borde.
 */
export function formatCompact(valor: number): string {
  if (!Number.isFinite(valor)) return ''
  return new Intl.NumberFormat(LOCALE, {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(valor)
}

/** `true` si el monto de la API es negativo, para decidir el color. */
export function isNegative(amount: string): boolean {
  return Number(amount) < 0
}
