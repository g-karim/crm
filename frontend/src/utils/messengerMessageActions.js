const API_PREFIX = 'crm_messenger.api.messages'
const EDITOR_SCROLL_MARGIN = 16

export function getMessengerMessageActions(message = {}) {
  let actions = []
  if (message.can_edit) actions.push('edit')
  if (message.can_delete) actions.push('delete')
  return actions
}

export function getMessengerMessageDisplay(message = {}) {
  return {
    tombstone: message.status === 'deleted',
    edited: message.status !== 'deleted' && Boolean(message.is_edited),
    text: message.status === 'deleted' ? '' : message.text || '',
  }
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

  function notify() {
    options.onChange?.({ ...state, errors: { ...state.errors } })
  }

  function startEdit(message) {
    if (!message?.can_edit || state.pendingMessage) return false
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
    if (!message?.can_edit || state.editingMessage !== message.name || !text)
      return false
    if (text === `${message.text || ''}`.trim()) {
      cancelEdit()
      return true
    }
    let ok = await run('edit', message, { text })
    if (ok) {
      state.editingMessage = ''
      state.draft = ''
      notify()
    }
    return ok
  }

  async function deleteMessage(message) {
    if (!message?.can_delete) return false
    return run('delete', message)
  }

  async function run(action, message, extra = {}) {
    if (state.pendingMessage) return false
    state.pendingMessage = message.name
    state.pendingAction = action
    clearError(message.name)
    notify()
    try {
      let result = await options.call(`${API_PREFIX}.${action}_message`, {
        message: message.name,
        ...extra,
      })
      if (!result?.ok) throw providerError(result, action)
      await options.sync()
      return true
    } catch (error) {
      state.errors[message.name] =
        error?.messages?.[0] || error?.message || fallbackMessage(action)
      options.onError?.(state.errors[message.name], error)
      return false
    } finally {
      state.pendingMessage = ''
      state.pendingAction = ''
      notify()
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
    deleteMessage,
    getState: () => ({ ...state, errors: { ...state.errors } }),
  }
}

function initialState() {
  return {
    editingMessage: '',
    draft: '',
    pendingMessage: '',
    pendingAction: '',
    errors: {},
  }
}

function providerError(result, action) {
  let error = new Error(result?.message || fallbackMessage(action))
  error.reason = result?.reason
  error.unknownResult = Boolean(result?.unknown_result)
  return error
}

function fallbackMessage(action) {
  return action === 'edit'
    ? 'Не удалось отредактировать сообщение.'
    : 'Не удалось удалить сообщение для всех.'
}
