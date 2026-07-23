export const VOICE_MIME_CANDIDATES = [
  'audio/ogg;codecs=opus',
  'audio/webm;codecs=opus',
  'audio/mp4;codecs=mp4a.40.2',
  'audio/mp4',
]

const WAVEFORM_SAMPLE_INTERVAL_MS = 80
const MAX_CAPTURE_WAVEFORM_SAMPLES = 4096

export function selectVoiceRecorderMime(
  MediaRecorderClass = globalThis.MediaRecorder,
) {
  if (!MediaRecorderClass?.isTypeSupported) return ''
  return (
    VOICE_MIME_CANDIDATES.find((mime) =>
      MediaRecorderClass.isTypeSupported(mime),
    ) || ''
  )
}

export function sanitizeVoiceWaveform(values = [], limit = 256) {
  if (!Array.isArray(values) || !values.length) return []
  let bucketSize = Math.max(1, values.length / Math.max(1, limit))
  let output = []
  for (let offset = 0; offset < values.length; offset += bucketSize) {
    let start = Math.floor(offset)
    let end = Math.max(start + 1, Math.floor(offset + bucketSize))
    let bucket = values.slice(start, end)
    let value =
      bucket.reduce((sum, item) => sum + Number(item || 0), 0) / bucket.length
    output.push(Math.max(0, Math.min(255, Math.round(value))))
  }
  return output.slice(0, limit)
}

export function voiceLevelFromTimeDomain(values = []) {
  if (!values?.length) return 0
  let squareSum = 0
  for (let value of values) {
    let centered = Number(value) - 128
    squareSum += centered * centered
  }
  let rms = Math.sqrt(squareSum / values.length)
  if (!Number.isFinite(rms) || rms < 2) return 0
  return Math.max(0, Math.min(255, Math.round((rms - 2) * 10)))
}

export function voiceRecorderError(error) {
  let name = error?.name || ''
  if (name === 'NotAllowedError' || name === 'SecurityError')
    return 'Доступ к микрофону запрещён.'
  if (name === 'NotFoundError') return 'Микрофон не найден.'
  if (name === 'NotReadableError' || name === 'AbortError')
    return 'Микрофон занят или недоступен.'
  return error?.message || 'Не удалось начать запись.'
}

export function createMessengerVoiceRecorder({
  maxDurationMs = 300000,
  maxSizeBytes = 10 * 1024 * 1024,
  onChange = () => {},
  mediaDevices = globalThis.navigator?.mediaDevices,
  MediaRecorderClass = globalThis.MediaRecorder,
  AudioContextClass = globalThis.AudioContext || globalThis.webkitAudioContext,
  createObjectURL = (blob) => URL.createObjectURL(blob),
  revokeObjectURL = (url) => URL.revokeObjectURL(url),
  now = () => performance.now(),
  setIntervalFn = globalThis.setInterval,
  clearIntervalFn = globalThis.clearInterval,
  requestAnimationFrameFn = globalThis.requestAnimationFrame,
  cancelAnimationFrameFn = globalThis.cancelAnimationFrame,
} = {}) {
  let snapshot = {
    state: 'idle',
    durationMs: 0,
    sizeBytes: 0,
    waveform: [],
    blob: null,
    url: '',
    mimeType: '',
    error: '',
    canPause: false,
  }
  let recorder = null
  let stream = null
  let audioContext = null
  let analyser = null
  let chunks = []
  let startedAt = 0
  let accumulatedMs = 0
  let timer = null
  let animationFrame = null
  let waveformSamples = []
  let lastWaveformSampleAt = Number.NEGATIVE_INFINITY
  let generation = 0

  function publish(values = {}) {
    snapshot = { ...snapshot, ...values }
    onChange({ ...snapshot })
  }

  async function start() {
    if (!['idle', 'error'].includes(snapshot.state)) return
    generation += 1
    let requestGeneration = generation
    clearPreview()
    waveformSamples = []
    lastWaveformSampleAt = Number.NEGATIVE_INFINITY
    let mimeType = selectVoiceRecorderMime(MediaRecorderClass)
    if (
      globalThis.isSecureContext === false &&
      globalThis.location?.hostname !== 'localhost'
    ) {
      publish({
        state: 'error',
        error: 'Для записи микрофона требуется HTTPS.',
      })
      return
    }
    if (!mediaDevices?.getUserMedia || !MediaRecorderClass || !mimeType) {
      publish({
        state: 'error',
        error: 'Запись голосовых не поддерживается этим браузером.',
      })
      return
    }
    publish({
      state: 'requesting_permission',
      durationMs: 0,
      sizeBytes: 0,
      waveform: [],
      blob: null,
      url: '',
      error: '',
    })
    try {
      let requestedStream = await mediaDevices.getUserMedia({ audio: true })
      if (requestGeneration !== generation) {
        requestedStream.getTracks().forEach((track) => track.stop())
        return
      }
      stream = requestedStream
      recorder = new MediaRecorderClass(stream, { mimeType })
      chunks = []
      accumulatedMs = 0
      startedAt = now()
      recorder.ondataavailable = ({ data }) => {
        if (!data?.size) return
        chunks.push(data)
        let sizeBytes = chunks.reduce((sum, item) => sum + item.size, 0)
        publish({ sizeBytes })
        if (sizeBytes >= maxSizeBytes) stop()
      }
      recorder.onerror = (event) => fail(event.error || event)
      recorder.onstop = finish
      startAnalyser()
      recorder.start(1000)
      timer = setIntervalFn(updateDuration, 200)
      publish({
        state: 'recording',
        mimeType: recorder.mimeType || mimeType,
        canPause:
          typeof recorder.pause === 'function' &&
          typeof recorder.resume === 'function',
      })
    } catch (error) {
      fail(error)
    }
  }

  function pause() {
    if (snapshot.state !== 'recording' || !snapshot.canPause) return
    try {
      accumulatedMs += now() - startedAt
      recorder.pause()
      publish({ state: 'paused', durationMs: Math.round(accumulatedMs) })
    } catch (error) {
      fail(error)
    }
  }

  function resume() {
    if (snapshot.state !== 'paused' || !snapshot.canPause) return
    try {
      recorder.resume()
      startedAt = now()
      lastWaveformSampleAt = Number.NEGATIVE_INFINITY
      publish({ state: 'recording' })
    } catch (error) {
      fail(error)
    }
  }

  function stop() {
    if (!['recording', 'paused'].includes(snapshot.state)) return
    if (snapshot.state === 'recording') accumulatedMs += now() - startedAt
    publish({ state: 'stopping', durationMs: Math.round(accumulatedMs) })
    clearTimer()
    if (recorder?.state !== 'inactive') recorder.stop()
  }

  function finish() {
    let blob = new Blob(chunks, {
      type: recorder?.mimeType || snapshot.mimeType,
    })
    let finalWaveform = sanitizeVoiceWaveform(waveformSamples)
    stopCapture()
    if (!blob.size || blob.size > maxSizeBytes) {
      chunks = []
      publish({
        state: 'error',
        blob: null,
        url: '',
        error: 'Запись превысила допустимый размер.',
      })
      return
    }
    let url = createObjectURL(blob)
    publish({
      state: 'preview',
      blob,
      url,
      sizeBytes: blob.size,
      durationMs: Math.min(Math.round(accumulatedMs), maxDurationMs),
      waveform: finalWaveform,
      error: '',
    })
    chunks = []
    waveformSamples = []
  }

  function updateDuration() {
    if (snapshot.state !== 'recording') return
    let durationMs = accumulatedMs + now() - startedAt
    publish({ durationMs: Math.round(durationMs) })
    if (durationMs >= maxDurationMs) stop()
  }

  function startAnalyser() {
    if (!AudioContextClass) return
    try {
      audioContext = new AudioContextClass()
      analyser = audioContext.createAnalyser()
      analyser.fftSize = 256
      audioContext.createMediaStreamSource(stream).connect(analyser)
      let data = new Uint8Array(analyser.fftSize)
      let sample = () => {
        if (!analyser) return
        let sampleAt = now()
        if (
          snapshot.state === 'recording' &&
          sampleAt - lastWaveformSampleAt >= WAVEFORM_SAMPLE_INTERVAL_MS
        ) {
          analyser.getByteTimeDomainData(data)
          waveformSamples.push(voiceLevelFromTimeDomain(data))
          if (waveformSamples.length > MAX_CAPTURE_WAVEFORM_SAMPLES)
            waveformSamples.shift()
          lastWaveformSampleAt = sampleAt
          publish({ waveform: [...waveformSamples] })
        }
        animationFrame = requestAnimationFrameFn(sample)
      }
      animationFrame = requestAnimationFrameFn(sample)
    } catch {
      stopAnalyser()
    }
  }

  function setExternalState(state, error = '') {
    publish({ state, error })
  }

  function reset() {
    generation += 1
    stopCapture()
    clearPreview()
    chunks = []
    waveformSamples = []
    lastWaveformSampleAt = Number.NEGATIVE_INFINITY
    accumulatedMs = 0
    publish({
      state: 'idle',
      durationMs: 0,
      sizeBytes: 0,
      waveform: [],
      blob: null,
      url: '',
      mimeType: '',
      error: '',
      canPause: false,
    })
  }

  function fail(error) {
    generation += 1
    stopCapture()
    chunks = []
    waveformSamples = []
    publish({ state: 'error', error: voiceRecorderError(error) })
  }

  function stopCapture() {
    clearTimer()
    stopAnalyser()
    recorder && (recorder.ondataavailable = null)
    recorder && (recorder.onerror = null)
    recorder && (recorder.onstop = null)
    if (recorder?.state && recorder.state !== 'inactive') recorder.stop()
    stream?.getTracks().forEach((track) => track.stop())
    recorder = null
    stream = null
  }

  function stopAnalyser() {
    if (animationFrame != null) cancelAnimationFrameFn(animationFrame)
    animationFrame = null
    analyser = null
    audioContext?.close?.()
    audioContext = null
  }

  function clearTimer() {
    if (timer != null) clearIntervalFn(timer)
    timer = null
  }

  function clearPreview() {
    if (snapshot.url) revokeObjectURL(snapshot.url)
  }

  return {
    start,
    pause,
    resume,
    stop,
    reset,
    dispose: reset,
    setExternalState,
    getSnapshot: () => ({ ...snapshot }),
  }
}
