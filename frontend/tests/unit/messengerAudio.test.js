import {
  clampAudioFraction,
  downsampleWaveform,
  formatAudioTime,
  normalizeAudioVolume,
  sanitizeWaveform,
} from '@/utils/messengerAudio'
import { describe, expect, it } from 'vitest'

describe('messenger audio player helpers', () => {
  it('sanitizes provider waveform values', () => {
    expect(sanitizeWaveform([-1, 12.4, 999, 'bad', 64])).toEqual([
      0, 12, 255, 64,
    ])
  })

  it('downsamples without analyzing audio content', () => {
    let waveform = Array.from({ length: 128 }, (_, index) => index * 2)
    let result = downsampleWaveform(waveform, 32)
    expect(result).toHaveLength(32)
    expect(result[0]).toBeGreaterThanOrEqual(0)
    expect(result.at(-1)).toBeLessThanOrEqual(255)
    expect(downsampleWaveform([], 32)).toEqual([])
  })

  it('formats time and clamps seek and volume', () => {
    expect(formatAudioTime(0)).toBe('0:00')
    expect(formatAudioTime(65.9)).toBe('1:05')
    expect(clampAudioFraction(-1)).toBe(0)
    expect(clampAudioFraction(1.5)).toBe(1)
    expect(normalizeAudioVolume(-0.1)).toBe(0)
    expect(normalizeAudioVolume(0.45)).toBe(0.45)
    expect(normalizeAudioVolume(4)).toBe(1)
  })
})
