import { describe, expect, it } from 'vitest'
import { formatAnalyticsNumber } from '../../src/utils/analyticsNumbers'

describe('analytics exact number display', () => {
  it('preserves cents in totals larger than the safe Number precision', () => {
    expect(formatAnalyticsNumber('99999999999999.01', 'en-US')).toBe(
      '99,999,999,999,999.01',
    )
    expect(formatAnalyticsNumber('100999999999998.99', 'en-US')).toBe(
      '100,999,999,999,998.99',
    )
  })

  it('rounds a decimal string without floating point loss or negative zero', () => {
    expect(formatAnalyticsNumber('0.005', 'en-US')).toBe('0.01')
    expect(formatAnalyticsNumber('-0.005', 'en-US')).toBe('-0.01')
    expect(formatAnalyticsNumber('-0.001', 'en-US')).toBe('0')
    expect(formatAnalyticsNumber('999.999', 'en-US')).toBe('1,000')
    expect(formatAnalyticsNumber('0.000001', 'en-US', 6)).toBe('0.000001')
    expect(formatAnalyticsNumber('9.50', 'en-US', 0)).toBe('10')
  })

  it('uses the selected locale and distinguishes missing values from zero', () => {
    const localized = formatAnalyticsNumber('100000000000000.01', 'ru-RU')
    expect(localized.replace(/\s/g, ' ')).toBe('100 000 000 000 000,01')
    expect(formatAnalyticsNumber(0, 'ru-RU')).toBe('0')
    expect(formatAnalyticsNumber(null, 'ru-RU')).toBe('—')
    expect(formatAnalyticsNumber('invalid', 'ru-RU')).toBe('—')
    expect(formatAnalyticsNumber(Infinity, 'ru-RU')).toBe('—')
  })
})
