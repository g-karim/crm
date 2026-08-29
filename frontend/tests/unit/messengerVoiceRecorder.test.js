import {
  createMessengerVoiceRecorder,
  sanitizeVoiceWaveform,
  selectVoiceRecorderMime,
  voiceLevelFromTimeDomain,
  voiceRecorderError,
} from '@/utils/messengerVoiceRecorder'
import { describe, expect, it, vi } from 'vitest'

describe('messenger voice recorder', () => {
  it('selects the first actually supported Opus format', () => {
    let MediaRecorderClass = {
      isTypeSupported: vi.fn((mime) => mime === 'audio/webm;codecs=opus'),
    }
    expect(selectVoiceRecorderMime(MediaRecorderClass)).toBe(
      'audio/webm;codecs=opus',
    )
    expect(MediaRecorderClass.isTypeSupported).toHaveBeenCalledWith(
      'audio/ogg;codecs=opus',
    )
  })

  it('requests permission only after start and cleans the preview', async () => {
    let track = { stop: vi.fn() }
    let getUserMedia = vi.fn(async () => ({
      getTracks: () => [track],
    }))
    let revoked = []
    let states = []
    let recorder = createMessengerVoiceRecorder({
      mediaDevices: { getUserMedia },
      MediaRecorderClass: FakeMediaRecorder,
      AudioContextClass: null,
      createObjectURL: () => 'blob:voice',
      revokeObjectURL: (url) => revoked.push(url),
      setIntervalFn: () => 1,
      clearIntervalFn: vi.fn(),
      onChange: (state) => states.push(state),
    })

    expect(getUserMedia).not.toHaveBeenCalled()
    await recorder.start()
    expect(getUserMedia).toHaveBeenCalledWith({ audio: true })
    FakeMediaRecorder.last.emit(new Blob(['voice']))
    recorder.stop()

    expect(recorder.getSnapshot().state).toBe('preview')
    expect(recorder.getSnapshot().mimeType).toBe('audio/ogg;codecs=opus')
    expect(track.stop).toHaveBeenCalled()

    recorder.reset()
    expect(revoked).toEqual(['blob:voice'])
    expect(recorder.getSnapshot().state).toBe('idle')
    expect(states.map((state) => state.state)).toContain('recording')
  })

  it('closes a late permission stream after cancellation', async () => {
    let resolvePermission
    let track = { stop: vi.fn() }
    let getUserMedia = vi.fn(
      () =>
        new Promise((resolve) => {
          resolvePermission = resolve
        }),
    )
    let recorder = createMessengerVoiceRecorder({
      mediaDevices: { getUserMedia },
      MediaRecorderClass: FakeMediaRecorder,
      AudioContextClass: null,
    })

    let pending = recorder.start()
    recorder.reset()
    resolvePermission({ getTracks: () => [track] })
    await pending

    expect(track.stop).toHaveBeenCalledOnce()
    expect(recorder.getSnapshot().state).toBe('idle')
  })

  it('stops and rejects a recording that crosses the size limit', async () => {
    let track = { stop: vi.fn() }
    let recorder = createMessengerVoiceRecorder({
      maxSizeBytes: 3,
      mediaDevices: {
        getUserMedia: vi.fn(async () => ({ getTracks: () => [track] })),
      },
      MediaRecorderClass: FakeMediaRecorder,
      AudioContextClass: null,
      setIntervalFn: () => 1,
      clearIntervalFn: vi.fn(),
    })

    await recorder.start()
    FakeMediaRecorder.last.emit(new Blob(['four']))

    expect(recorder.getSnapshot().state).toBe('error')
    expect(recorder.getSnapshot().error).toContain('допустимый размер')
    expect(track.stop).toHaveBeenCalled()
  })

  it('sanitizes/downsamples waveform and maps permission errors', () => {
    expect(sanitizeVoiceWaveform([-20, 20, 300], 3)).toEqual([0, 20, 255])
    expect(sanitizeVoiceWaveform(Array(512).fill(100), 256)).toHaveLength(256)
    expect(voiceRecorderError({ name: 'NotAllowedError' })).toContain(
      'запрещён',
    )
    expect(voiceRecorderError({ name: 'NotFoundError' })).toContain('не найден')
  })

  it('uses an absolute noise-gated level for the live waveform', () => {
    expect(voiceLevelFromTimeDomain(new Uint8Array(32).fill(128))).toBe(0)
    expect(voiceLevelFromTimeDomain(Uint8Array.from([127, 128, 129]))).toBe(0)
    expect(voiceLevelFromTimeDomain(Uint8Array.from([64, 192]))).toBe(255)
  })

  it('freezes analyser samples while paused and resumes with a new sample', async () => {
    let time = 0
    let frames = []
    let recorder = createMessengerVoiceRecorder({
      mediaDevices: {
        getUserMedia: vi.fn(async () => ({ getTracks: () => [] })),
      },
      MediaRecorderClass: FakeMediaRecorder,
      AudioContextClass: FakeAudioContext,
      now: () => time,
      requestAnimationFrameFn: (callback) => {
        frames.push(callback)
        return frames.length
      },
      cancelAnimationFrameFn: vi.fn(),
      setIntervalFn: () => 1,
      clearIntervalFn: vi.fn(),
    })

    await recorder.start()
    runNextFrame(frames)
    expect(recorder.getSnapshot().waveform).toHaveLength(1)

    recorder.pause()
    time += 100
    runNextFrame(frames)
    expect(recorder.getSnapshot().waveform).toHaveLength(1)

    recorder.resume()
    runNextFrame(frames)
    expect(recorder.getSnapshot().waveform).toHaveLength(2)
    recorder.reset()
  })
})

function runNextFrame(frames) {
  frames.shift()?.()
}

class FakeAudioContext {
  createAnalyser() {
    return {
      fftSize: 0,
      getByteTimeDomainData(data) {
        data.fill(128)
        data[0] = 96
      },
    }
  }

  createMediaStreamSource() {
    return { connect: vi.fn() }
  }

  close() {}
}

class FakeMediaRecorder {
  static last

  static isTypeSupported(mime) {
    return mime === 'audio/ogg;codecs=opus'
  }

  constructor(_stream, { mimeType }) {
    this.mimeType = mimeType
    this.state = 'inactive'
    FakeMediaRecorder.last = this
  }

  start(timeslice) {
    this.timeslice = timeslice
    this.state = 'recording'
  }

  pause() {
    this.state = 'paused'
  }

  resume() {
    this.state = 'recording'
  }

  stop() {
    this.state = 'inactive'
    this.onstop?.()
  }

  emit(data) {
    this.ondataavailable?.({ data })
  }
}
