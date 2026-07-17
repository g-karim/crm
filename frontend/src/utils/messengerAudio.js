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
    result.push(Math.round(chunk.reduce((sum, value) => sum + value, 0) / chunk.length))
  }
  return result
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
