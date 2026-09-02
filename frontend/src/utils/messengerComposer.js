export function createComposerAttachmentController(options) {
  let items = []
  let handledPasteEvents = new WeakMap()
  let frozen = false
  let generation = 0

  function notify() {
    options.onChange?.([...items])
  }

  async function uploadItem(item) {
    if (frozen) return
    let uploadGeneration = generation
    item.status = 'uploading'
    item.progress = 0
    item.error = ''
    notify()
    try {
      let uploadedFile = await options.upload(item.file, (progress) => {
        if (item.discarded || uploadGeneration !== generation) return
        item.progress = Math.max(0, Math.min(Number(progress || 0), 100))
        notify()
      })
      if (item.discarded || uploadGeneration !== generation) {
        await discardFiles([uploadedFile?.name], item.scope).catch(() => {})
        return
      }
      item.uploadedFile = uploadedFile
      item.status = 'uploaded'
      item.progress = 100
    } catch (error) {
      item.status = 'failed'
      item.error = uploadErrorMessage(error)
    }
    notify()
  }

  function addFiles(fileList) {
    if (frozen) return []
    let files = Array.from(fileList || []).filter(Boolean)
    let maxFiles = Number(
      typeof options.maxFiles === 'function'
        ? options.maxFiles()
        : options.maxFiles || 10,
    )
    let validation = options.validateFiles?.(files, [...items]) || {}
    if (validation.error) {
      options.onError?.(validation.error)
      return []
    }
    files = validation.files || files
    let available = Math.max(maxFiles - items.length, 0)
    if (files.length > available) {
      options.onError?.(
        translate('You can select at most {0} attachments.', [maxFiles]),
      )
      return []
    }
    if (!files.length) return []

    let added = files.map((file) => {
      let isImage = file.type?.startsWith('image/')
      let item = {
        id: makeId(),
        file,
        fileName: file.name,
        mimeType: file.type || '',
        sizeBytes: file.size || 0,
        previewUrl: isImage ? options.createObjectURL?.(file) || '' : '',
        status: 'queued',
        progress: 0,
        error: '',
        uploadedFile: null,
        scope: options.scope?.(),
      }
      items.push(item)
      return item
    })
    notify()
    added.forEach((item) => uploadItem(item))
    return added
  }

  async function remove(id) {
    if (frozen) return
    let item = items.find((candidate) => candidate.id === id)
    if (!item) return
    item.discarded = true
    if (item.previewUrl) options.revokeObjectURL?.(item.previewUrl)
    items = items.filter((candidate) => candidate.id !== id)
    notify()
    await discardFiles([item.uploadedFile?.name], item.scope).catch(() => {})
  }

  function retry(id) {
    if (frozen) return
    let item = items.find((candidate) => candidate.id === id)
    if (!item || item.status !== 'failed') return
    return uploadItem(item)
  }

  function release() {
    generation += 1
    items.forEach((item) => {
      if (item.previewUrl) options.revokeObjectURL?.(item.previewUrl)
    })
    items = []
    frozen = false
    notify()
  }

  async function discard() {
    let discardedItems = [...items]
    items.forEach((item) => (item.discarded = true))
    release()
    let groups = new Map()
    discardedItems.forEach((item) => {
      if (!item.uploadedFile?.name) return
      let names = groups.get(item.scope) || []
      names.push(item.uploadedFile.name)
      groups.set(item.scope, names)
    })
    await Promise.allSettled(
      [...groups].map(([scope, fileNames]) => discardFiles(fileNames, scope)),
    )
  }

  function freeze() {
    if (items.some((item) => item.status !== 'uploaded')) return null
    frozen = true
    notify()
    return items.map((item) => item.uploadedFile?.name).filter(Boolean)
  }

  function unfreeze() {
    frozen = false
    notify()
  }

  function retargetScope(scope) {
    items.forEach((item) => {
      item.scope = scope
    })
    notify()
  }

  async function discardFiles(fileNames, scope) {
    fileNames = [...new Set((fileNames || []).filter(Boolean))]
    if (fileNames.length) await options.discard?.(fileNames, scope)
  }

  function handlePaste(event) {
    if (frozen) return false
    if (event && typeof event === 'object' && handledPasteEvents.has(event)) {
      return handledPasteEvents.get(event)
    }
    let files = Array.from(event?.clipboardData?.items || [])
      .filter((item) => item.kind === 'file')
      .map((item) => item.getAsFile())
      .filter((file) => file?.type?.startsWith('image/'))
    if (!files.length) {
      if (event && typeof event === 'object')
        handledPasteEvents.set(event, false)
      return false
    }
    if (event && typeof event === 'object') handledPasteEvents.set(event, true)
    event.preventDefault()
    addFiles(files)
    return true
  }

  function handleDrop(event) {
    if (frozen) return false
    let files = Array.from(event?.dataTransfer?.files || [])
    if (!files.length) return false
    event.preventDefault()
    addFiles(files)
    return true
  }

  return {
    addFiles,
    remove,
    retry,
    discard,
    release,
    freeze,
    unfreeze,
    retargetScope,
    handlePaste,
    handleDrop,
    getItems: () => [...items],
    getScopes: () => [
      ...new Set(items.map((item) => item.scope).filter(Boolean)),
    ],
    isFrozen: () => frozen,
    hasBlockingItems: () => items.some((item) => item.status !== 'uploaded'),
    readyFileNames: () =>
      items
        .filter((item) => item.status === 'uploaded')
        .map((item) => item.uploadedFile?.name)
        .filter(Boolean),
  }
}

export async function retargetComposerTemporaryFiles(
  call,
  { sourceConversation = '', targetConversation = '', files = [] } = {},
) {
  files = [...new Set((files || []).filter(Boolean))]
  if (!files.length) return { ok: true, retargeted: [] }
  if (!sourceConversation || !targetConversation) {
    throw new Error(
      translate('Could not identify the attachment conversation.'),
    )
  }
  let result = await call(
    'crm_messenger.api.attachments.retarget_temporary_files',
    {
      source_conversation: sourceConversation,
      target_conversation: targetConversation,
      files,
    },
  )
  if (!result?.ok) {
    throw new Error(
      result?.message ||
        translate('Could not move attachments to the selected conversation.'),
    )
  }
  return result
}

export function validateComposerFileMix(files, existing, context = {}) {
  if (!context.supportsAttachments) {
    return {
      files: [],
      error: translate('The selected channel does not support attachments.'),
    }
  }
  let combined = [...existing.map((item) => item.file), ...files].filter(
    Boolean,
  )
  let maxFiles = Number(
    context.maxAttachmentCount || (context.channelType === 'max' ? 12 : 10),
  )
  if (combined.length > maxFiles) {
    return {
      files: [],
      error: translate('You can select at most {0} attachments.', [maxFiles]),
    }
  }
  if (context.channelType !== 'max') return { files }

  let mediaFlags = combined.map(
    (file) => isImageFile(file) || isVideoFile(file),
  )
  let valid =
    (mediaFlags.every(Boolean) && combined.length <= maxFiles) ||
    (combined.length === 1 && !mediaFlags[0])
  if (valid) return { files }
  return {
    files: [],
    error: translate(
      'MAX supports up to {0} images or videos, or one file or audio attachment without mixing types.',
      [maxFiles],
    ),
  }
}

export function isImageFile(file = {}) {
  return (
    file.type?.startsWith('image/') ||
    /\.(png|jpe?g|gif|webp|heic)$/i.test(file.name || '')
  )
}

export function isVideoFile(file = {}) {
  return (
    ['video/mp4', 'video/webm', 'video/quicktime'].includes(file.type) ||
    /\.(mp4|webm|mov)$/i.test(file.name || '')
  )
}

function makeId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function uploadErrorMessage(error) {
  if (error?.messages?.[0]) return error.messages[0]
  if (error?.message) return error.message
  if (error?._server_messages) {
    try {
      return JSON.parse(JSON.parse(error._server_messages)[0]).message
    } catch {
      return translate('Could not upload the file.')
    }
  }
  return translate('Could not upload the file.')
}

function translate(message, values = []) {
  if (globalThis.__) return globalThis.__(message, values)
  return message.replace(/{(\d+)}/g, (match, index) => values[index] ?? match)
}
