import { describe, expect, it, vi } from 'vitest'
import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'
import {
  callOutcomes,
  callbackDeadline,
  saveFollowup,
  seekRecording,
} from '../../src/utils/callFollowups'
dayjs.extend(utc)
dayjs.extend(timezone)

describe('callback deadline timezone boundary', () => {
  it('converts the chosen user-local time to the site timezone', () => {
    expect(
      callbackDeadline(
        '2026-10-23T23:00',
        dayjs,
        'Africa/Abidjan',
        'Europe/Moscow',
      ),
    ).toBe('2026-10-23 20:00:00')
  })
  it('preserves the instant across a calendar-day boundary', () => {
    expect(
      callbackDeadline('2026-10-24T01:15', dayjs, 'UTC', 'Europe/Moscow'),
    ).toBe('2026-10-23 22:15:00')
  })
})

const state = () => ({
  saving: false,
  pending: null,
  conflict: false,
  error: '',
})

describe('call follow-up operation safety', () => {
  it('offers manager outcomes independently of provider statuses', () => {
    expect(callOutcomes).toEqual([
      'Agreed',
      'Callback',
      'Not interested',
      'Wrong number',
    ])
  })
  it('retries the exact frozen operation after an unknown response', async () => {
    const s = state(),
      request = vi
        .fn()
        .mockRejectedValueOnce(new Error('Network'))
        .mockResolvedValue({ revision: 1 })
    const params = {
      name: 'call-1',
      mutation_id: 'original',
      callback: { due_date: 'tomorrow' },
    }
    await saveFollowup(s, { request, endpoint: 'save', params })
    expect(s.pending).not.toBeNull()
    params.callback.due_date = 'changed'
    await saveFollowup(s, {
      request,
      endpoint: 'different',
      params: { mutation_id: 'new' },
    })
    expect(request.mock.calls[1]).toEqual([
      'save',
      {
        name: 'call-1',
        mutation_id: 'original',
        callback: { due_date: 'tomorrow' },
      },
    ])
    expect(s.pending).toBeNull()
  })
  it('does not apply a late response after selecting another call or account', async () => {
    const s = state()
    const result = await saveFollowup(s, {
      request: async () => ({ name: 'old-call' }),
      endpoint: 'save',
      params: {},
      isCurrent: () => false,
    })
    expect(result).toBeNull()
  })
  it('blocks silent overwrite after a revision conflict', async () => {
    const s = state(),
      request = vi
        .fn()
        .mockRejectedValue({ exc_type: 'TimestampMismatchError' })
    await saveFollowup(s, { request, endpoint: 'save', params: {} })
    expect(s.conflict).toBe(true)
    expect(s.pending).toBeNull()
    await saveFollowup(s, { request, endpoint: 'save', params: {} })
    expect(request).toHaveBeenCalledTimes(1)
  })
  it('allows corrected input only after a definite permission rejection', async () => {
    const s = state()
    await saveFollowup(s, {
      request: async () => {
        throw { exc_type: 'PermissionError' }
      },
      endpoint: 'save',
      params: {},
    })
    expect(s.pending).toBeNull()
    expect(s.error).toContain('Check')
  })
  it('prevents parallel saves', async () => {
    const s = { ...state(), saving: true },
      request = vi.fn()
    await saveFollowup(s, { request, endpoint: 'save', params: {} })
    expect(request).not.toHaveBeenCalled()
  })
})

describe('recording seeking', () => {
  it('clamps backward and forward seeking to media bounds', () => {
    expect(seekRecording(3, 30, -10)).toBe(0)
    expect(seekRecording(28, 30, 10)).toBe(30)
    expect(seekRecording(15, 30, -10)).toBe(5)
  })
  it('does not seek until media duration is known', () => {
    expect(seekRecording(0, NaN, 10)).toBeNull()
    expect(seekRecording(0, Infinity, 10)).toBeNull()
  })
})
