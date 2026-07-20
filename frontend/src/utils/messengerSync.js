const EVENT_NAME = 'crm_messenger:conversation_changed'
const REFERENCE_DOCTYPE = 'CRM Lead'

export function compareMessengerMessages(left = {}, right = {}) {
  return (
    compareValues(left.message_datetime, right.message_datetime) ||
    compareValues(left.creation, right.creation) ||
    compareValues(left.name, right.name)
  )
}

export function mergeMessengerMessages(current = [], incoming = []) {
  let byName = new Map()
  current.forEach((message) => {
    if (message?.name) byName.set(message.name, message)
  })

  let inserted = []
  let updated = []
  incoming.forEach((message) => {
    if (!message?.name) return
    if (byName.has(message.name)) updated.push(message.name)
    else inserted.push(message.name)
    byName.set(message.name, message)
  })

  return {
    messages: [...byName.values()].sort(compareMessengerMessages),
    inserted,
    updated,
  }
}

export function createMessengerSyncController(options) {
  let socket = options.socket
  let call = options.call
  let visibilityTarget = options.visibilityTarget
  let leadName = ''
  let messages = []
  let syncCursor = ''
  let beforeCursor = ''
  let hasMoreHistory = false
  let started = false
  let generation = 0
  let deltaPromise = null
  let deltaRequested = false
  let historyPromise = null

  function api(method, params) {
    return call(`crm_messenger.api.messages.${method}`, params)
  }

  function scopeParams(extra = {}) {
    return {
      reference_doctype: REFERENCE_DOCTYPE,
      reference_name: leadName,
      ...extra,
    }
  }

  function notify(kind, merge = {}, extra = {}) {
    options.onChange?.({
      kind,
      messages,
      inserted: merge.inserted || [],
      updated: merge.updated || [],
      hasMoreHistory,
      ...extra,
    })
  }

  function merge(incoming, kind, extra) {
    options.onBeforeChange?.({ kind, incoming, messages })
    let result = mergeMessengerMessages(messages, incoming)
    messages = result.messages
    notify(kind, result, extra)
    return result
  }

  function subscribe(name) {
    if (name) socket?.emit('doc_subscribe', REFERENCE_DOCTYPE, name)
  }

  function unsubscribe(name) {
    if (name) socket?.emit('doc_unsubscribe', REFERENCE_DOCTYPE, name)
  }

  async function loadSnapshot({ reset = true } = {}) {
    if (!leadName) return
    let requestGeneration = generation
    let requestedLead = leadName
    let result = await api(
      'get_message_page',
      scopeParams({ limit: 100 }),
    )
    if (requestGeneration !== generation || requestedLead !== leadName) return
    if (result?.contract_version !== 1 || !result?.sync_cursor) {
      throw new Error('Unsupported messenger snapshot response.')
    }

    if (reset) messages = []
    syncCursor = result.sync_cursor
    beforeCursor = result.page?.before_cursor || ''
    hasMoreHistory = Boolean(result.page?.has_more && beforeCursor)
    merge(result.messages || [], 'snapshot', { reset })

    if (deltaRequested) await syncDelta()
  }

  async function loadOlder() {
    if (!leadName || !hasMoreHistory || !beforeCursor) return
    if (historyPromise) return historyPromise
    let requestGeneration = generation
    let requestedLead = leadName
    let requestedCursor = beforeCursor
    historyPromise = api(
      'get_message_page',
      scopeParams({ limit: 100, before_cursor: requestedCursor }),
    )
      .then((result) => {
        if (
          requestGeneration !== generation ||
          requestedLead !== leadName ||
          requestedCursor !== beforeCursor
        )
          return
        if (result?.contract_version !== 1) {
          throw new Error('Unsupported messenger history response.')
        }
        beforeCursor = result.page?.before_cursor || ''
        hasMoreHistory = Boolean(result.page?.has_more && beforeCursor)
        merge(result.messages || [], 'history')
      })
      .finally(() => {
        historyPromise = null
      })
    return historyPromise
  }

  async function drainDelta(requestGeneration, requestedLead) {
    do {
      deltaRequested = false
      let hasMore = true
      while (hasMore) {
        let result = await api(
          'get_message_changes',
          scopeParams({ cursor: syncCursor, limit: 200 }),
        )
        if (requestGeneration !== generation || requestedLead !== leadName)
          return
        if (result?.contract_version !== 1 || !result?.next_cursor) {
          throw new Error('Unsupported messenger delta response.')
        }
        let merged = merge(result.changes || [], 'delta')
        syncCursor = result.next_cursor
        hasMore = Boolean(result.has_more)
        if (merged.inserted.length || merged.updated.length) {
          options.onDeltaApplied?.(merged, result.changes || [])
        }
      }
    } while (deltaRequested)
  }

  async function syncDelta() {
    if (!leadName || !syncCursor) {
      deltaRequested = true
      return
    }
    if (deltaPromise) {
      deltaRequested = true
      return deltaPromise
    }
    let requestGeneration = generation
    let requestedLead = leadName
    deltaPromise = drainDelta(requestGeneration, requestedLead)
      .catch(async (error) => {
        if (requestGeneration !== generation) return
        if (isCursorError(error)) {
          await loadSnapshot()
          return
        }
        options.onError?.(error)
        throw error
      })
      .finally(() => {
        deltaPromise = null
      })
    return deltaPromise
  }

  function onRealtime(payload = {}) {
    if (
      payload.version !== 1 ||
      payload.reference_doctype !== REFERENCE_DOCTYPE ||
      payload.reference_name !== leadName
    )
      return
    syncDelta().catch(() => {})
  }

  function onConnect() {
    if (!leadName) return
    subscribe(leadName)
    if (syncCursor) syncDelta().catch(() => {})
  }

  function onVisibilityChange() {
    if (visibilityTarget?.visibilityState === 'visible') {
      syncDelta().catch(() => {})
    }
  }

  async function setLead(nextLead) {
    nextLead = nextLead || ''
    if (nextLead === leadName && syncCursor) return
    let previousLead = leadName
    generation += 1
    leadName = nextLead
    messages = []
    syncCursor = ''
    beforeCursor = ''
    hasMoreHistory = false
    deltaRequested = false
    if (previousLead) unsubscribe(previousLead)
    if (!leadName) {
      notify('reset')
      return
    }
    subscribe(leadName)
    await loadSnapshot()
  }

  async function start(initialLead) {
    if (!started) {
      started = true
      socket?.on(EVENT_NAME, onRealtime)
      socket?.on('connect', onConnect)
      visibilityTarget?.addEventListener?.(
        'visibilitychange',
        onVisibilityChange,
      )
    }
    return setLead(initialLead)
  }

  function stop() {
    generation += 1
    unsubscribe(leadName)
    leadName = ''
    if (!started) return
    started = false
    socket?.off(EVENT_NAME, onRealtime)
    socket?.off('connect', onConnect)
    visibilityTarget?.removeEventListener?.(
      'visibilitychange',
      onVisibilityChange,
    )
  }

  return {
    start,
    stop,
    setLead,
    loadSnapshot,
    loadOlder,
    syncDelta,
    getMessages: () => messages,
    getCursor: () => syncCursor,
    hasMoreHistory: () => hasMoreHistory,
  }
}

function compareValues(left, right) {
  return `${left || ''}`.localeCompare(`${right || ''}`)
}

function isCursorError(error) {
  return (
    error?.exc_type === 'ValidationError' ||
    /cursor/i.test(error?.message || error?.messages?.[0] || '')
  )
}
