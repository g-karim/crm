// Device IDs are preferences, never audio, customer data or SIP credentials.
export function microphoneConstraints(deviceId = '') {
  return deviceId ? { deviceId: { exact: deviceId } } : true
}

export function readAudioPreferences(storage, user) {
  try {
    const value = JSON.parse(storage.getItem(`crm:call-audio:${user}`))
    return {
      input: typeof value?.input === 'string' ? value.input : '',
      output: typeof value?.output === 'string' ? value.output : '',
    }
  } catch {
    return { input: '', output: '' }
  }
}
export function saveAudioPreferences(storage, user, value) {
  try {
    storage.setItem(
      `crm:call-audio:${user}`,
      JSON.stringify({ input: value.input, output: value.output }),
    )
  } catch {
    // Restricted storage must not prevent using the devices in this tab.
  }
}

// Explicit, local-only level check. stop() also cancels a pending permission prompt.
export function createMicrophoneCheck({
  mediaDevices = navigator.mediaDevices,
  AudioContextClass = globalThis.AudioContext,
  frame = requestAnimationFrame,
  cancelFrame = cancelAnimationFrame,
  onLevel = () => {},
  onState = () => {},
  timeoutMs = 20000,
} = {}) {
  let version = 0,
    stream,
    context,
    source,
    animation,
    deadline
  function stop() {
    version++
    clearTimeout(deadline)
    if (animation != null) cancelFrame(animation)
    animation = null
    source?.disconnect()
    source = null
    stream?.getTracks().forEach((track) => track.stop())
    stream = null
    context?.close().catch(() => {})
    context = null
    onLevel(0)
    onState('idle')
  }
  async function start(deviceId = '') {
    stop()
    const current = version
    onState('requesting')
    deadline = setTimeout(stop, timeoutMs)
    let next
    try {
      next = await mediaDevices.getUserMedia({
        audio: microphoneConstraints(deviceId),
        video: false,
      })
      if (version !== current) {
        next.getTracks().forEach((track) => track.stop())
        return
      }
      stream = next
      context = new AudioContextClass()
      const local = context
      source = context.createMediaStreamSource(stream)
      const analyser = context.createAnalyser()
      analyser.fftSize = 256
      source.connect(analyser) // Never connect the microphone to the speakers.
      await context.resume()
      if (version !== current) return
      const samples = new Uint8Array(analyser.fftSize)
      onState('checking')
      function measure() {
        if (version !== current || local.state === 'closed') return
        analyser.getByteTimeDomainData(samples)
        const rms = Math.sqrt(
          samples.reduce((sum, x) => sum + ((x - 128) / 128) ** 2, 0) /
            samples.length,
        )
        onLevel(Math.min(100, Math.round(rms * 300)))
        animation = frame(measure)
      }
      measure()
    } catch (error) {
      if (version !== current) return
      stop()
      throw error
    }
  }
  return { start, stop }
}

// A short generated WAV for an explicit speaker check; no fetch or recording.
export function speakerTestWave() {
  const rate = 16000,
    count = rate
  const bytes = new ArrayBuffer(44 + count * 2)
  const view = new DataView(bytes)
  const write = (offset, value) =>
    [...value].forEach((char, i) =>
      view.setUint8(offset + i, char.charCodeAt(0)),
    )
  write(0, 'RIFF')
  view.setUint32(4, 36 + count * 2, true)
  write(8, 'WAVE')
  write(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, rate, true)
  view.setUint32(28, rate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  write(36, 'data')
  view.setUint32(40, count * 2, true)
  for (let i = 0; i < count; i++) {
    const time = i / rate
    const envelope = Math.min(time * 30, (1 - time) * 30, 1)
    view.setInt16(
      44 + i * 2,
      Math.sin(2 * Math.PI * (time < 0.5 ? 440 : 660) * time) * envelope * 4500,
      true,
    )
  }
  return new Blob([bytes], { type: 'audio/wav' })
}
