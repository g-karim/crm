export function createComposerAttachmentController(options) {
  let items = []
  let handledPasteEvents = new WeakMap()

  function notify() {
    options.onChange?.([...items])
  }

  async function uploadItem(item) {
    item.status = 'uploading'
    item.progress = 0
    item.error = ''
    notify()
    try {
      let uploadedFile = await options.upload(item.file, (progress) => {
        item.progress = Math.max(0, Math.min(Number(progress || 0), 100))
        notify()
      })
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
    let files = Array.from(fileList || []).filter(Boolean)
    let available = Math.max((options.maxFiles || 10) - items.length, 0)
    if (files.length > available) {
      options.onError?.('Можно выбрать не более 10 вложений.')
    }
    let validation = options.validateFiles?.(files, [...items]) || {}
    if (validation.error) options.onError?.(validation.error)
    files = validation.files || files
    files = files.slice(0, available)
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
      }
      items.push(item)
      return item
    })
    notify()
    added.forEach((item) => uploadItem(item))
    return added
  }

  function remove(id) {
    let item = items.find((candidate) => candidate.id === id)
    if (!item) return
    if (item.previewUrl) options.revokeObjectURL?.(item.previewUrl)
    items = items.filter((candidate) => candidate.id !== id)
    notify()
  }

  function retry(id) {
    let item = items.find((candidate) => candidate.id === id)
    if (!item || item.status !== 'failed') return
    return uploadItem(item)
  }

  function clear() {
    items.forEach((item) => {
      if (item.previewUrl) options.revokeObjectURL?.(item.previewUrl)
    })
    items = []
    notify()
  }

  function handlePaste(event) {
    if (event && typeof event === 'object' && handledPasteEvents.has(event)) {
      return handledPasteEvents.get(event)
    }
    let files = Array.from(event?.clipboardData?.items || [])
      .filter((item) => item.kind === 'file')
      .map((item) => item.getAsFile())
      .filter((file) => file?.type?.startsWith('image/'))
    if (!files.length) {
      if (event && typeof event === 'object') handledPasteEvents.set(event, false)
      return false
    }
    if (event && typeof event === 'object') handledPasteEvents.set(event, true)
    event.preventDefault()
    addFiles(files)
    return true
  }

  function handleDrop(event) {
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
    clear,
    handlePaste,
    handleDrop,
    getItems: () => [...items],
    hasBlockingItems: () =>
      items.some((item) => item.status !== 'uploaded'),
    readyFileNames: () =>
      items
        .filter((item) => item.status === 'uploaded')
        .map((item) => item.uploadedFile?.name)
        .filter(Boolean),
  }
}

export function validateComposerFileMix(files, existing, context = {}) {
  if (!context.supportsAttachments) {
    return { files: [], error: 'Выбранный канал не поддерживает вложения.' }
  }
  let combined = [
    ...existing.map((item) => item.file),
    ...files,
  ].filter(Boolean)
  if (context.channelType !== 'max') return { files }

  let imageFlags = combined.map(isImageFile)
  let valid =
    (imageFlags.every(Boolean) && combined.length <= 10) ||
    (combined.length === 1 && !imageFlags[0])
  if (valid) return { files }
  return {
    files: [],
    error:
      'MAX поддерживает до 10 изображений либо один файл/аудио без смешивания.',
  }
}

export function isImageFile(file = {}) {
  return (
    file.type?.startsWith('image/') ||
    /\.(png|jpe?g|gif|webp|heic)$/i.test(file.name || '')
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
      return 'Не удалось загрузить файл.'
    }
  }
  return 'Не удалось загрузить файл.'
}
