import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { scheduleOperation } from '../../src/utils/personalReminder'

describe('personal reminder request', () => {
  beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(new Date('2030-01-01T00:00:00Z')) })
  afterEach(() => vi.useRealTimers())
  const channels = () => ({ crm_push: true, one_message: true, one_push: true })
  it('preserves the chosen local time as an explicit instant without a task deadline', () => {
    const value = scheduleOperation('12', '2030-01-02T15:00', channels(), 'viewer', 'operation')
    expect(new Date(value.args.at).getHours()).toBe(15)
    expect(value.args.task).toBe('12')
    expect(value.args).not.toHaveProperty('due_date')
  })
  it('keeps the pending payload independent of later channel edits', () => {
    const input = channels(), value = scheduleOperation('12', '2030-01-02T15:00', input, 'viewer', 'operation')
    input.one_message = false
    expect(value.args.channels.one_message).toBe(true)
    expect(value.args.mutation_id).toBe('operation')
  })
  it('rejects empty and past dates before creating an operation', () => {
    for (const date of ['', 'invalid', '2020-01-01T15:00']) expect(() => scheduleOperation('12', date, channels(), 'viewer')).toThrow()
  })
  it('rejects a One push without its message', () => {
    expect(() => scheduleOperation('12', '2030-01-02T15:00', { crm_push: true, one_message: false, one_push: true }, 'viewer')).toThrow()
  })
  it('rejects an empty delivery selection', () => {
    expect(() => scheduleOperation('12', '2030-01-02T15:00', { crm_push: false, one_message: false, one_push: false }, 'viewer')).toThrow()
  })
})
