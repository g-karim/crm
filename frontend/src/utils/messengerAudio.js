export function sanitizeWaveform(values = []) {
  if (!Array.isArray(values)) return []
  return values
    .slice(0, 256)
    .map((value) => Number(value))
    .filter(Number.isFinite)
    .map((value) => Math.max(0, Math.min(Math.round(value), 255)))
}

export function downsampleWaveform(values = [], target = 64) {
  let samples = sanitizeWaveform(values)
  target = Math.max(1, Math.floor(Number(target) || 1))
  if (samples.length <= target) return samples
  let result = []
  for (let index = 0; index < target; index += 1) {
    let start = Math.floor((index * samples.length) / target)
    let end = Math.max(Math.floor(((index + 1) * samples.length) / target), start + 1)
    let chunk = samples.slice(start, end)
    result.push(Math.max(...chunk))
  }
  return result
}

export function normalizeWaveform(values = []) {
  let samples = sanitizeWaveform(values)
  if (!samples.length) return []
  let peak = Math.max(...samples)
  if (!peak) return samples.map(() => 0)
  return samples.map((value) => value / peak)
}

export function prepareWaveform(values = [], target = 64) {
  return normalizeWaveform(downsampleWaveform(values, target))
}

export function formatAudioTime(seconds) {
  seconds = Math.max(Math.floor(Number(seconds) || 0), 0)
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export function clampAudioFraction(value) {
  return Math.max(0, Math.min(Number(value) || 0, 1))
}

export function normalizeAudioVolume(value) {
  return Math.max(0, Math.min(Number(value) || 0, 1))
}

export function audioFractionFromPointer(event, target = event?.currentTarget) {
  let bounds = target?.getBoundingClientRect?.()
  if (!bounds?.width) return null
  return clampAudioFraction((Number(event?.clientX) - bounds.left) / bounds.width)
}

export function createAudioSeekDrag(onSeek) {
  let pointerId = null
  let target = null

  function seek(event) {
    let fraction = audioFractionFromPointer(event, target)
    if (fraction !== null) onSeek(fraction)
  }

  function releasePointer() {
    if (pointerId === null || !target) return
    try {
      if (!target.hasPointerCapture || target.hasPointerCapture(pointerId)) {
        target.releasePointerCapture?.(pointerId)
      }
    } catch {
      // Capture may already have been released by the browser.
    }
    pointerId = null
    target = null
  }

  function pointerDown(event) {
    if (pointerId !== null || event.isPrimary === false) return
    if (event.pointerType === 'mouse' && event.button !== 0) return
    pointerId = event.pointerId
    target = event.currentTarget
    try {
      target?.setPointerCapture?.(pointerId)
    } catch {
      // Seeking still works when capture is unavailable.
    }
    seek(event)
  }

  function pointerMove(event) {
    if (event.pointerId !== pointerId) return
    seek(event)
  }

  function pointerUp(event) {
    if (event.pointerId !== pointerId) return
    seek(event)
    releasePointer()
  }

  function pointerCancel(event) {
    if (event.pointerId !== pointerId) return
    releasePointer()
  }

  return {
    pointerDown,
    pointerMove,
    pointerUp,
    pointerCancel,
    cancel: releasePointer,
  }
}
