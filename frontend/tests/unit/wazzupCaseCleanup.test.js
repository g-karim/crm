import { withWazzupCaseCleanup } from '../browser/wazzup-case-cleanup'

describe('Partner browser fixture cleanup', () => {
  it('waits for the held request to settle before completing a successful case', async () => {
    let release
    const held = new Promise((resolve) => {
      release = resolve
    })
    const events = []
    const result = withWazzupCaseCleanup(
      async () => {
        events.push('scenario')
        return 'verified'
      },
      async () => {
        events.push('cleanup started')
        await held
        events.push('cleanup settled')
      },
    ).then((value) => {
      events.push('next case may start')
      return value
    })

    await Promise.resolve()
    expect(events).toEqual(['scenario', 'cleanup started'])
    release()
    await expect(result).resolves.toBe('verified')
    expect(events).toEqual([
      'scenario',
      'cleanup started',
      'cleanup settled',
      'next case may start',
    ])
  })

  it('releases a failed scenario exactly once and preserves its error', async () => {
    const original = new Error('Scenario assertion failed')
    const cleanup = vi.fn().mockResolvedValue(undefined)

    await expect(
      withWazzupCaseCleanup(async () => {
        throw original
      }, cleanup),
    ).rejects.toBe(original)
    expect(cleanup).toHaveBeenCalledTimes(1)
  })

  it('does not turn a cleanup failure after a successful scenario into a pass', async () => {
    const cleanupFailure = new Error('Held HTTP request did not settle')
    await expect(
      withWazzupCaseCleanup(
        async () => 'verified',
        async () => {
          throw cleanupFailure
        },
      ),
    ).rejects.toBe(cleanupFailure)
  })

  it('reports cleanup failure without masking the original scenario error', async () => {
    const original = new Error('Scenario assertion failed')
    const cleanupFailure = new Error('Held HTTP request did not settle')
    const report = vi
      .fn()
      .mockRejectedValue(new Error('Attachment unavailable'))

    await expect(
      withWazzupCaseCleanup(
        async () => {
          throw original
        },
        async () => {
          throw cleanupFailure
        },
        report,
      ),
    ).rejects.toBe(original)
    expect(report).toHaveBeenCalledExactlyOnceWith(cleanupFailure)
  })
})
