/**
 * Manejo de períodos `AAAA-MM`.
 *
 * Se opera sobre las partes del string y no con `Date` para no arrastrar el
 * problema de zonas horarias: `new Date('2026-08')` se interpreta como UTC y
 * en Argentina puede caer en el mes anterior.
 */

const PARTES = 2

export function periodoActual(hoy: Date = new Date()): string {
  const mes = String(hoy.getMonth() + 1).padStart(2, '0')
  return `${hoy.getFullYear()}-${mes}`
}

export function desplazarPeriodo(periodo: string, meses: number): string {
  const partes = periodo.split('-')
  if (partes.length !== PARTES) return periodo

  const anio = Number(partes[0])
  const mes = Number(partes[1])
  if (!Number.isFinite(anio) || !Number.isFinite(mes)) return periodo

  const total = anio * 12 + (mes - 1) + meses
  const anioNuevo = Math.floor(total / 12)
  const mesNuevo = (total % 12) + 1
  return `${String(anioNuevo).padStart(4, '0')}-${String(mesNuevo).padStart(2, '0')}`
}

export function primerDiaDe(periodo: string): string {
  return `${periodo}-01`
}

export function ultimoDiaDe(periodo: string): string {
  const partes = periodo.split('-')
  if (partes.length !== PARTES) return periodo
  const anio = Number(partes[0])
  const mes = Number(partes[1])
  // El día 0 del mes siguiente es el último del actual.
  const ultimo = new Date(anio, mes, 0).getDate()
  return `${periodo}-${String(ultimo).padStart(2, '0')}`
}
