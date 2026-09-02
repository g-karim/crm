import {
  callAnalysisStatus,
  parseCallAnalysisItems,
} from '@/utils/callAnalysis'

describe('callAnalysis', () => {
  it('parses persisted JSON arrays and removes empty items', () => {
    expect(
      parseCallAnalysisItems('["Price agreed", "", " Call back "]'),
    ).toEqual(['Price agreed', 'Call back'])
  })

  it('accepts arrays and fails closed for malformed values', () => {
    expect(parseCallAnalysisItems(['One', null, 2])).toEqual(['One', '2'])
    expect(parseCallAnalysisItems('{bad json')).toEqual([])
    expect(parseCallAnalysisItems({ item: 'value' })).toEqual([])
  })

  it('marks only queued and processing calls as running', () => {
    expect(callAnalysisStatus('Queued').running).toBe(true)
    expect(callAnalysisStatus('Processing').running).toBe(true)
    expect(callAnalysisStatus('Completed')).toMatchObject({
      label: 'Completed',
      theme: 'green',
      running: false,
    })
  })
})
