import {
  canRenderInlineVideo,
  formatAttachmentDuration,
  getAttachmentAction,
  getAttachmentState,
  getImageGridCellClass,
  getImageAspectRatio,
  groupMessengerAttachments,
  visibleImageAttachments,
} from '@/utils/messengerAttachments'
import { describe, expect, it } from 'vitest'

describe('messenger attachment contract v1', () => {
  it('groups voice/audio, sticker, images and unsupported', () => {
    let groups = groupMessengerAttachments([
      { id: 'I-1', type: 'image' },
      { id: 'A-1', type: 'audio', is_voice: true },
      { id: 'S-1', type: 'sticker', mime_type: 'video/webm' },
      { id: 'U-1', type: 'unsupported' },
    ])
    expect(groups.images.map((item) => item.id)).toEqual(['I-1'])
    expect(groups.stickers.map((item) => item.id)).toEqual(['S-1'])
    expect(groups.other.map((item) => item.id)).toEqual(['A-1', 'U-1'])
  })

  it('formats voice duration', () => {
    expect(formatAttachmentDuration(4250)).toBe('0:04')
    expect(formatAttachmentDuration(65000)).toBe('1:05')
  })

  it('builds layouts for one, two, three, four and more images', () => {
    expect(getImageGridCellClass(1, 0)).toContain('max-h')
    expect(getImageGridCellClass(2, 1)).toBe('aspect-square')
    expect(getImageGridCellClass(3, 0)).toContain('row-span-2')
    expect(getImageGridCellClass(3, 1)).toBe('aspect-square')
    expect(getImageGridCellClass(4, 3)).toBe('aspect-square')
    expect(
      visibleImageAttachments(Array.from({ length: 6 }, (_, id) => ({ id }))),
    ).toHaveLength(4)
    expect(getImageAspectRatio({ width: 200, height: 100 })).toBe(1.8)
    expect(getImageAspectRatio({ width: 100, height: 300 })).toBe(0.75)
  })

  it('maps all attachment states and blocks unavailable actions', () => {
    for (let status of [
      'pending',
      'downloading',
      'retrying',
      'available',
      'external',
      'uploading',
      'uploaded',
      'failed',
      'unsupported',
    ]) {
      expect(getAttachmentState({ status }).label).toBeTruthy()
    }
    expect(getAttachmentAction({ status: 'pending', url: '/stream' })).toBe('')
    expect(
      getAttachmentAction({
        status: 'external',
        url: '/stream',
        open_url: '/redirect',
      }),
    ).toBe('/redirect')
  })

  it('keeps unsupported attachments inactive', () => {
    let attachment = {
      id: 'U-1',
      type: 'unsupported',
      status: 'unsupported',
      fallback_text: 'Неподдерживаемое вложение',
    }
    expect(getAttachmentState(attachment).unsupported).toBe(true)
    expect(getAttachmentAction(attachment)).toBe('')
  })

  it('renders inline video only from an active private stream URL', () => {
    expect(
      canRenderInlineVideo({
        type: 'video',
        status: 'available',
        mime_type: 'video/mp4',
        url: '/api/method/crm_messenger.api.attachments.stream?attachment=A-1',
      }),
    ).toBe(true)
    expect(
      canRenderInlineVideo({
        type: 'video',
        status: 'external',
        mime_type: 'image/jpeg',
        open_url: '/redirect',
      }),
    ).toBe(false)
  })
})
