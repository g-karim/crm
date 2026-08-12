import {
  buildMessengerAttachmentSegments,
  canRenderInlineVideo,
  formatAttachmentDuration,
  getAttachmentAction,
  getAttachmentState,
  getMessengerAttachmentTitle,
  getMessengerMessagePreview,
  getCompactMediaDimensions,
  getVideoPlaybackUrl,
  getImageGridCellClass,
  getSingleImageBubbleWidthClass,
  getSingleImageMediaWidthClass,
  groupMessengerAttachments,
  isSingleImageAttachmentSet,
  visibleImageAttachments,
} from '@/utils/messengerAttachments'
import { describe, expect, it } from 'vitest'

describe('messenger attachment contract v1', () => {
  it('groups only adjacent images and preserves provider order', () => {
    let segments = buildMessengerAttachmentSegments([
      { id: 'V-1', type: 'video' },
      { id: 'V-2', type: 'video' },
      { id: 'I-1', type: 'image' },
      { id: 'I-2', type: 'image' },
      { id: 'F-1', type: 'file' },
      { id: 'I-3', type: 'image' },
    ])

    expect(segments.map((segment) => segment.type)).toEqual([
      'video',
      'video',
      'images',
      'file',
      'images',
    ])
    expect(segments[2].items.map((item) => item.id)).toEqual(['I-1', 'I-2'])
    expect(segments[4].items.map((item) => item.id)).toEqual(['I-3'])
  })

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

  it('uses one title contract and hides provider-generated names', () => {
    expect(
      getMessengerAttachmentTitle({
        type: 'audio',
        is_voice: true,
        file_name: 'voice.ogg',
      }),
    ).toBe('Голосовое сообщение')
    expect(
      getMessengerAttachmentTitle({
        type: 'video',
        file_name: 'video-note.mp4',
      }),
    ).toBe('Видео')
    expect(
      getMessengerAttachmentTitle({
        type: 'file',
        file_name: 'contract.pdf',
      }),
    ).toBe('contract.pdf')
    expect(
      getMessengerAttachmentTitle({
        type: 'file',
        file_name: 'contract.pdf',
        display_title: 'Договор',
      }),
    ).toBe('Договор')
    expect(
      getMessengerAttachmentTitle({
        type: 'unsupported',
        fallback_text: 'Неподдерживаемое вложение MAX: share',
      }),
    ).toBe('Неподдерживаемое вложение')
    expect(
      getMessengerAttachmentTitle({
        type: 'link',
        title: 'Provider-specific page title',
      }),
    ).toBe('Ссылка')
    expect(
      getMessengerAttachmentTitle({
        type: 'audio',
        file_name: 'audio.mp3',
      }),
    ).toBe('Аудио')
    expect(
      getMessengerAttachmentTitle({
        type: 'sticker',
        status: 'unsupported',
        file_name: 'sticker.tgs',
      }),
    ).toBe('Стикер недоступен')
  })

  it('builds human last-message previews without raw type markers', () => {
    expect(
      getMessengerMessagePreview({
        message_type: 'audio',
        display_text: 'Голосовое сообщение',
      }),
    ).toBe('Голосовое сообщение')
    expect(getMessengerMessagePreview({ message_type: 'video' })).toBe('Видео')
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

  it('uses content-sized bubble classes for compact media', () => {
    expect(getSingleImageBubbleWidthClass({ width: 100, height: 200 })).toBe(
      'w-fit max-w-full',
    )
    expect(getSingleImageBubbleWidthClass({})).toBe('w-fit max-w-full')
    expect(getSingleImageMediaWidthClass({ width: 100, height: 200 })).toBe(
      'max-w-full',
    )
  })

  it('fits portrait, square and landscape media inside 320 by 360 pixels', () => {
    expect(getCompactMediaDimensions({ width: 100, height: 200 })).toEqual({
      ratio: 0.5,
      width: 180,
      height: 360,
    })
    expect(getCompactMediaDimensions({ width: 64, height: 64 })).toEqual({
      ratio: 1,
      width: 320,
      height: 320,
    })
    expect(getCompactMediaDimensions({ width: 400, height: 200 })).toEqual({
      ratio: 2,
      width: 320,
      height: 160,
    })
    expect(
      getCompactMediaDimensions({ width: 9, height: 16 }).height,
    ).toBeLessThanOrEqual(360)
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
      'processing',
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
        status: 'failed',
        type: 'audio',
        is_voice: true,
        url: '/private-voice-stream',
      }),
    ).toBe('/private-voice-stream')
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
      getVideoPlaybackUrl({
        type: 'video',
        status: 'available',
        video_source: 'local_file',
        mime_type: 'video/webm',
        playback_url: '/private-video-stream',
      }),
    ).toBe('/private-video-stream')
    expect(
      canRenderInlineVideo({
        type: 'video',
        status: 'external',
        mime_type: 'image/jpeg',
        open_url: '/redirect',
      }),
    ).toBe(false)
    expect(
      canRenderInlineVideo({
        type: 'video',
        status: 'external',
        video_source: 'provider_embed',
        mime_type: 'video/mp4',
        url: 'https://temporary.provider/video.mp4',
      }),
    ).toBe(false)
  })
})
