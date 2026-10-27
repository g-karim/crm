import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  createMicrophoneCheck,
  microphoneConstraints,
  readAudioPreferences,
  saveAudioPreferences,
  speakerTestWave,
} from '@/utils/telephonyAudio'

describe('call audio preferences', () => {
  it('uses the default microphone or the exact selected device', () => {
    expect(microphoneConstraints()).toBe(true)
    expect(microphoneConstraints('usb')).toEqual({ deviceId: { exact: 'usb' } })
  })
  it('keeps only device IDs per user and tolerates restricted or corrupt storage', () => {
    const storage = { getItem: vi.fn(() => '{bad'), setItem: vi.fn() }
    expect(readAudioPreferences(storage, 'user')).toEqual({
      input: '',
      output: '',
    })
    storage.getItem.mockReturnValue(
      '{"input":"mic","output":42,"password":"secret"}',
    )
    expect(readAudioPreferences(storage, 'user')).toEqual({
      input: 'mic',
      output: '',
    })
    saveAudioPreferences(storage, 'user', {
      input: 'mic',
      output: 'usb',
      password: 'secret',
    })
    expect(storage.setItem).toHaveBeenCalledWith(
      'crm:call-audio:user',
      '{"input":"mic","output":"usb"}',
    )
    expect(readAudioPreferences(undefined, 'user')).toEqual({
      input: '',
      output: '',
    })
    expect(() => saveAudioPreferences(undefined, 'user', {})).not.toThrow()
  })
  it('generates a finite local WAV without requesting audio or fetching a file', async () => {
    const blob = speakerTestWave()
    expect(blob.type).toBe('audio/wav')
    expect(blob.size).toBe(32044)
    const view = new DataView(await blob.arrayBuffer())
    expect(view.getUint32(24, true)).toBe(16000)
    expect(view.getUint32(40, true)).toBe(32000)
    expect(view.getInt16(44 + 100 * 2, true)).not.toBe(0)
  })
})

describe('explicit microphone level check', () => {
  let check
  afterEach(() => {
    check?.stop()
    vi.useRealTimers()
  })
  function setup(getUserMedia) {
    const stop = vi.fn(),
      stream = { getTracks: () => [{ stop }] }
    const analyser = {
      fftSize: 0,
      getByteTimeDomainData: vi.fn((values) => values.fill(150)),
    }
    const source = { connect: vi.fn(), disconnect: vi.fn() }
    const ctx = {
      state: 'running',
      createMediaStreamSource: vi.fn(() => source),
      createAnalyser: () => analyser,
      resume: vi.fn().mockResolvedValue(),
      close: vi.fn().mockResolvedValue(),
    }
    const mediaDevices = {
      getUserMedia: getUserMedia || vi.fn().mockResolvedValue(stream),
    }
    const frame = vi.fn(() => 7),
      cancelFrame = vi.fn(),
      onLevel = vi.fn(),
      onState = vi.fn()
    check = createMicrophoneCheck({
      mediaDevices,
      AudioContextClass: class {
        constructor() {
          return ctx
        }
      },
      frame,
      cancelFrame,
      onLevel,
      onState,
    })
    return {
      stream,
      stop,
      source,
      ctx,
      mediaDevices,
      frame,
      cancelFrame,
      onLevel,
      onState,
    }
  }
  it('does not capture until explicitly started, measures locally and cleans every resource', async () => {
    const t = setup()
    expect(t.mediaDevices.getUserMedia).not.toHaveBeenCalled()
    await check.start('usb')
    expect(t.mediaDevices.getUserMedia).toHaveBeenCalledWith({
      audio: { deviceId: { exact: 'usb' } },
      video: false,
    })
    expect(t.onState).toHaveBeenLastCalledWith('checking')
    expect(t.onLevel.mock.lastCall[0]).toBeGreaterThan(0)
    check.stop()
    expect(t.stop).toHaveBeenCalledOnce()
    expect(t.source.disconnect).toHaveBeenCalledOnce()
    expect(t.ctx.close).toHaveBeenCalledOnce()
    expect(t.cancelFrame).toHaveBeenCalledWith(7)
    expect(t.onLevel).toHaveBeenLastCalledWith(0)
  })
  it('stops late permission resolution without constructing audio context', async () => {
    let resolve
    const t = setup(
      vi.fn(
        () =>
          new Promise((yes) => {
            resolve = yes
          }),
      ),
    )
    const pending = check.start()
    check.stop()
    resolve(t.stream)
    await pending
    expect(t.stop).toHaveBeenCalledOnce()
    expect(t.ctx.createMediaStreamSource).not.toHaveBeenCalled()
    expect(t.frame).not.toHaveBeenCalled()
  })
  it('automatically releases the microphone after twenty seconds', async () => {
    vi.useFakeTimers()
    const t = setup()
    await check.start()
    vi.advanceTimersByTime(20000)
    expect(t.stop).toHaveBeenCalledOnce()
    expect(t.onState).toHaveBeenLastCalledWith('idle')
  })
  it('reports denied permission and can retry', async () => {
    const t = setup(vi.fn().mockRejectedValueOnce(new Error('denied')))
    await expect(check.start()).rejects.toThrow('denied')
    expect(t.onState).toHaveBeenLastCalledWith('idle')
    t.mediaDevices.getUserMedia.mockResolvedValue(t.stream)
    await check.start()
    expect(t.onState).toHaveBeenLastCalledWith('checking')
  })
})
