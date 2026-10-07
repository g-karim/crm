const EVENT_NAME = 'crm_messenger:conversation_changed'
const TYPING_EVENT_NAME = 'crm_messenger:typing'
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
    let existing = byName.get(message.name)
    if (existing && !shouldReplaceMessengerMessage(existing, message)) return
    if (existing) updated.push(message.name)
    else inserted.push(message.name)
    byName.set(message.name, message)
  })

  return {
    messages: [...byName.values()].sort(compareMessengerMessages),
    inserted,
    updated,
  }
}

export function countNewMessengerMessages({
  messages = [],
  inserted = [],
  previousLastMessage = null,
} = {}) {
  if (!previousLastMessage || !inserted.length) return 0
  let insertedNames = new Set(inserted)
  return messages.filter(
    (message) =>
      insertedNames.has(message?.name) &&
      message.direction === 'inbound' &&
      message.status !== 'deleted' &&
      message.ingest_source !== 'provider_history' &&
      compareMessengerMessages(message, previousLastMessage) > 0,
  ).length
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
  let deltaRequest = null
  let pendingDeltaGeneration = null
  let historyRequest = null
  let scopeReloadRequest = null
  let scopeReloadNeeded = false
  let snapshotRetryTimer = null
  let snapshotRetryDelay = 2000

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

  function notifyPermissions(result) {
    if (result?.permissions) options.onPermissions?.(result.permissions)
  }

  function merge(incoming, kind, extra) {
    let changeSnapshot = options.onBeforeChange?.({ kind, incoming, messages })
    let result = mergeMessengerMessages(messages, incoming)
    messages = result.messages
    notify(kind, result, { ...extra, changeSnapshot })
    return result
  }

  function subscribe(name) {
    if (name) socket?.emit('doc_subscribe', REFERENCE_DOCTYPE, name)
  }

  function unsubscribe(name) {
    if (name) socket?.emit('doc_unsubscribe', REFERENCE_DOCTYPE, name)
  }

  function clearSnapshotRetry() {
    clearTimeout(snapshotRetryTimer)
    snapshotRetryTimer = null
  }

  function scheduleSnapshotRetry(error) {
    if (
      ['PermissionError', 'AuthenticationError', 'DoesNotExistError'].includes(
        error?.exc_type,
      )
    )
      return
    clearSnapshotRetry()
    let requestGeneration = generation
    snapshotRetryTimer = setTimeout(() => {
      snapshotRetryTimer = null
      if (requestGeneration === generation && leadName)
        syncDelta().catch(() => {})
    }, snapshotRetryDelay)
    snapshotRetryDelay = Math.min(snapshotRetryDelay * 2, 30000)
  }

  async function loadSnapshot({ reset = true } = {}) {
    if (!leadName) return
    let requestGeneration = generation
    let requestedLead = leadName
    let result
    try {
      result = await api('get_message_page', scopeParams({ limit: 100 }))
    } catch (error) {
      if (requestGeneration !== generation || requestedLead !== leadName) return
      if (!syncCursor) {
        scopeReloadNeeded = true
        scheduleSnapshotRetry(error)
      }
      throw error
    }
    if (requestGeneration !== generation || requestedLead !== leadName) return
    if (result?.contract_version !== 1 || !result?.sync_cursor) {
      throw new Error('Unsupported messenger snapshot response.')
    }

    clearSnapshotRetry()
    snapshotRetryDelay = 2000
    notifyPermissions(result)
    scopeReloadNeeded = false
    if (reset) {
      let snapshotByName = new Map(
        (result.messages || []).map((message) => [message?.name, message]),
      )
      messages = messages.filter((message) => {
        let snapshotMessage = snapshotByName.get(message?.name)
        return (
          snapshotMessage &&
          !shouldReplaceMessengerMessage(message, snapshotMessage)
        )
      })
    }
    syncCursor = result.sync_cursor
    beforeCursor = result.page?.before_cursor || ''
    hasMoreHistory = Boolean(result.page?.has_more && beforeCursor)
    merge(result.messages || [], 'snapshot', { reset })

    if (pendingDeltaGeneration === requestGeneration) {
      pendingDeltaGeneration = null
      await syncDelta()
    }
  }

  async function loadOlder() {
    if (!leadName || !hasMoreHistory || !beforeCursor) return
    let requestGeneration = generation
    let requestedLead = leadName
    let requestedCursor = beforeCursor
    if (
      historyRequest?.generation === requestGeneration &&
      historyRequest?.lead === requestedLead
    )
      return historyRequest.promise
    let request = {
      generation: requestGeneration,
      lead: requestedLead,
      promise: null,
    }
    request.promise = api('get_message_page', {
      reference_doctype: REFERENCE_DOCTYPE,
      reference_name: requestedLead,
      limit: 100,
      before_cursor: requestedCursor,
    })
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
        notifyPermissions(result)
        beforeCursor = result.page?.before_cursor || ''
        hasMoreHistory = Boolean(result.page?.has_more && beforeCursor)
        merge(result.messages || [], 'history')
      })
      .finally(() => {
        if (historyRequest === request) historyRequest = null
      })
    historyRequest = request
    return request.promise
  }

  async function drainDelta(request) {
    do {
      request.requested = false
      let hasMore = true
      while (hasMore) {
        let requestedCursor = syncCursor
        let result = await api('get_message_changes', {
          reference_doctype: REFERENCE_DOCTYPE,
          reference_name: request.lead,
          cursor: requestedCursor,
          limit: 200,
        })
        if (request.generation !== generation || request.lead !== leadName)
          return
        if (result?.contract_version !== 1 || !result?.next_cursor) {
          throw new Error('Unsupported messenger delta response.')
        }
        notifyPermissions(result)
        let merged = merge(result.changes || [], 'delta')
        syncCursor = result.next_cursor
        hasMore = Boolean(result.has_more)
        if (merged.inserted.length || merged.updated.length) {
          options.onDeltaApplied?.(merged, result.changes || [])
        }
      }
    } while (request.requested)
  }

  async function syncDelta() {
    if (!leadName) return
    if (!syncCursor) {
      pendingDeltaGeneration = generation
      if (scopeReloadNeeded && !scopeReloadRequest) return reloadScope()
      return
    }
    let requestGeneration = generation
    let requestedLead = leadName
    if (
      deltaRequest?.generation === requestGeneration &&
      deltaRequest?.lead === requestedLead
    ) {
      deltaRequest.requested = true
      return deltaRequest.promise
    }
    let request = {
      generation: requestGeneration,
      lead: requestedLead,
      requested: false,
      promise: null,
    }
    request.promise = drainDelta(request)
      .catch(async (error) => {
        if (requestGeneration !== generation) return
        if (isCursorError(error)) {
          await loadSnapshot()
          if (request.requested) pendingDeltaGeneration = requestGeneration
          return
        }
        options.onError?.(error)
        throw error
      })
      .finally(() => {
        if (deltaRequest !== request) return
        deltaRequest = null
        if (
          pendingDeltaGeneration === requestGeneration &&
          requestGeneration === generation &&
          requestedLead === leadName &&
          syncCursor
        ) {
          pendingDeltaGeneration = null
          syncDelta().catch(() => {})
        }
      })
    deltaRequest = request
    return request.promise
  }

  function reloadScope() {
    if (!leadName) return
    if (
      scopeReloadRequest?.generation === generation &&
      scopeReloadRequest?.lead === leadName
    ) {
      scopeReloadRequest.requested = true
      return scopeReloadRequest.promise
    }

    clearSnapshotRetry()
    generation += 1
    let requestGeneration = generation
    let requestedLead = leadName
    scopeReloadNeeded = true
    syncCursor = ''
    beforeCursor = ''
    hasMoreHistory = false
    pendingDeltaGeneration = null
    let request = {
      generation: requestGeneration,
      lead: requestedLead,
      requested: false,
      promise: null,
    }
    request.promise = loadSnapshot()
      .catch((error) => {
        if (requestGeneration === generation && requestedLead === leadName) {
          options.onError?.(error)
        }
        throw error
      })
      .finally(() => {
        if (scopeReloadRequest !== request) return
        scopeReloadRequest = null
        if (
          request.requested &&
          requestGeneration === generation &&
          requestedLead === leadName
        ) {
          reloadScope()?.catch(() => {})
        }
      })
    scopeReloadRequest = request
    return request.promise
  }

  function onRealtime(payload = {}) {
    if (
      payload.version !== 1 ||
      payload.reference_doctype !== REFERENCE_DOCTYPE ||
      payload.reference_name !== leadName
    )
      return
    if (payload.conversation_state_changed || payload.scope_invalidated) {
      options.onConversationStateChanged?.(payload)
    }
    if (payload.scope_invalidated) {
      reloadScope()?.catch(() => {})
      return
    }
    syncDelta().catch(() => {})
  }

  function onTyping(payload = {}) {
    if (
      payload.version !== 1 ||
      payload.reference_doctype !== REFERENCE_DOCTYPE ||
      payload.reference_name !== leadName
    )
      return
    options.onTyping?.(payload)
  }

  function onConnect() {
    if (!leadName) return
    subscribe(leadName)
    syncDelta().catch(() => {})
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
    clearSnapshotRetry()
    snapshotRetryDelay = 2000
    generation += 1
    leadName = nextLead
    messages = []
    syncCursor = ''
    beforeCursor = ''
    hasMoreHistory = false
    pendingDeltaGeneration = null
    scopeReloadRequest = null
    scopeReloadNeeded = false
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
      socket?.on(TYPING_EVENT_NAME, onTyping)
      socket?.on('connect', onConnect)
      visibilityTarget?.addEventListener?.(
        'visibilitychange',
        onVisibilityChange,
      )
    }
    return setLead(initialLead)
  }

  function stop() {
    clearSnapshotRetry()
    generation += 1
    scopeReloadRequest = null
    scopeReloadNeeded = false
    unsubscribe(leadName)
    leadName = ''
    if (!started) return
    started = false
    socket?.off(EVENT_NAME, onRealtime)
    socket?.off(TYPING_EVENT_NAME, onTyping)
    socket?.off('connect', onConnect)
    visibilityTarget?.removeEventListener?.(
      'visibilitychange',
      onVisibilityChange,
    )
  }

  function mergeExternal(incoming) {
    return merge(Array.isArray(incoming) ? incoming : [incoming], 'external')
  }

  return {
    start,
    stop,
    setLead,
    loadSnapshot,
    loadOlder,
    syncDelta,
    mergeExternal,
    getMessages: () => messages,
    getCursor: () => syncCursor,
    hasMoreHistory: () => hasMoreHistory,
  }
}

function compareValues(left, right) {
  return `${left || ''}`.localeCompare(`${right || ''}`)
}

function shouldReplaceMessengerMessage(current, incoming) {
  let currentVersion = current?.modified
  let incomingVersion = incoming?.modified
  if (currentVersion && !incomingVersion) return false
  if (!currentVersion || !incomingVersion) return true
  return compareValues(incomingVersion, currentVersion) >= 0
}

function isCursorError(error) {
  return (
    error?.exc_type === 'ValidationError' ||
    /cursor/i.test(error?.message || error?.messages?.[0] || '')
  )
}
