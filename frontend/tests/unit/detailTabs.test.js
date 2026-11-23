import { describe, expect, it } from 'vitest'
import {
  detailTabIndex,
  detailViewLabel,
  groupDetailTabs,
} from '@/utils/detailTabs'

const makeTabs = (names) => names.map((name) => ({ name, label: name }))

describe('grouped card navigation', () => {
  it('keeps documents, settlements and fulfillment in one group with direct links', () => {
    const tabs = makeTabs([
      'Activity',
      'Data',
      'Documents',
      'Attachments',
      'Fulfillment',
      'Settlements',
    ])
    const docs = groupDetailTabs(tabs).find(
      (group) => group.name === 'documents',
    )
    expect(docs.views.map((view) => view.name)).toEqual([
      'Documents',
      'Settlements',
      'Fulfillment',
      'Attachments',
    ])
    expect(detailTabIndex(tabs, '#settlements')).toBe(5)
    expect(detailTabIndex(tabs, '#fulfillment')).toBe(4)
    expect(detailViewLabel({ name: 'Settlements' })).toBe('Расчёты')
    expect(detailViewLabel({ name: 'Fulfillment' })).toBe('Исполнение')
  })

  it('keeps four fixed groups and the original view indices', () => {
    const tabs = makeTabs([
      'Data',
      'Attachments',
      'Comments',
      'Documents',
      'Calls',
      'Activity',
      'Events',
      'Tasks',
      'Notes',
      'Emails',
    ])
    const groups = groupDetailTabs(tabs)
    expect(groups.map((group) => group.name)).toEqual([
      'data',
      'activity',
      'communication',
      'documents',
    ])
    expect(groups[1].views.map((view) => view.name)).toEqual([
      'Activity',
      'Tasks',
      'Events',
      'Comments',
      'Notes',
    ])
    expect(groups[3].views.map((view) => view.name)).toEqual([
      'Documents',
      'Attachments',
    ])
    for (const group of groups)
      for (const view of group.views)
        expect(tabs[view.index].name).toBe(view.name)
  })

  it('only offers available channels and retains files without ERP', () => {
    const groups = groupDetailTabs(
      makeTabs(['Activity', 'Emails', 'Attachments', 'Data']),
    )
    expect(groups[2].views.map((view) => view.name)).toEqual(['Emails'])
    expect(groups[3].views.map((view) => view.name)).toEqual(['Attachments'])
    expect(groupDetailTabs([])).toEqual([])
  })

  it('keeps mobile details and additional fields together without losing extensions', () => {
    const groups = groupDetailTabs(
      makeTabs(['Details', 'Activity', 'Data', 'Custom view']),
    )
    expect(
      groups
        .find((group) => group.name === 'data')
        .views.map((view) => view.name),
    ).toEqual(['Details', 'Data', 'Custom view'])
    expect(detailViewLabel({ name: 'Activity' })).toBe('History')
    expect(detailViewLabel({ name: 'Custom view', label: 'Custom' })).toBe(
      'Custom',
    )
  })

  it('resolves existing links and falls back to history for an activity record or unavailable channel', () => {
    const tabs = makeTabs([
      'Details',
      'Activity',
      'Tasks',
      'Emails',
      'Documents',
    ])
    expect(detailTabIndex(tabs, '#tasks')).toBe(2)
    expect(detailTabIndex(tabs, 'EMAILS')).toBe(3)
    expect(detailTabIndex(tabs, 'documents')).toBe(4)
    expect(detailTabIndex(tabs, 'communication-record-id')).toBe(1)
    expect(detailTabIndex(tabs, 'whatsapp')).toBe(1)
    expect(detailTabIndex([], null)).toBe(0)
  })

  it('opens data by default and keeps explicit links authoritative', () => {
    const desktop = makeTabs(['Activity', 'Tasks', 'Data', 'Documents'])
    const mobile = makeTabs(['Details', ...desktop.map((tab) => tab.name)])
    expect(detailTabIndex(desktop)).toBe(2)
    expect(detailTabIndex(desktop, '')).toBe(2)
    expect(detailTabIndex(mobile)).toBe(0)
    expect(detailTabIndex(mobile, '#data')).toBe(3)
    expect(detailTabIndex(mobile, '#tasks')).toBe(2)
    expect(detailTabIndex(mobile, 'timeline-record-id')).toBe(1)
  })
})
