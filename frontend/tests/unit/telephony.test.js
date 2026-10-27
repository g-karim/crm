import {
  callDuration,
  callCalendarDate,
  callStatusKey,
  dialNumber,
  displayPhone,
  groupCalls,
  isMissedCall,
  mergeCalls,
} from '@/utils/telephony'

describe('telephony workspace helpers', () => {
  it('localizes site-local calendar dates without a timezone day shift', () => {
    expect(callCalendarDate('2026-10-22 23:59:00', 'ru')).toContain('октября')
    expect(callCalendarDate('2026-10-22', 'en')).toContain('October')
    expect(callCalendarDate('')).toBe('')
  })
  it('normalizes Russian local numbers without accepting names or dial commands', () => {
    expect(dialNumber('8 (962) 555-19-66')).toBe('79625551966')
    expect(dialNumber('Алексей')).toBe('')
    expect(dialNumber('*123#')).toBe('')
    expect(dialNumber('')).toBe('')
  })
  it('formats international numbers and preserves an unknown caller identifier', () => {
    expect(displayPhone('79625551966')).toBe('+7 962 555-19-66')
    expect(displayPhone('+442079460958')).toBe('+442079460958')
    expect(displayPhone('anonymous')).toBe('anonymous')
  })
  it('formats numeric and fractional durations and handles absent values', () => {
    expect(callDuration('34.48')).toBe('0:34')
    expect(callDuration(3661)).toBe('61:01')
    expect(callDuration(null)).toBe('0:00')
    expect(callDuration(-10)).toBe('0:00')
  })
  it('distinguishes unanswered outgoing attempts from missed incoming calls', () => {
    expect(isMissedCall({ type: 'Outgoing', status: 'No Answer' })).toBe(false)
    expect(isMissedCall({ type: 'Incoming', status: 'No Answer' })).toBe(true)
    expect(isMissedCall({ type: 'Incoming', status: 'Completed' })).toBe(false)
    expect(callStatusKey({ type: 'Outgoing', status: 'No Answer' })).toBe(
      'No answer',
    )
    expect(callStatusKey({ type: 'Incoming', status: 'No Answer' })).toBe(
      'Missed Call',
    )
  })
  it('groups site-local dates without reinterpreting them in the browser timezone', () => {
    const rows = [
      { name: 'a', timestamp: '2026-10-23 00:01:00' },
      { name: 'b', timestamp: '2026-10-22 23:59:00' },
      { name: 'c', timestamp: '2026-10-23 00:00:00' },
    ]
    expect(
      groupCalls(rows).map((group) => [
        group.date,
        group.calls.map((call) => call.name),
      ]),
    ).toEqual([
      ['2026-10-23', ['a', 'c']],
      ['2026-10-22', ['b']],
    ])
  })
  it('updates a repeated page boundary without duplicate call records', () => {
    expect(
      mergeCalls(
        [{ name: 'a', duration: 1 }],
        [{ name: 'a', duration: 2 }, { name: 'b' }],
      ),
    ).toEqual([{ name: 'a', duration: 2 }, { name: 'b' }])
  })
})
