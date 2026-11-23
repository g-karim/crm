import { describe, it, expect } from 'vitest'
import { analyticsPeriod } from '../../src/utils/analyticsPeriods'
describe('analytics calendar shortcuts', () => {
  it('compares 30 inclusive days across a year boundary', () =>
    expect(analyticsPeriod('30days', '2026-01-10')).toEqual({
      from_date: '2025-12-12',
      to_date: '2026-01-10',
    }))
  it('uses the observed part of this month', () =>
    expect(analyticsPeriod('month', '2026-11-16')).toEqual({
      from_date: '2026-11-01',
      to_date: '2026-11-16',
    }))
  it('anchors the quarter to its first month', () =>
    expect(analyticsPeriod('quarter', '2026-11-16')).toEqual({
      from_date: '2026-10-01',
      to_date: '2026-11-16',
    }))
  it('includes leap day', () =>
    expect(analyticsPeriod('30days', '2024-03-01').from_date).toBe(
      '2024-02-01',
    ))
  it('rejects nonexistent calendar dates', () =>
    expect(() => analyticsPeriod('month', '2026-02-30')).toThrow(RangeError))
  it('rejects unknown shortcuts', () =>
    expect(() => analyticsPeriod('year', '2026-11-16')).toThrow(RangeError))
})
