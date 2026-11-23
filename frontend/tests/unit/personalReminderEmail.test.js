import { describe, expect, it } from 'vitest'
import { scheduleOperation } from '../../src/utils/personalReminder'

describe('personal reminder email channel', () => {
  it('supports email alone independently of both push channels and One', () => {
    const channels = { crm_push: false, one_message: false, one_push: false, email: true }
    const result = scheduleOperation('17', new Date(Date.now() + 3600000).toISOString(), channels, 'fixture@example.invalid', 'a'.repeat(32))
    expect(result.args.channels).toEqual(channels)
    channels.email = false
    expect(result.args.channels.email).toBe(true)
  })
  it('still rejects an empty selection and a One push without a One message', () => {
    const future = new Date(Date.now() + 3600000).toISOString()
    expect(() => scheduleOperation('17', future, { email: false }, 'fixture')).toThrow()
    expect(() => scheduleOperation('17', future, { email: true, one_push: true, one_message: false }, 'fixture')).toThrow()
  })
})
