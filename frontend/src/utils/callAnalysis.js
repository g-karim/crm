export function parseCallAnalysisItems(value) {
  if (Array.isArray(value)) return cleanItems(value)
  if (typeof value !== 'string' || !value.trim()) return []
  try {
    return cleanItems(JSON.parse(value))
  } catch {
    return []
  }
}

function cleanItems(value) {
  if (!Array.isArray(value)) return []
  return value
    .map((item) => String(item || '').trim())
    .filter(Boolean)
    .slice(0, 12)
}

export function callAnalysisStatus(status) {
  const states = {
    Queued: { label: 'Queued', theme: 'gray', running: true },
    Processing: { label: 'Analyzing', theme: 'blue', running: true },
    Completed: { label: 'Completed', theme: 'green', running: false },
    Failed: { label: 'Failed', theme: 'red', running: false },
  }
  return states[status] || { label: '', theme: 'gray', running: false }
}
