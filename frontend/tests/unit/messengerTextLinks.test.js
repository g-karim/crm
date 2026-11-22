import { getMessengerTextSegments } from '@/utils/messengerTextLinks'
import { describe, expect, it } from 'vitest'

describe('messenger text links', () => {
  it.each([
    'https://kabinet.kgeu.ru/WebApp/#/Rasp/Group/12589',
    'https://www.avito.ru/brands/683a6924651baab4e51fc766348b14e2?src=sharing',
  ])('preserves the full screenshot URL %s', (url) => {
    expect(getMessengerTextSegments(`Ссылка: ${url}`)).toEqual([
      { text: 'Ссылка: ' },
      { text: url, href: url },
    ])
  })

  it('preserves Unicode, query parameters, fragments, whitespace and newlines', () => {
    let url = 'https://пример.рф/объявление?город=Казань&цена=100#подробнее'
    let text = `  Адрес:\n${url}\n\n  Следующая строка  `
    let segments = getMessengerTextSegments(text)

    expect(segments).toEqual([
      { text: '  Адрес:\n' },
      { text: url, href: url },
      { text: '\n\n  Следующая строка  ' },
    ])
    expect(segments.map((segment) => segment.text).join('')).toBe(text)
  })

  it('leaves surrounding punctuation outside links while keeping balanced parentheses', () => {
    let text =
      'См. (https://example.com/path_(abc)), «https://example.com/next» и https://example.com/last…'
    let segments = getMessengerTextSegments(text)

    expect(segments.filter((segment) => segment.href)).toEqual([
      {
        text: 'https://example.com/path_(abc)',
        href: 'https://example.com/path_(abc)',
      },
      { text: 'https://example.com/next', href: 'https://example.com/next' },
      { text: 'https://example.com/last', href: 'https://example.com/last' },
    ])
    expect(segments.map((segment) => segment.text).join('')).toBe(text)
  })

  it('activates explicit HTTP(S) URLs only', () => {
    let text =
      'javascript:alert(1) data:text/html,<b>x</b> ftp://example.com www.example.com person@example.com //example.com HTTPS://example.com/ok'
    let segments = getMessengerTextSegments(text)

    expect(segments.filter((segment) => segment.href)).toEqual([
      { text: 'HTTPS://example.com/ok', href: 'HTTPS://example.com/ok' },
    ])
    expect(segments.map((segment) => segment.text).join('')).toBe(text)
  })

  it.each([
    'https://user:secret@example.com/path',
    'https://user@example.com/path',
    'https://example.com/a\u202eb',
    'https://example.com/a\\b',
    'https://',
  ])('keeps unsafe or malformed URL text literal: %s', (text) => {
    let segments = getMessengerTextSegments(text)
    expect(segments).toEqual([{ text }])
  })

  it('handles absent text without adding content', () => {
    expect(getMessengerTextSegments()).toEqual([])
    expect(getMessengerTextSegments(null)).toEqual([])
  })
})
