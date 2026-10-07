import { afterEach, describe, expect, it } from 'vitest'
import { formatCalendarMonthYear } from '@/utils/calendarLocalization'

const originalFrappe = globalThis.frappe
const originalTranslate = globalThis.__

afterEach(() => {
  globalThis.frappe = originalFrappe
  globalThis.__ = originalTranslate
})

describe('calendar month headings', () => {
  it('capitalizes Russian month names for short and long headings', () => {
    globalThis.frappe = { boot: { lang: 'ru' } }
    globalThis.__ = (value) => value

    expect(formatCalendarMonthYear(new Date(2026, 0, 1))).toMatch(
      /^Январь 2026/,
    )
    expect(formatCalendarMonthYear(new Date(2026, 8, 1))).toMatch(
      /^Сентябрь 2026/,
    )
  })
})
