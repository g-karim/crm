import {
  createComposerAttachmentController,
  validateComposerFileMix,
} from '@/utils/messengerComposer'
import { describe, expect, it, vi } from 'vitest'

function file(name, type = 'application/octet-stream') {
  return new File(['content'], name, { type })
}

function harness(upload = vi.fn(async (value) => ({ name: `FILE-${value.name}` }))) {
  let urls = []
  let revoked = []
  let changes = []
  let controller = createComposerAttachmentController({
    upload,
    createObjectURL: (value) => {
      let url = `blob:${value.name}`
      urls.push(url)
      return url
    },
    revokeObjectURL: (url) => revoked.push(url),
    validateFiles: (files) => ({ files }),
    onChange: (items) => changes.push(items),
  })
  return { controller, upload, urls, revoked, changes }
}

describe('messenger composer attachments', () => {
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
    await vi.waitFor(() => expect(current.controller.readyFileNames()).toHaveLength(1))
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
    await vi.waitFor(() => expect(current.controller.readyFileNames()).toHaveLength(2))
    expect(current.upload).toHaveBeenCalledTimes(2)
  })

  it('uses the same pipeline for drag-and-drop', async () => {
    let current = harness()
    let event = {
      dataTransfer: { files: [file('drop.pdf', 'application/pdf')] },
      preventDefault: vi.fn(),
    }

    expect(current.controller.handleDrop(event)).toBe(true)
    await vi.waitFor(() => expect(current.controller.readyFileNames()).toEqual(['FILE-drop.pdf']))
    expect(current.upload).toHaveBeenCalledOnce()
  })

  it('removes local state and revokes preview without deleting a Frappe File', async () => {
    let current = harness()
    let [item] = current.controller.addFiles([file('remove.png', 'image/png')])
    await vi.waitFor(() => expect(current.controller.readyFileNames()).toHaveLength(1))

    current.controller.remove(item.id)

    expect(current.controller.getItems()).toEqual([])
    expect(current.revoked).toEqual(['blob:remove.png'])
  })

  it('keeps a failed upload and retries the same File', async () => {
    let upload = vi
      .fn()
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce({ name: 'FILE-retry' })
    let current = harness(upload)
    let [item] = current.controller.addFiles([file('retry.jpg', 'image/jpeg')])
    await vi.waitFor(() => expect(current.controller.getItems()[0].status).toBe('failed'))

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
})
