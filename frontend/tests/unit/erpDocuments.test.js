import { describe, expect, it } from 'vitest'
import {
  safeDocumentURL,
  currentDocumentIssues,
} from '../../src/utils/erpDocuments'

describe('ERP document links', () => {
  it('keeps private file and ERP routes on the current site', () => {
    expect(
      safeDocumentURL('/private/files/offer.pdf', 'https://crm.example'),
    ).toBe('https://crm.example/private/files/offer.pdf')
    expect(
      safeDocumentURL('/desk/quotation/new?crm_deal=A', 'https://crm.example'),
    ).toContain('/desk/quotation/new?crm_deal=A')
  })
  it('rejects script, foreign-origin and malformed links', () => {
    for (const value of [
      'javascript:alert(1)',
      'https://foreign.example/file.pdf',
      '//foreign.example/a',
      'http://[',
      null,
    ]) {
      expect(safeDocumentURL(value, 'https://crm.example')).toBe('')
    }
  })
  it('pins only current versions while history remains separate', () => {
    const active = { name: 'v2', state: 'Действует' }
    expect(
      currentDocumentIssues([
        { name: 'v1', state: 'Заменён' },
        active,
        { name: 'x', state: 'Отменён' },
      ]),
    ).toEqual([active])
  })
})
