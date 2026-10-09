import { describe, it, expect, vi, afterEach } from 'vitest'
import {
  usesDefaultTouchSort,
  touchSettingsDirty,
  withTouchTimeout,
  touchExportEndpoint,
} from '@/utils/touchTracking'

describe('touch settings and view choices', () => {
  it('routes only CRM touch ordering to the matching export', () => {
    expect(
      touchExportEndpoint('CRM Lead', 'last_touch_at desc, creation desc'),
    ).toBe('crm.touch_tracking_export.export_query')
    expect(touchExportEndpoint('CRM Deal', 'last_touch_at asc')).toBe(
      'crm.touch_tracking_export.export_query',
    )
    expect(touchExportEndpoint('Contact', 'last_touch_at desc')).toBe(
      'frappe.desk.reportview.export_query',
    )
    expect(touchExportEndpoint('CRM Lead', 'creation desc')).toBe(
      'frappe.desk.reportview.export_query',
    )
    expect(touchExportEndpoint('CRM Lead', 'modified desc')).toBe(
      'frappe.desk.reportview.export_query',
    )
  })
  it('uses the site default only for new or unsorted standard views', () => {
    expect(usesDefaultTouchSort()).toBe(true)
    expect(usesDefaultTouchSort({ is_standard: 1, order_by: '' })).toBe(true)
    expect(
      usesDefaultTouchSort({ is_standard: 1, order_by: 'modified desc' }),
    ).toBe(false)
    expect(usesDefaultTouchSort({ is_standard: 0, order_by: '' })).toBe(false)
    expect(
      usesDefaultTouchSort({ is_standard: 0, order_by: 'creation asc' }),
    ).toBe(false)
  })
  it('does not mark reordered selections or object keys as changes', () => {
    expect(
      touchSettingsDirty(
        { lead_fields: ['email', 'phone', 'email'], enabled: true },
        { enabled: true, lead_fields: ['phone', 'email'] },
      ),
    ).toBe(false)
  })
  it('detects changed rules, fields and the site switch independently', () => {
    const original = { enabled: true, lead_events: [], deal_fields: ['phone'] }
    for (const changes of [
      { enabled: false },
      { lead_events: ['task_due_date'] },
      { deal_fields: [] },
    ])
      expect(touchSettingsDirty({ ...original, ...changes }, original)).toBe(
        true,
      )
    expect(touchSettingsDirty(null, original)).toBe(false)
  })
})

describe('bounded touch UI requests', () => {
  afterEach(() => vi.useRealTimers())
  it('returns a successful response and removes the timer', async () => {
    vi.useFakeTimers()
    expect(
      await withTouchTimeout(() => Promise.resolve({ saved: true })),
    ).toEqual({ saved: true })
    expect(vi.getTimerCount()).toBe(0)
  })
  it('preserves API failures and removes the timer', async () => {
    vi.useFakeTimers()
    const failure = new Error('Permission denied')
    await expect(withTouchTimeout(() => Promise.reject(failure))).rejects.toBe(
      failure,
    )
    expect(vi.getTimerCount()).toBe(0)
  })
  it('turns a hanging request into a retryable error', async () => {
    vi.useFakeTimers()
    const request = withTouchTimeout(() => new Promise(() => {}), 100)
    const assertion = expect(request).rejects.toThrow(
      'Request timed out. Please retry.',
    )
    await vi.advanceTimersByTimeAsync(100)
    await assertion
    expect(vi.getTimerCount()).toBe(0)
  })
  it('handles a synchronous fetcher failure without leaving a timer', async () => {
    vi.useFakeTimers()
    await expect(
      withTouchTimeout(() => {
        throw new Error('Unavailable')
      }),
    ).rejects.toThrow('Unavailable')
    expect(vi.getTimerCount()).toBe(0)
  })
})
