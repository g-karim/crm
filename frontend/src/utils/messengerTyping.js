const DEFAULT_INTERVAL_MS = 4000

export function createMessengerTypingController(options = {}) {
  let lastSentAt = 0
  let context = ''
  let generation = 0

  function reset() {
    lastSentAt = 0
    context = ''
    generation += 1
  }

  function input({ text = '', conversation = '', enabled = false } = {}) {
    let nextContext = String(conversation || '')
    if (!enabled || !nextContext || !String(text || '').trim()) {
      reset()
      return false
    }
    if (context !== nextContext) {
      lastSentAt = 0
      context = nextContext
      generation += 1
    }

    let now = Number(options.now?.() ?? Date.now())
    let interval = Number(options.intervalMs || DEFAULT_INTERVAL_MS)
    if (lastSentAt && now - lastSentAt < interval) return false

    lastSentAt = now
    let requestGeneration = generation
    Promise.resolve(options.send?.(nextContext)).catch(() => {
      // Typing is ephemeral and must never surface as a composer error.
      if (requestGeneration !== generation) return
    })
    return true
  }

  return { input, reset }
}
