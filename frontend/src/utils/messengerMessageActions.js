const API_PREFIX = 'crm_messenger.api.messages'
const EDITOR_SCROLL_MARGIN = 16
const DELETE_UNKNOWN_MESSAGE =
  'The message deletion result is unknown. Automatic retry is disabled.'
const EDIT_UNKNOWN_MESSAGE =
  'The message editing result is unknown. Automatic retry is disabled.'
const DELETE_UNCONFIRMED_MESSAGE = 'Could not confirm deletion'
const DELETE_IDENTITY_FIELDS = [
  'name',
  'provider',
  'conversation',
  'channel',
  'external_message_id',
  'external_chat_id',
]

export function getMessengerMessageActions(
  message = {},
  { deleteBlocked = false, editBlocked = false } = {},
) {
  let actions = []
  if (message.can_reply) actions.push('reply')
  if (canRetryMessengerMessage(message)) actions.push('retry')
  if (canEditMessengerMessage(message, editBlocked, deleteBlocked))
    actions.push('edit')
  if (canRetryDeleteMessengerMessage(message, deleteBlocked, editBlocked))
    actions.push('retry_delete')
  else if (canDeleteMessengerMessage(message, deleteBlocked, editBlocked))
    actions.push('delete')
  return actions
}

export function canEditMessengerMessage(
  message = {},
  editBlocked = false,
  deleteBlocked = false,
) {
  return Boolean(
    message?.can_edit &&
    !editBlocked &&
    !deleteBlocked &&
    message.status !== 'deleted' &&
    !['pending', 'unknown', 'deleted'].includes(message.delete_state) &&
    !['pending', 'unknown'].includes(message.edit_state) &&
    (message.provider !== 'wazzup' ||
      (message.message_type === 'text' && !message.attachments?.length)),
  )
}

export function canDeleteMessengerMessage(
  message = {},
  deleteBlocked = false,
  editBlocked = false,
) {
  return Boolean(
    message?.can_delete &&
    !deleteBlocked &&
    !editBlocked &&
    message.status !== 'deleted' &&
    !['pending', 'unknown', 'deleted'].includes(message.delete_state) &&
    !(
      isPartnerMessengerMessage(message) && message.delete_state === 'failed'
    ) &&
    !['pending', 'unknown'].includes(message.edit_state),
  )
}

export function isPartnerMessengerMessage(message = {}) {
  let mode =
    message.channel_info?.wazzup_api_mode || message.channel_info?.api_mode
  return message.provider === 'wazzup' && mode === 'partner_api_v2'
}

export function canRetryDeleteMessengerMessage(
  message = {},
  deleteBlocked = false,
  editBlocked = false,
) {
  return Boolean(
    isPartnerMessengerMessage(message) &&
    message.can_retry_delete === true &&
    Number(message.delete_retry_attempts_remaining) > 0 &&
    message.modified &&
    !deleteBlocked &&
    !editBlocked &&
    message.status !== 'deleted' &&
    ['unknown', 'failed'].includes(message.delete_state) &&
    !['pending', 'unknown'].includes(message.edit_state),
  )
}

export function getMessengerDeleteRetryConfirmation(message = {}) {
  return {
    title: 'Retry deletion?',
    message:
      message.delete_state === 'unknown'
        ? 'The previous attempt may already have deleted this message. Confirm to send another deletion request for the same message.'
        : 'Retry deleting this message for all participants? CRM will keep a deletion marker if deletion is confirmed.',
  }
}

export function makeMessengerDeleteRetryRequestId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  if (!globalThis.crypto?.getRandomValues) return ''
  let bytes = globalThis.crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 15) | 64
  bytes[8] = (bytes[8] & 63) | 128
  let hex = [...bytes]
    .map((value) => value.toString(16).padStart(2, '0'))
    .join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export function getMessengerMessageDeleteNotice(
  message = {},
  localUnknown = false,
) {
  if (message.status === 'deleted') return ''
  if (isPartnerMessengerMessage(message)) {
    if (message.delete_state === 'unknown' || localUnknown)
      return DELETE_UNCONFIRMED_MESSAGE
    if (message.delete_state === 'pending') return 'Deleting message...'
  }
  if (message.delete_state === 'unknown') return DELETE_UNKNOWN_MESSAGE
  if (message.delete_state === 'pending')
    return 'Message deletion is pending. Refresh messages to check its status.'
  return ''
}

export function getMessengerMessageEditNotice(message = {}) {
  if (message.status === 'deleted') return ''
  if (message.edit_state === 'unknown') return EDIT_UNKNOWN_MESSAGE
  if (message.edit_state === 'pending')
    return 'Message editing is pending. Refresh messages to check its status.'
  return ''
}

export function canRetryMessengerMessage(message = {}) {
  if (!message?.can_retry) return false
  return !(
    ['vk_direct', 'wazzup'].includes(message.provider) &&
    (message.delivery_status || message.status) === 'unknown'
  )
}

export function getMessengerMessageDisplay(message = {}) {
  return {
    tombstone: message.status === 'deleted',
    edited: message.status !== 'deleted' && Boolean(message.is_edited),
    text: message.status === 'deleted' ? '' : message.text || '',
  }
}

export function getMessengerRetryConfirmation(message = {}) {
  if (message?.provider === 'avito_direct') {
    return {
      title: 'Retry sending?',
      message:
        'Avito may have accepted the message, but CRM did not receive a definitive result. Retrying may create a duplicate.',
    }
  }
  if (message?.provider === 'vk_direct') {
    return {
      title: 'Retry sending?',
      message:
        'VK may have already accepted the message. Retrying may create a duplicate.',
    }
  }
  return {
    title: 'Retry sending?',
    message:
      'The provider may have accepted the message, but CRM did not receive a definitive result. Retrying may create a duplicate.',
  }
}

export function canSaveMessengerMessageEdit(
  message = {},
  draft = '',
  { editBlocked = false, deleteBlocked = false } = {},
) {
  if (!canEditMessengerMessage(message, editBlocked, deleteBlocked))
    return false
  let text = `${draft || ''}`.trim()
  if (text === `${message.text || ''}`.trim()) return false
  let maxLength = Number(message.edit_max_length || 0)
  if (maxLength > 0 && text.length > maxLength) return false
  if (text) return true
  return Boolean(message.can_edit_empty)
}

export async function openMessengerMessageEditor(message, options) {
  if (!options.startEdit(message)) return false
  await options.nextTick()

  let editor = options.getEditorElement(message.name)
  let textarea = editor?.querySelector?.('textarea')
  revealMessengerEditor(options.scrollContainer(), editor, textarea)
  return true
}

export function revealMessengerEditor(scrollContainer, editor, textarea) {
  if (!scrollContainer || !editor) {
    textarea?.focus?.({ preventScroll: true })
    return false
  }

  let viewport = scrollContainer.getBoundingClientRect()
  let bounds = editor.getBoundingClientRect()
  let delta = 0
  if (bounds.top < viewport.top) {
    delta = bounds.top - viewport.top - EDITOR_SCROLL_MARGIN
  } else if (bounds.bottom > viewport.bottom) {
    delta = bounds.bottom - viewport.bottom + EDITOR_SCROLL_MARGIN
  }

  if (delta) {
    scrollContainer.scrollTop = Math.max(
      0,
      (scrollContainer.scrollTop || 0) + delta,
    )
  }
  textarea?.focus?.({ preventScroll: true })
  return Boolean(delta)
}

export function createMessengerMessageActions(options) {
  let state = initialState()
  let deleteAttempts = new Map()
  let deleteCooldowns = new Map()

  function notify() {
    options.onChange?.(getState())
  }

  function startEdit(message) {
    if (!canEditMessage(message) || state.pendingMessage) return false
    state.editingMessage = message.name
    state.draft = message.text || ''
    clearError(message.name)
    notify()
    return true
  }

  function setDraft(value) {
    state.draft = value || ''
    notify()
  }

  function cancelEdit() {
    if (state.pendingAction === 'edit') return false
    state.editingMessage = ''
    state.draft = ''
    notify()
    return true
  }

  async function saveEdit(message) {
    let text = state.draft.trim()
    if (!canEditMessage(message) || state.editingMessage !== message.name)
      return false
    if (text === `${message.text || ''}`.trim()) {
      cancelEdit()
      return true
    }
    if (!canSaveMessengerMessageEdit(message, text)) return false
    let ok = await run('edit', message, { text })
    if (ok) {
      state.editingMessage = ''
      state.draft = ''
      notify()
    }
    return ok
  }

  async function deleteMessage(message) {
    if (!canDeleteMessage(message)) return false
    return run('delete', message)
  }

  function canRetryDeleteMessage(message) {
    return canRetryDeleteMessengerMessage(
      message,
      state.blockedDeletes[message?.name],
      state.blockedEdits[message?.name],
    )
  }

  function getDeleteRetryAfterSeconds(message) {
    let now = (options.now || Date.now)()
    let seconds = Math.max(0, Number(message.delete_retry_after_seconds) || 0)
    let cooldown = deleteCooldowns.get(message.name)
    if (
      !cooldown ||
      cooldown.modified !== message.modified ||
      cooldown.seconds !== seconds
    ) {
      cooldown = {
        modified: message.modified,
        seconds,
        until: now + seconds * 1000,
      }
      deleteCooldowns.set(message.name, cooldown)
    }
    return Math.max(0, Math.ceil((cooldown.until - now) / 1000))
  }

  async function retryDeleteMessage(message, confirmed = false) {
    if (!confirmed || state.pendingMessage || !canRetryDeleteMessage(message))
      return false
    let current = options.getMessage
      ? options.getMessage(message.name)
      : message
    if (
      !current ||
      !canRetryDeleteMessage(current) ||
      !sameDeleteIdentity(message, current) ||
      current.modified !== message.modified ||
      getDeleteRetryAfterSeconds(current) > 0
    )
      return false
    let requestId = makeMessengerDeleteRetryRequestId()
    if (!requestId) return false
    return run('delete', current, {
      confirm_unknown_delete: current.delete_state === 'unknown' ? 1 : 0,
      delete_retry_request_id: requestId,
      expected_modified: current.modified,
    })
  }

  function canDeleteMessage(message) {
    return canDeleteMessengerMessage(
      message,
      state.blockedDeletes[message?.name],
      state.blockedEdits[message?.name],
    )
  }

  function canEditMessage(message) {
    return canEditMessengerMessage(
      message,
      state.blockedEdits[message?.name],
      state.blockedDeletes[message?.name],
    )
  }

  function reconcileEditStates(messages = []) {
    let changed = false
    for (let message of messages) {
      if (
        !state.blockedEdits[message.name] ||
        !['failed', 'succeeded'].includes(message.edit_state) ||
        message.can_edit !== true
      )
        continue
      delete state.blockedEdits[message.name]
      clearError(message.name)
      changed = true
    }
    if (changed) notify()
  }

  function reconcileDeleteStates(messages = []) {
    let changed = false
    for (let message of messages) {
      if (canRetryDeleteMessengerMessage(message))
        getDeleteRetryAfterSeconds(message)
      let attempt = deleteAttempts.get(message.name)
      let freshRetry =
        canRetryDeleteMessengerMessage(message) &&
        attempt?.modified &&
        sameDeleteIdentity(attempt.message, message) &&
        `${message.modified}`.localeCompare(`${attempt.modified}`) >= 0
      let freshFailure =
        message.delete_state === 'failed' &&
        message.can_delete === true &&
        attempt?.modified &&
        message.delete_requested_at &&
        message.delete_requested_at !== attempt.requestedAt &&
        message.modified &&
        `${message.modified}`.localeCompare(`${attempt.modified}`) > 0
      if (
        state.blockedDeletes[message.name] !== 'unknown' ||
        (!freshRetry && !freshFailure)
      )
        continue
      delete state.blockedDeletes[message.name]
      deleteAttempts.delete(message.name)
      clearError(message.name)
      changed = true
    }
    if (changed) notify()
  }

  async function retryMessage(message, confirmUnknown = false) {
    if (!canRetryMessengerMessage(message)) return false
    return run('retry_outbound', message, {
      confirm_unknown: confirmUnknown ? 1 : 0,
    })
  }

  async function run(action, message, extra = {}) {
    if (state.pendingMessage) return false
    state.pendingMessage = message.name
    state.pendingAction = action
    clearError(message.name)
    notify()
    let wazzupDelete = action === 'delete' && message.provider === 'wazzup'
    let deleteAttempt = {
      modified: message.modified,
      requestedAt: message.delete_requested_at,
      message: Object.fromEntries(
        DELETE_IDENTITY_FIELDS.map((field) => [field, message[field]]),
      ),
    }
    let wazzupEdit = action === 'edit' && message.provider === 'wazzup'
    let definitiveFailure = false
    let accepted = false
    try {
      let method =
        action === 'retry_outbound'
          ? 'retry_outbound_message'
          : `${action}_message`
      let result = await options.call(`${API_PREFIX}.${method}`, {
        message: message.name,
        ...extra,
      })
      definitiveFailure = Boolean(
        result?.ok === false &&
        result.reason &&
        result.reason !== 'unknown_result' &&
        !result.unknown_result,
      )
      if (!result?.ok) throw providerError(result, action)
      accepted = true
      if (wazzupDelete) state.blockedDeletes[message.name] = 'deleted'
      if (wazzupEdit) state.blockedEdits[message.name] = 'succeeded'
      await options.sync()
      return true
    } catch (error) {
      let unknownMutation =
        (wazzupDelete || wazzupEdit) && !accepted && !definitiveFailure
      if (unknownMutation) {
        if (wazzupDelete) {
          state.blockedDeletes[message.name] = 'unknown'
          deleteAttempts.set(message.name, deleteAttempt)
        } else state.blockedEdits[message.name] = 'unknown'
        state.errors[message.name] = wazzupDelete
          ? isPartnerMessengerMessage(message)
            ? DELETE_UNCONFIRMED_MESSAGE
            : DELETE_UNKNOWN_MESSAGE
          : EDIT_UNKNOWN_MESSAGE
        // A lost RPC response may hide a durable pending/unknown state. Fetch
        // only the local delta; never dispatch another provider mutation.
        try {
          await options.sync()
        } catch {
          // Keep the original ambiguity notice when refresh also fails.
        }
      } else {
        state.errors[message.name] =
          error?.messages?.[0] || error?.message || fallbackMessage(action)
        if (
          wazzupDelete &&
          isPartnerMessengerMessage(message) &&
          definitiveFailure
        ) {
          try {
            await options.sync()
          } catch {
            // An explicit refresh can fetch the latest retry budget later.
          }
        }
      }
      if (state.errors[message.name])
        options.onError?.(state.errors[message.name], error)
      return false
    } finally {
      state.pendingMessage = ''
      state.pendingAction = ''
      notify()
    }
  }

  function getState() {
    return {
      ...state,
      errors: { ...state.errors },
      blockedDeletes: { ...state.blockedDeletes },
      blockedEdits: { ...state.blockedEdits },
    }
  }

  function clearError(messageName) {
    if (!messageName || !state.errors[messageName]) return
    let errors = { ...state.errors }
    delete errors[messageName]
    state.errors = errors
  }

  return {
    startEdit,
    setDraft,
    cancelEdit,
    saveEdit,
    canEditMessage,
    reconcileEditStates,
    canDeleteMessage,
    canRetryDeleteMessage,
    getDeleteRetryAfterSeconds,
    reconcileDeleteStates,
    deleteMessage,
    retryDeleteMessage,
    retryMessage,
    getState,
  }
}

function sameDeleteIdentity(expected, current) {
  if (!expected || !current) return false
  return DELETE_IDENTITY_FIELDS.every(
    (field) => expected[field] === current[field],
  )
}

function initialState() {
  return {
    editingMessage: '',
    draft: '',
    pendingMessage: '',
    pendingAction: '',
    errors: {},
    blockedDeletes: {},
    blockedEdits: {},
  }
}

function providerError(result, action) {
  let error = new Error(result?.message || fallbackMessage(action))
  error.reason = result?.reason
  error.unknownResult = Boolean(result?.unknown_result)
  return error
}

function fallbackMessage(action) {
  if (action === 'retry_outbound') return 'Could not retry sending the message.'
  return action === 'edit'
    ? 'Could not edit the message.'
    : 'Could not delete the message for everyone.'
}
