// Segment text is rendered as text nodes, never provider-supplied markup.
export function transcriptMatches(segments, query) {
  const value = String(query || '')
    .trim()
    .toLocaleLowerCase()
  return segments.filter((segment) =>
    String(segment.text || '')
      .toLocaleLowerCase()
      .includes(value),
  )
}

export function transcriptTimestamp(value) {
  if (!Number.isFinite(value) || value < 0) return '—'
  const seconds = Math.floor(value)
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export function absoluteRecordingSeek(target, duration) {
  if (
    !Number.isFinite(target) ||
    target < 0 ||
    !Number.isFinite(duration) ||
    duration <= 0
  )
    return null
  return Math.min(target, duration)
}
