import {
  createComposerAttachmentController,
  getComposerAttachmentPolicy,
  getComposerImageCaptionState,
  isVideoFile,
  retargetComposerTemporaryFiles,
  validateComposerFileMix,
} from '@/utils/messengerComposer'
import { describe, expect, it, vi } from 'vitest'

function file(name, type = 'application/octet-stream') {
  return new File(['content'], name, { type })
}

function harness(
  upload = vi.fn(async (value) => ({ name: `FILE-${value.name}` })),
) {
  let urls = []
  let revoked = []
  let changes = []
  let discard = vi.fn(async () => {})
  let controller = createComposerAttachmentController({
    upload,
    discard,
    scope: () => 'CONVERSATION-1',
    createObjectURL: (value) => {
      let url = `blob:${value.name}`
      urls.push(url)
      return url
    },
    revokeObjectURL: (url) => revoked.push(url),
    validateFiles: (files) => ({ files }),
    onChange: (items) => changes.push(items),
  })
  return { controller, upload, discard, urls, revoked, changes }
}

describe('messenger composer attachments', () => {
  it('recognizes VK document fallback video formats by MIME or extension', () => {
    expect(isVideoFile(file('clip.bin', 'video/mp4'))).toBe(true)
    expect(isVideoFile(file('clip.MOV'))).toBe(true)
    expect(isVideoFile(file('clip.avi', 'video/x-msvideo'))).toBe(false)
  })

  it('adds an image from clipboard and uploads it', async () => {
    let image = file('paste.png', 'image/png')
    let current = harness()
    let event = {
      clipboardData: {
        items: [{ kind: 'file', getAsFile: () => image }],
      },
      preventDefault: vi.fn(),
    }

    expect(current.controller.handlePaste(event)).toBe(true)
    await vi.waitFor(() =>
      expect(current.controller.getItems()[0].status).toBe('uploaded'),
    )
    expect(event.preventDefault).toHaveBeenCalledOnce()
    expect(current.urls).toEqual(['blob:paste.png'])
  })

  it('does not intercept ordinary text paste', () => {
    let current = harness()
    let event = {
      clipboardData: { items: [{ kind: 'string' }] },
      preventDefault: vi.fn(),
    }

    expect(current.controller.handlePaste(event)).toBe(false)
    expect(event.preventDefault).not.toHaveBeenCalled()
    expect(current.controller.getItems()).toEqual([])
  })

  it('handles the same bubbling paste event only once', async () => {
    let image = file('single.png', 'image/png')
    let current = harness()
    let event = {
      clipboardData: {
        items: [{ kind: 'file', getAsFile: () => image }],
      },
      preventDefault: vi.fn(),
    }

    expect(current.controller.handlePaste(event)).toBe(true)
    expect(current.controller.handlePaste(event)).toBe(true)
    await vi.waitFor(() =>
      expect(current.controller.readyFileNames()).toHaveLength(1),
    )
    expect(current.upload).toHaveBeenCalledOnce()
    expect(event.preventDefault).toHaveBeenCalledOnce()
  })

  it('treats two separate paste events as two attachments', async () => {
    let image = file('twice.png', 'image/png')
    let current = harness()
    let makeEvent = () => ({
      clipboardData: {
        items: [{ kind: 'file', getAsFile: () => image }],
      },
      preventDefault: vi.fn(),
    })

    current.controller.handlePaste(makeEvent())
    current.controller.handlePaste(makeEvent())
    await vi.waitFor(() =>
      expect(current.controller.readyFileNames()).toHaveLength(2),
    )
    expect(current.upload).toHaveBeenCalledTimes(2)
  })

  it('uses the same pipeline for drag-and-drop', async () => {
    let current = harness()
    let event = {
      dataTransfer: { files: [file('drop.pdf', 'application/pdf')] },
      preventDefault: vi.fn(),
    }

    expect(current.controller.handleDrop(event)).toBe(true)
    await vi.waitFor(() =>
      expect(current.controller.readyFileNames()).toEqual(['FILE-drop.pdf']),
    )
    expect(current.upload).toHaveBeenCalledOnce()
  })

  it('removes local state, revokes preview and discards the temporary File', async () => {
    let current = harness()
    let [item] = current.controller.addFiles([file('remove.png', 'image/png')])
    await vi.waitFor(() =>
      expect(current.controller.readyFileNames()).toHaveLength(1),
    )

    await current.controller.remove(item.id)

    expect(current.controller.getItems()).toEqual([])
    expect(current.revoked).toEqual(['blob:remove.png'])
    expect(current.discard).toHaveBeenCalledWith(
      ['FILE-remove.png'],
      'CONVERSATION-1',
    )
  })

  it('removes only the selected image from a multi-image draft', async () => {
    let current = harness()
    let [first] = current.controller.addFiles([
      file('first.png', 'image/png'),
      file('second.png', 'image/png'),
    ])
    await vi.waitFor(() =>
      expect(current.controller.readyFileNames()).toEqual([
        'FILE-first.png',
        'FILE-second.png',
      ]),
    )

    await current.controller.remove(first.id)

    expect(current.controller.readyFileNames()).toEqual(['FILE-second.png'])
    expect(current.controller.getItems().map((item) => item.fileName)).toEqual([
      'second.png',
    ])
    expect(current.revoked).toEqual(['blob:first.png'])
    expect(current.discard).toHaveBeenCalledWith(
      ['FILE-first.png'],
      'CONVERSATION-1',
    )
  })

  it('freezes an immutable uploaded snapshot until send completes', async () => {
    let current = harness()
    let [item] = current.controller.addFiles([file('send.pdf')])
    await vi.waitFor(() =>
      expect(current.controller.readyFileNames()).toEqual(['FILE-send.pdf']),
    )

    expect(current.controller.freeze()).toEqual(['FILE-send.pdf'])
    expect(current.controller.isFrozen()).toBe(true)
    expect(current.controller.addFiles([file('late.pdf')])).toEqual([])
    await current.controller.remove(item.id)
    current.controller.retry(item.id)
    expect(current.controller.readyFileNames()).toEqual(['FILE-send.pdf'])

    current.controller.unfreeze()
    await current.controller.remove(item.id)
    expect(current.controller.getItems()).toEqual([])
  })

  it('releases accepted files locally without server cleanup', async () => {
    let current = harness()
    current.controller.addFiles([file('accepted.pdf')])
    await vi.waitFor(() =>
      expect(current.controller.readyFileNames()).toHaveLength(1),
    )

    current.controller.freeze()
    current.controller.release()

    expect(current.controller.getItems()).toEqual([])
    expect(current.discard).not.toHaveBeenCalled()
  })

  it('retargets attachment ownership used by later cleanup', async () => {
    let current = harness()
    current.controller.addFiles([file('retarget.pdf')])
    await vi.waitFor(() =>
      expect(current.controller.readyFileNames()).toEqual([
        'FILE-retarget.pdf',
      ]),
    )

    current.controller.retargetScope('CONVERSATION-2')
    await current.controller.discard()

    expect(current.discard).toHaveBeenCalledWith(
      ['FILE-retarget.pdf'],
      'CONVERSATION-2',
    )
  })

  it('uses the backend temporary-file retarget contract', async () => {
    let call = vi.fn(async () => ({
      ok: true,
      retargeted: ['FILE-1', 'FILE-2'],
    }))

    await expect(
      retargetComposerTemporaryFiles(call, {
        sourceConversation: 'CONVERSATION-1',
        targetConversation: 'CONVERSATION-2',
        files: ['FILE-1', 'FILE-2', 'FILE-1'],
      }),
    ).resolves.toEqual({
      ok: true,
      retargeted: ['FILE-1', 'FILE-2'],
    })
    expect(call).toHaveBeenCalledWith(
      'crm_messenger.api.attachments.retarget_temporary_files',
      {
        source_conversation: 'CONVERSATION-1',
        target_conversation: 'CONVERSATION-2',
        files: ['FILE-1', 'FILE-2'],
      },
    )
  })

  it('discards an upload that finishes after its composer scope reset', async () => {
    let resolveUpload
    let upload = vi.fn(
      () => new Promise((resolve) => (resolveUpload = resolve)),
    )
    let current = harness(upload)
    current.controller.addFiles([file('stale.pdf')])

    await current.controller.discard()
    resolveUpload({ name: 'FILE-stale.pdf' })

    await vi.waitFor(() =>
      expect(current.discard).toHaveBeenCalledWith(
        ['FILE-stale.pdf'],
        'CONVERSATION-1',
      ),
    )
    expect(current.controller.getItems()).toEqual([])
  })

  it('keeps a failed upload and retries the same File', async () => {
    let upload = vi
      .fn()
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce({ name: 'FILE-retry' })
    let current = harness(upload)
    let [item] = current.controller.addFiles([file('retry.jpg', 'image/jpeg')])
    await vi.waitFor(() =>
      expect(current.controller.getItems()[0].status).toBe('failed'),
    )

    await current.controller.retry(item.id)

    expect(current.controller.getItems()[0].status).toBe('uploaded')
    expect(current.controller.readyFileNames()).toEqual(['FILE-retry'])
    expect(upload).toHaveBeenCalledTimes(2)
  })

  it('enforces MAX attachment mixing in the shared pipeline', () => {
    let result = validateComposerFileMix(
      [file('document.pdf', 'application/pdf')],
      [{ file: file('photo.jpg', 'image/jpeg') }],
      { supportsAttachments: true, channelType: 'max' },
    )
    expect(result.files).toEqual([])
    expect(result.error).toContain('MAX')
  })

  it('allows 12 mixed MAX images and videos but rejects the thirteenth', () => {
    let media = Array.from({ length: 12 }, (_, index) =>
      file(
        index % 2 ? `video-${index}.mp4` : `image-${index}.jpg`,
        index % 2 ? 'video/mp4' : 'image/jpeg',
      ),
    )
    let context = {
      supportsAttachments: true,
      channelType: 'max',
      maxAttachmentCount: 12,
    }

    expect(validateComposerFileMix(media, [], context).error).toBeUndefined()
    expect(
      validateComposerFileMix(
        [...media, file('extra.webp', 'image/webp')],
        [],
        context,
      ).files,
    ).toEqual([])
  })

  it('rejects 13 MAX files as one batch with one warning', () => {
    let onError = vi.fn()
    let upload = vi.fn()
    let context = {
      supportsAttachments: true,
      channelType: 'max',
      maxAttachmentCount: 12,
    }
    let controller = createComposerAttachmentController({
      upload,
      maxFiles: 12,
      validateFiles: (files, existing) =>
        validateComposerFileMix(files, existing, context),
      onError,
    })
    let files = Array.from({ length: 13 }, (_, index) =>
      file(`image-${index}.jpg`, 'image/jpeg'),
    )

    expect(controller.addFiles(files)).toEqual([])
    expect(onError).toHaveBeenCalledOnce()
    expect(upload).not.toHaveBeenCalled()
    expect(controller.getItems()).toEqual([])

    controller.addFiles(files.slice(0, 11))
    onError.mockClear()
    upload.mockClear()
    expect(controller.addFiles(files.slice(11))).toEqual([])
    expect(onError).toHaveBeenCalledOnce()
    expect(upload).not.toHaveBeenCalled()
    expect(controller.getItems()).toHaveLength(11)
  })

  it('applies the capability attachment limit to every provider', () => {
    let result = validateComposerFileMix(
      [file('third.jpg', 'image/jpeg')],
      [
        { file: file('first.jpg', 'image/jpeg') },
        { file: file('second.jpg', 'image/jpeg') },
      ],
      {
        supportsAttachments: true,
        channelType: 'custom',
        maxAttachmentCount: 2,
      },
    )

    expect(result.files).toEqual([])
    expect(result.error).toContain('2')
  })

  it('blocks unsupported Avito attachments before upload', () => {
    let onError = vi.fn()
    let upload = vi.fn()
    let policy = getComposerAttachmentPolicy(
      {
        supports_attachments: true,
        supported_attachment_types: ['image'],
        max_attachment_count: 1,
      },
      'avito',
    )
    let controller = createComposerAttachmentController({
      upload,
      maxFiles: 1,
      validateFiles: (files, existing) =>
        validateComposerFileMix(files, existing, policy),
      onError,
    })

    expect(
      controller.addFiles([file('document.pdf', 'application/pdf')]),
    ).toEqual([])
    expect(upload).not.toHaveBeenCalled()
    expect(onError).toHaveBeenCalledWith(
      'The selected channel supports only image attachments.',
    )
  })

  it('blocks unsupported pasted Avito media before upload', () => {
    let onError = vi.fn()
    let upload = vi.fn()
    let policy = getComposerAttachmentPolicy(
      {
        supports_attachments: true,
        supported_attachment_types: ['image'],
        max_attachment_count: 1,
      },
      'avito',
    )
    let controller = createComposerAttachmentController({
      upload,
      maxFiles: 1,
      validateFiles: (files, existing) =>
        validateComposerFileMix(files, existing, policy),
      onError,
    })
    let event = {
      clipboardData: {
        items: [
          {
            kind: 'file',
            getAsFile: () => file('clip.mp4', 'video/mp4'),
          },
        ],
      },
      preventDefault: vi.fn(),
    }

    expect(controller.handlePaste(event)).toBe(true)
    expect(event.preventDefault).toHaveBeenCalledOnce()
    expect(upload).not.toHaveBeenCalled()
    expect(onError).toHaveBeenCalledOnce()
  })

  it('allows one supported Avito image but rejects its second image and WebP', () => {
    let policy = getComposerAttachmentPolicy(
      {
        supports_attachments: true,
        supported_attachment_types: ['image'],
        max_attachment_count: 1,
      },
      'avito',
    )
    let jpeg = file('photo.jpg', 'image/jpeg')

    expect(validateComposerFileMix([jpeg], [], policy).error).toBeUndefined()
    expect(
      validateComposerFileMix([file('photo.BMP')], [], policy).error,
    ).toBeUndefined()
    expect(
      validateComposerFileMix([file('photo.HEIF')], [], policy).error,
    ).toBeUndefined()
    expect(
      validateComposerFileMix(
        [file('second.png', 'image/png')],
        [{ file: jpeg }],
        policy,
      ).error,
    ).toContain('at most 1')
    expect(
      validateComposerFileMix([file('photo.webp', 'image/webp')], [], policy)
        .error,
    ).toContain('JPEG, PNG, GIF, BMP, and HEIC')
  })

  it('blocks Avito image captions without discarding the existing draft', () => {
    let draft = 'Send this after the image'
    let policy = getComposerAttachmentPolicy(
      {
        supports_attachments: true,
        supported_attachment_types: ['image'],
        max_attachment_count: 1,
      },
      'avito',
    )
    let attachment = { file: file('photo.jpg', 'image/jpeg') }

    expect(getComposerImageCaptionState(draft, [attachment], policy)).toEqual({
      blocked: true,
      message:
        'Avito API does not support image captions. Send the text as a separate message.',
      error:
        'Avito API does not support image captions. Send the text as a separate message.',
    })
    expect(draft).toBe('Send this after the image')
    expect(getComposerImageCaptionState(draft, [], policy).blocked).toBe(false)
  })

  it('disables Avito caption input without warning for an empty draft', () => {
    let policy = getComposerAttachmentPolicy(
      {
        supports_attachments: true,
        supported_attachment_types: ['image'],
        max_attachment_count: 1,
      },
      'avito',
    )

    expect(
      getComposerImageCaptionState(
        '',
        [{ file: file('photo.jpg', 'image/jpeg') }],
        policy,
      ),
    ).toEqual({
      blocked: true,
      message:
        'Avito API does not support image captions. Send the text as a separate message.',
      error: '',
    })
  })

  it('preserves attachment and caption behavior for other providers', () => {
    let policy = getComposerAttachmentPolicy(
      {
        supports_attachments: true,
        supported_attachment_types: ['image', 'file'],
        max_attachment_count: 10,
      },
      'telegram',
    )

    expect(
      validateComposerFileMix(
        [file('document.pdf', 'application/pdf')],
        [],
        policy,
      ).error,
    ).toBeUndefined()
    expect(
      getComposerImageCaptionState(
        'caption',
        [{ file: file('photo.webp', 'image/webp') }],
        policy,
      ).blocked,
    ).toBe(false)
  })
})
