import {
  draftKey,
  mergeMessages,
  deliveryLabel,
  safeEmailDocument,
  quoteMessage,
  restoreInboxDraft,
  draftFingerprint,
} from '@/utils/inbox'

describe('unified inbox boundaries', () => {
  it('does not create a false edit when the server reorders JSON keys', () => {
    expect(
      draftFingerprint({
        text: 'same',
        attachments: [{ name: 'f', file_name: 'a' }],
      }),
    ).toBe(
      draftFingerprint({
        attachments: [{ file_name: 'a', name: 'f' }],
        text: 'same',
      }),
    )
  })
  it('requires explicit resolution when an offline copy predates another window', () => {
    expect(
      restoreInboxDraft(
        { revision: 2, draft: { text: 'mine' } },
        { revision: 3, draft: { text: 'other window' } },
      ),
    ).toEqual({ draft: { text: 'mine' }, conflict: true })
    expect(
      restoreInboxDraft(
        { revision: 2, draft: { text: 'mine' } },
        { revision: 2, draft: { text: 'old' } },
      ).conflict,
    ).toBe(false)
  })
  it('isolates drafts by viewer and exact source, never by client name', () => {
    expect(draftKey('Guest', 'email:x')).toBeNull()
    expect(draftKey('a', 'email:x')).not.toEqual(draftKey('b', 'email:x'))
    expect(draftKey('a', 'email:x')).not.toEqual(draftKey('a', 'messenger:x'))
  })
  it('merges changes without duplicates, retaining a stable chronological order', () => {
    const a = {
      name: 'a',
      creation: '2026-01-01',
      message_datetime: '2026-01-01',
      text: 'old',
    }
    const b = {
      name: 'b',
      creation: '2026-01-01',
      message_datetime: '2026-01-01',
    }
    expect(mergeMessages([b, a], [{ ...a, text: 'edited' }])).toEqual([
      { ...a, text: 'edited' },
      b,
    ])
  })
  it('never presents a local example as provider-confirmed delivery', () => {
    expect(
      deliveryLabel({ direction: 'outbound', status: 'sent' }, true),
    ).toContain('не отправлено')
    expect(
      deliveryLabel({ direction: 'outbound', status: 'unknown' }),
    ).toContain('не подтверждена')
    expect(deliveryLabel({ direction: 'inbound' })).toBe('')
  })
  it('blocks executable mail, remote trackers, forms and navigation', () => {
    const doc = safeEmailDocument(
      '<script>alert(1)</script><img src="https://tracker.test/x"><a href="javascript:alert(2)">Link</a><p onmouseover="alert(1)" style="background:url(https://evil.test)">Hello</p><form action="https://evil.test">Form</form>',
    )
    expect(doc).not.toContain('<script')
    expect(doc).not.toContain('<img')
    expect(doc).not.toContain('href=')
    expect(doc).not.toContain('onmouseover')
    expect(doc).not.toContain('https://')
    expect(doc).toContain("default-src 'none'")
    expect(doc).toContain('Hello')
  })
  it('quotes all lines of a selected mail without HTML execution', () => {
    expect(quoteMessage('a\nb')).toBe('> a\n> b\n\n')
  })
})
