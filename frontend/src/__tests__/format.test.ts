import { describe, expect, it } from 'vitest'

import {
  formatDate,
  formatMoney,
  formatPercent,
  formatPeriod,
  isNegative,
} from '@/utils/format'

describe('formatMoney', () => {
  it('formatea con separadores de es-AR', () => {
    // Arrange / Act
    const resultado = formatMoney('1234567.89', 'ARS')

    // Assert: punto para miles y coma decimal.
    expect(resultado).toContain('1.234.567,89')
  })

  it('siempre muestra dos decimales', () => {
    // Arrange / Act / Assert
    expect(formatMoney('1000', 'ARS')).toContain('1.000,00')
  })

  it('formatea montos negativos', () => {
    // Arrange / Act / Assert
    expect(formatMoney('-500.25', 'ARS')).toContain('500,25')
    expect(formatMoney('-500.25', 'ARS')).toMatch(/-/)
  })

  it('devuelve el valor crudo si no es un número', () => {
    // Arrange / Act / Assert
    expect(formatMoney('no-es-un-monto', 'ARS')).toBe('no-es-un-monto ARS')
  })
})

describe('formatDate', () => {
  it('convierte ISO a dd/MM/yyyy', () => {
    // Arrange / Act / Assert
    expect(formatDate('2026-08-05')).toBe('05/08/2026')
  })

  it('no corre la fecha un día hacia atrás', () => {
    /*
     * `new Date('2026-08-01')` se interpreta como medianoche UTC, que en
     * Argentina (UTC-3) es el 31 de julio a las 21. Formatear con el
     * constructor mostraría el día anterior en todo el país.
     */
    // Arrange / Act / Assert
    expect(formatDate('2026-08-01')).toBe('01/08/2026')
    expect(formatDate('2026-01-01')).toBe('01/01/2026')
  })

  it('tolera un timestamp completo', () => {
    // Arrange / Act / Assert
    expect(formatDate('2026-08-05T13:45:00Z')).toBe('05/08/2026')
  })

  it('devuelve el valor crudo si no tiene forma de fecha', () => {
    // Arrange / Act / Assert
    expect(formatDate('ayer')).toBe('ayer')
  })
})

describe('formatPeriod', () => {
  it('convierte AAAA-MM al nombre del mes', () => {
    // Arrange / Act
    const resultado = formatPeriod('2026-08')

    // Assert
    expect(resultado.toLowerCase()).toContain('agosto')
    expect(resultado).toContain('2026')
  })

  it('devuelve el valor crudo si no tiene forma de período', () => {
    // Arrange / Act / Assert
    expect(formatPeriod('2026')).toBe('2026')
  })
})

describe('formatPercent', () => {
  it('agrega el símbolo y usa coma decimal', () => {
    // Arrange / Act / Assert
    expect(formatPercent('83.33')).toBe('83,3%')
  })

  it('acepta porcentajes por encima de cien', () => {
    // Arrange / Act / Assert
    expect(formatPercent('130.00')).toBe('130,0%')
  })
})

describe('isNegative', () => {
  it('reconoce los montos negativos', () => {
    // Arrange / Act / Assert
    expect(isNegative('-1.00')).toBe(true)
    expect(isNegative('0.00')).toBe(false)
    expect(isNegative('1.00')).toBe(false)
  })
})
