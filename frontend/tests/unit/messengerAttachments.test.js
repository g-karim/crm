import {
  buildMessengerAttachmentSegments,
  canRenderInlineVideo,
  formatAttachmentDuration,
  getAttachmentAction,
  getAttachmentState,
  getMessengerAttachmentTitle,
  getMessengerReplyAttachmentType,
  getMessengerMessagePreview,
  getCompactMediaDimensions,
  getCompactPreviewDimensions,
  getVideoExternalAction,
  getVideoPlaybackUrl,
  getImageGridCellClass,
  getSingleImageBubbleWidthClass,
  getSingleImageMediaWidthClass,
  groupMessengerAttachments,
  isSingleImageAttachmentSet,
  isSingleFileAttachmentSet,
  isSingleLocationAttachmentSet,
  isSingleStickerAttachmentSet,
  visibleImageAttachments,
} from '@/utils/messengerAttachments'
import { describe, expect, it } from 'vitest'

describe('messenger attachment contract v1', () => {
  it.each(['wazzup', 'max_direct', 'telegram_bot', 'vk_direct'])(
    'labels decoded animated images in %s reply previews without guessing from MIME',
    (provider) => {
      for (let mime_type of [
        'image/gif',
        'image/webp',
        'image/apng',
        'image/png',
      ]) {
        expect(
          getMessengerReplyAttachmentType({
            provider,
            type: 'image',
            mime_type,
            is_animated: true,
          }),
        ).toBe('animation')
        expect(
          getMessengerReplyAttachmentType({
            provider,
            type: 'image',
            mime_type,
          }),
        ).toBe('image')
      }
      for (let mime_type of ['image/png', 'image/jpeg', 'image/webp']) {
        expect(
          getMessengerReplyAttachmentType({
            provider,
            type: 'image',
            mime_type,
            is_animated: false,
          }),
        ).toBe('image')
      }
      expect(
        getMessengerReplyAttachmentType({
          provider,
          type: 'image',
          mime_type: 'image/jpeg',
          is_animated: true,
        }),
      ).toBe('image')
      expect(
        getMessengerReplyAttachmentType({
          provider,
          type: 'video',
          mime_type: 'video/mp4',
          is_animated: true,
        }),
      ).toBe('animation')
      expect(
        getMessengerReplyAttachmentType({
          provider,
          type: 'sticker',
          mime_type: 'image/webp',
          is_animated: true,
        }),
      ).toBe('sticker')
      expect(
        getMessengerReplyAttachmentType({
          provider,
          type: 'audio',
          is_voice: true,
        }),
      ).toBe('voice')
    },
  )

  it('prefers the shared semantic type without changing attachment rendering types', () => {
    expect(
      getMessengerReplyAttachmentType({
        type: 'video',
        semantic_type: 'video_note',
      }),
    ).toBe('video_note')
    expect(
      getMessengerReplyAttachmentType({
        type: 'image',
        semantic_type: 'image',
        is_animated: true,
      }),
    ).toBe('image')
    expect(
      getMessengerReplyAttachmentType({
        type: 'image',
        semantic_type: 'animation',
      }),
    ).toBe('animation')
    let sticker = {
      id: 'STICKER',
      type: 'sticker',
      semantic_type: 'sticker',
      is_animated: true,
    }
    expect(getMessengerReplyAttachmentType(sticker)).toBe('sticker')
    expect(buildMessengerAttachmentSegments([sticker])[0].type).toBe('sticker')
    expect(sticker.type).toBe('sticker')
  })

  it.each(['provider-specific', 'constructor', '__proto__'])(
    'falls back to legacy attachment flags for an unknown semantic type %s',
    (semantic_type) => {
      expect(
        getMessengerReplyAttachmentType({
          type: 'audio',
          semantic_type,
          is_voice: true,
        }),
      ).toBe('voice')
    },
  )

  it('does not infer a video message from a technical filename', () => {
    expect(
      getMessengerReplyAttachmentType({
        type: 'video',
        mime_type: 'video/mp4',
        file_name: 'video-note.mp4',
      }),
    ).toBe('video')
  })

  it('keeps transparent square WebP artwork as an image despite obsolete sticker hints', () => {
    let artwork = {
      id: 'TRANSPARENT-WEBP',
      provider: 'wazzup',
      type: 'image',
      mime_type: 'image/webp',
      width: 512,
      height: 512,
      is_sticker_candidate: true,
    }
    expect(isSingleStickerAttachmentSet([artwork])).toBe(false)
    expect(getMessengerReplyAttachmentType(artwork)).toBe('image')
    expect(buildMessengerAttachmentSegments([artwork])[0]).toMatchObject({
      type: 'images',
      items: [{ type: 'image' }],
    })
  })

  it.each(['wazzup', 'max_direct', 'telegram_bot', 'vk_direct'])(
    'uses the common compact renderer for explicit %s stickers',
    (provider) => {
      let sticker = { provider, type: 'sticker', mime_type: 'image/webp' }
      expect(isSingleStickerAttachmentSet([sticker])).toBe(true)
      expect(getMessengerReplyAttachmentType(sticker)).toBe('sticker')
      expect(buildMessengerAttachmentSegments([sticker])[0]).toMatchObject({
        type: 'sticker',
        attachment: sticker,
      })
    },
  )

  it('routes explicit voice DTOs to the common audio player', () => {
    expect(
      buildMessengerAttachmentSegments([{ id: 'VOICE', type: 'voice' }])[0]
        .type,
    ).toBe('audio')
  })

  it('lets a single document fill the content width without widening mixed media', () => {
    expect(isSingleFileAttachmentSet([{ type: 'file' }])).toBe(true)
    expect(
      isSingleFileAttachmentSet([{ type: 'file' }, { type: 'image' }]),
    ).toBe(false)
  })

  it.each(['File.docx', '0123456789abcdef0123456789abcdef.docx'])(
    'preserves the confirmed Wazzup original filename %s',
    (original_file_name) => {
      expect(
        getMessengerAttachmentTitle({
          provider: 'wazzup',
          type: 'file',
          original_file_name,
          display_title: 'File',
          file_name: '0123456789abcdef0123456789abcdef.docx',
        }),
      ).toBe(original_file_name)
    },
  )

  it('uses the original display filename and hides opaque storage names', () => {
    let hash = '0123456789abcdef0123456789abcdef.pdf'
    expect(
      getMessengerAttachmentTitle({
        provider: 'wazzup',
        type: 'file',
        display_title: 'Договор.pdf',
        file_name: hash,
      }),
    ).toBe('Договор.pdf')
    expect(
      getMessengerAttachmentTitle({
        provider: 'wazzup',
        type: 'file',
        display_title: hash,
        file_name: hash,
      }),
    ).toBe('File')
    expect(
      getMessengerAttachmentTitle({
        provider: 'wazzup',
        type: 'file',
        file_name: 'f46113a6-fb8f-4d5d-9887-e6fd1e704477.pdf',
      }),
    ).toBe('File')
    // A suffix resembling a Frappe storage hash is not proof of a lost name.
    expect(
      getMessengerAttachmentTitle({
        type: 'file',
        file_name: 'reportabc123.pdf',
      }),
    ).toBe('reportabc123.pdf')
  })

  it.each(['max_direct', 'vk_direct', 'telegram_bot', 'avito_direct'])(
    'preserves explicitly named opaque documents for %s',
    (provider) => {
      let file_name = '0123456789abcdef0123456789abcdef.pdf'
      expect(
        getMessengerAttachmentTitle({
          provider,
          type: 'file',
          file_name,
          display_title: file_name,
        }),
      ).toBe(file_name)
    },
  )

  it('does not render arbitrary status diagnostics or expose unavailable actions', () => {
    let state = getAttachmentState({
      status: 'https://provider.test/?secret=private',
      error: 'private provider body',
    })
    expect(state).toMatchObject({
      status: 'unsupported',
      label: 'Unsupported',
      busy: false,
      active: false,
    })
    expect(getAttachmentState({ status: 'failed' }).label).toBe(
      'Attachment unavailable',
    )
  })
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

  it('routes animated images and videos through one animation segment', () => {
    let segments = buildMessengerAttachmentSegments([
      { id: 'GIF-1', type: 'image', is_animated: true },
      { id: 'GIF-2', type: 'video', is_animated: true },
      { id: 'I-1', type: 'image' },
    ])

    expect(segments.map((segment) => segment.type)).toEqual([
      'animation',
      'animation',
      'images',
    ])
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
    ).toBe('Voice message')
    expect(
      getMessengerAttachmentTitle({
        type: 'video',
        file_name: 'video-note.mp4',
      }),
    ).toBe('Video')
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
        display_title: 'Файл',
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
    ).toBe('Unsupported attachment')
    expect(
      getMessengerAttachmentTitle({
        type: 'link',
        title: 'Provider-specific page title',
      }),
    ).toBe('Link')
    expect(
      getMessengerAttachmentTitle({
        type: 'audio',
        file_name: 'audio.mp3',
      }),
    ).toBe('Audio')
    expect(
      getMessengerAttachmentTitle({
        type: 'sticker',
        status: 'unsupported',
        file_name: 'sticker.tgs',
      }),
    ).toBe('Sticker unavailable')
  })

  it('builds human last-message previews without raw type markers', () => {
    expect(
      getMessengerMessagePreview({
        message_type: 'audio',
        display_text: 'Голосовое сообщение',
      }),
    ).toBe('Голосовое сообщение')
    expect(getMessengerMessagePreview({ message_type: 'video' })).toBe('Video')
    expect(getMessengerMessagePreview({ message_type: 'video_note' })).toBe(
      'Video message',
    )
    expect(getMessengerMessagePreview({ message_type: 'animation' })).toBe(
      'Animation',
    )
    expect(
      getMessengerMessagePreview({ message_type: 'application/x-internal' }),
    ).toBe('Attachment')
    expect(
      getMessengerMessagePreview({
        message_type: 'video_note',
        text: 'Подпись к видео',
      }),
    ).toBe('Подпись к видео')
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
    expect(isSingleStickerAttachmentSet([{ id: 'S-1', type: 'sticker' }])).toBe(
      true,
    )
    expect(
      isSingleStickerAttachmentSet([
        { id: 'S-1', type: 'sticker' },
        { id: 'S-2', type: 'sticker' },
      ]),
    ).toBe(false)
  })

  it('classifies only a single location as fixed-width location content', () => {
    expect(
      isSingleLocationAttachmentSet([{ id: 'GEO-1', type: 'location' }]),
    ).toBe(true)
    expect(
      isSingleLocationAttachmentSet([
        { id: 'GEO-1', type: 'location' },
        { id: 'I-1', type: 'image' },
      ]),
    ).toBe(false)
  })

  it('uses content-sized bubble classes for compact media', () => {
    expect(getSingleImageBubbleWidthClass({ width: 100, height: 200 })).toBe(
      'w-fit',
    )
    expect(getSingleImageBubbleWidthClass({})).toBe('w-fit')
    expect(getSingleImageMediaWidthClass({ width: 100, height: 200 })).toBe(
      'max-w-full',
    )
  })

  it('uses a full-width letterboxed frame for portrait media', () => {
    expect(getCompactMediaDimensions({ width: 9, height: 16 })).toEqual({
      ratio: 320 / 360,
      width: 320,
      height: 360,
      letterboxed: true,
    })
    expect(getCompactMediaDimensions({ width: 4, height: 5 })).toEqual({
      ratio: 320 / 360,
      width: 320,
      height: 360,
      letterboxed: true,
    })
    expect(getCompactMediaDimensions({ width: 64, height: 64 })).toEqual({
      ratio: 1,
      width: 320,
      height: 320,
      letterboxed: false,
    })
    expect(getCompactMediaDimensions({ width: 400, height: 200 })).toEqual({
      ratio: 2,
      width: 320,
      height: 160,
      letterboxed: false,
    })
    expect(getCompactMediaDimensions({})).toEqual({
      ratio: 16 / 9,
      width: 320,
      height: 180,
      letterboxed: false,
    })
  })

  it('letterboxes tall compact previews without cropping them', () => {
    expect(getCompactPreviewDimensions({ width: 1920, height: 1080 })).toEqual({
      ratio: 1920 / 1080,
      width: 320,
      height: 180,
      letterboxed: false,
    })
    expect(getCompactPreviewDimensions({ width: 1080, height: 1920 })).toEqual({
      ratio: 320 / 280,
      width: 320,
      height: 280,
      letterboxed: true,
    })
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
        status: 'available',
        download_url: '/protected/download',
      }),
    ).toBe('/protected/download')
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

  it.each([
    'wazzup',
    'max_direct',
    'vk_direct',
    'telegram_bot',
    'avito_direct',
  ])(
    'downloads saved %s documents through the named download endpoint',
    (provider) => {
      let attachment = {
        provider,
        id: 'SAVED-DOCUMENT',
        type: 'file',
        file_name: 'File.docx',
        url: '/api/method/crm_messenger.api.attachments.stream?attachment=SAVED-DOCUMENT',
        download_url:
          '/api/method/crm_messenger.api.attachments.download?attachment=SAVED-DOCUMENT',
      }
      for (let status of ['available', 'uploaded']) {
        expect(getAttachmentAction({ ...attachment, status })).toBe(
          attachment.download_url,
        )
      }
      for (let status of ['pending', 'downloading', 'retrying', 'failed']) {
        expect(getAttachmentAction({ ...attachment, status })).toBe('')
      }
    },
  )

  it('preserves source actions for external documents and streamed media', () => {
    expect(
      getAttachmentAction({
        type: 'file',
        status: 'external',
        open_url: '/protected/external-document',
      }),
    ).toBe('/protected/external-document')
    expect(
      getAttachmentAction({
        type: 'file',
        status: 'available',
        url: '/legacy-document',
      }),
    ).toBe('/legacy-document')
    for (let type of ['image', 'audio', 'video', 'sticker']) {
      expect(
        getAttachmentAction({
          type,
          status: 'available',
          url: '/protected/stream',
          download_url: '/protected/download',
        }),
      ).toBe('/protected/stream')
    }
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

  it('allows an external-only video action before attachment processing finishes', () => {
    expect(
      getVideoExternalAction({
        type: 'video',
        status: 'pending',
        video_source: 'external',
        open_url: '/open-vk-video',
      }),
    ).toBe('/open-vk-video')
    expect(
      getVideoExternalAction({
        type: 'video',
        status: 'pending',
        video_source: 'provider_embed',
        open_url: '/open-vk-embed',
      }),
    ).toBe('/open-vk-embed')
    expect(
      getVideoExternalAction({
        type: 'video',
        status: 'pending',
        video_source: 'provider_file',
        open_url: '/open-provider-file',
      }),
    ).toBe('')
  })
})
