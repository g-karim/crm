import {
  audioFractionFromPointer,
  clampAudioFraction,
  createAudioSeekDrag,
  downsampleWaveform,
  formatAudioTime,
  normalizeWaveform,
  normalizeAudioVolume,
  prepareWaveform,
  sanitizeWaveform,
} from '@/utils/messengerAudio'
import { vkVoiceAttachment } from '../fixtures/vkVoiceAttachment'
import { describe, expect, it } from 'vitest'

describe('messenger audio player helpers', () => {
  it('sanitizes provider waveform values', () => {
    expect(sanitizeWaveform([-1, 12.4, 999, 'bad', 64])).toEqual([
      0, 12, 255, 64,
    ])
  })

  it('preserves peaks while downsampling provider data', () => {
    expect(downsampleWaveform([1, 2, 80, 3, 4, 5, 6, 7], 2)).toEqual([
      80, 7,
    ])
  })

  it('normalizes low-amplitude recordings by their actual peak', () => {
    expect(normalizeWaveform([0, 2, 4, 8])).toEqual([0, 0.25, 0.5, 1])

    let bars = prepareWaveform(vkVoiceAttachment.waveform, 64)
    expect(bars).toHaveLength(64)
    expect(Math.max(...bars)).toBe(1)
    expect(new Set(bars).size).toBeGreaterThan(10)
  })

  it('keeps the range fallback for missing waveform data', () => {
    expect(prepareWaveform()).toEqual([])
    expect(prepareWaveform(null)).toEqual([])
    expect(prepareWaveform(['bad'])).toEqual([])
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

  it('supports the complete pointer drag lifecycle in both directions', () => {
    let fractions = []
    let captured = null
    let target = {
      getBoundingClientRect: () => ({ left: 100, width: 200 }),
      setPointerCapture: vi.fn((pointerId) => (captured = pointerId)),
      hasPointerCapture: vi.fn((pointerId) => captured === pointerId),
      releasePointerCapture: vi.fn(() => (captured = null)),
    }
    let drag = createAudioSeekDrag((fraction) => fractions.push(fraction))

    drag.pointerDown(pointerEvent(target, 7, 140))
    drag.pointerMove(pointerEvent(target, 7, 260))
    drag.pointerMove(pointerEvent(target, 7, 180))
    drag.pointerUp(pointerEvent(target, 7, 200))
    drag.pointerMove(pointerEvent(target, 7, 220))

    expect(fractions).toEqual([0.2, 0.8, 0.4, 0.5])
    expect(target.setPointerCapture).toHaveBeenCalledWith(7)
    expect(target.releasePointerCapture).toHaveBeenCalledWith(7)
  })

  it('releases capture and stops seeking on pointercancel', () => {
    let onSeek = vi.fn()
    let target = pointerTarget()
    let drag = createAudioSeekDrag(onSeek)

    drag.pointerDown(pointerEvent(target, 4, 25))
    drag.pointerCancel(pointerEvent(target, 4, 75))
    drag.pointerMove(pointerEvent(target, 4, 90))

    expect(onSeek).toHaveBeenCalledTimes(1)
    expect(target.releasePointerCapture).toHaveBeenCalledWith(4)
  })

  it('clamps pointer coordinates outside the waveform', () => {
    let target = pointerTarget()
    expect(audioFractionFromPointer({ clientX: -50 }, target)).toBe(0)
    expect(audioFractionFromPointer({ clientX: 150 }, target)).toBe(1)
    expect(
      audioFractionFromPointer(
        { clientX: 50 },
        { getBoundingClientRect: () => ({ left: 0, width: 0 }) },
      ),
    ).toBeNull()
  })
})

function pointerTarget() {
  let captured = null
  return {
    getBoundingClientRect: () => ({ left: 0, width: 100 }),
    setPointerCapture: vi.fn((pointerId) => (captured = pointerId)),
    hasPointerCapture: vi.fn((pointerId) => captured === pointerId),
    releasePointerCapture: vi.fn(() => (captured = null)),
  }
}

function pointerEvent(target, pointerId, clientX) {
  return {
    currentTarget: target,
    pointerId,
    clientX,
    pointerType: 'mouse',
    button: 0,
    isPrimary: true,
  }
}
