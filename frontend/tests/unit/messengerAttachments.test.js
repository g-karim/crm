import {
  canRenderInlineVideo,
  formatAttachmentDuration,
  getAttachmentAction,
  getAttachmentState,
  getImageGridCellClass,
  getSingleImageBubbleWidthClass,
  getSingleImageMediaWidthClass,
  groupMessengerAttachments,
  isSingleImageAttachmentSet,
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

  it('classifies only a single standalone image as single-image layout', () => {
    expect(isSingleImageAttachmentSet([{ id: 'I-1', type: 'image' }])).toBe(
      true,
    )
    expect(
      isSingleImageAttachmentSet([
        { id: 'I-1', type: 'image' },
        { id: 'I-2', type: 'image' },
      ]),
    ).toBe(false)
    expect(
      isSingleImageAttachmentSet([
        { id: 'I-1', type: 'image' },
        { id: 'F-1', type: 'file' },
      ]),
    ).toBe(false)
    expect(isSingleImageAttachmentSet([{ id: 'S-1', type: 'sticker' }])).toBe(
      false,
    )
  })

  it('selects presentation width from image orientation, not intrinsic size', () => {
    expect(getSingleImageBubbleWidthClass({ width: 100, height: 200 })).toBe(
      'w-[18rem]',
    )
    expect(getSingleImageBubbleWidthClass({ width: 64, height: 64 })).toBe(
      'w-[24rem]',
    )
    expect(getSingleImageBubbleWidthClass({ width: 400, height: 200 })).toBe(
      'w-[29.5rem]',
    )
    expect(getSingleImageBubbleWidthClass({ width: 100, height: 95 })).toBe(
      'w-[24rem]',
    )
    expect(getSingleImageBubbleWidthClass({})).toBe('w-[24rem]')

    expect(getSingleImageMediaWidthClass({ width: 100, height: 200 })).toBe(
      'w-[16.5rem]',
    )
    expect(getSingleImageMediaWidthClass({ width: 64, height: 64 })).toBe(
      'w-[22.5rem]',
    )
    expect(getSingleImageMediaWidthClass({ width: 400, height: 200 })).toBe(
      'w-[28rem]',
    )
  })

  it('builds grid layouts for two, three, four and more images', () => {
    expect(getImageGridCellClass(2, 1)).toBe('aspect-square')
    expect(getImageGridCellClass(3, 0)).toContain('row-span-2')
    expect(getImageGridCellClass(3, 1)).toBe('aspect-square')
    expect(getImageGridCellClass(4, 3)).toBe('aspect-square')
    expect(
      visibleImageAttachments(Array.from({ length: 6 }, (_, id) => ({ id }))),
    ).toHaveLength(4)
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
