import { describe, expect, it } from 'vitest'
import {
  absoluteRecordingSeek,
  transcriptMatches,
  transcriptTimestamp,
} from '../../src/utils/callInsights'

describe('transcript navigation', () => {
  it('searches literal unicode text without treating input as a regex or markup', () => {
    const rows = [
      { text: 'Отправить СЧЁТ' },
      { text: '<script>hello</script>' },
      { text: 'Стоимость [100]' },
    ]
    expect(transcriptMatches(rows, 'счёт')).toEqual([rows[0]])
    expect(transcriptMatches(rows, '[')).toEqual([rows[2]])
    expect(transcriptMatches(rows, '')).toEqual(rows)
    expect(transcriptMatches(rows, 'nothing')).toEqual([])
  })
  it('formats truthful timestamps and rejects invalid values', () => {
    expect(transcriptTimestamp(61.8)).toBe('1:01')
    expect(transcriptTimestamp(0)).toBe('0:00')
    expect(transcriptTimestamp(3601)).toBe('60:01')
    for (const value of [NaN, Infinity, -1, '20'])
      expect(transcriptTimestamp(value)).toBe('—')
  })
  it('never seeks to invalid metadata or beyond the recording', () => {
    expect(absoluteRecordingSeek(10, 30)).toBe(10)
    expect(absoluteRecordingSeek(40, 30)).toBe(30)
    expect(absoluteRecordingSeek(0, 30)).toBe(0)
    for (const [target, duration] of [
      [NaN, 30],
      [-1, 30],
      [10, NaN],
      [10, Infinity],
      [10, 0],
    ])
      expect(absoluteRecordingSeek(target, duration)).toBeNull()
  })
})
