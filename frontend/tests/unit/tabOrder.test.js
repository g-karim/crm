import { describe, expect, it } from 'vitest'
import { moveVisibleTab, orderTabs } from '@/utils/tabOrder'

const tabs = ['Activity', 'Emails', 'Events', 'WhatsApp'].map((name) => ({
  name,
}))

describe('personal detail tab order', () => {
  it('keeps the default order until a user changes it', () => {
    expect(orderTabs(tabs, null).map((tab) => tab.name)).toEqual(
      tabs.map((tab) => tab.name),
    )
  })

  it('loads saved names and safely appends new tabs', () => {
    expect(
      orderTabs(tabs, ['Events', 'Activity', 'Events', 'Removed']).map(
        (tab) => tab.name,
      ),
    ).toEqual(['Events', 'Activity', 'Emails', 'WhatsApp'])
  })

  it('moves visible tabs without losing hidden tabs', () => {
    const visible = tabs.slice(0, 3)
    const saved = moveVisibleTab(tabs, visible, 2, 0)
    expect(saved).toEqual(['Events', 'Activity', 'Emails', 'WhatsApp'])
    expect(orderTabs(tabs, saved).map((tab) => tab.name)).toEqual(saved)
  })

  it('keeps an unavailable tab in its existing slot', () => {
    const withHiddenFirst = orderTabs(tabs, [
      'Activity',
      'WhatsApp',
      'Emails',
      'Events',
    ])
    expect(
      moveVisibleTab(withHiddenFirst, [tabs[0], tabs[1], tabs[2]], 2, 0),
    ).toEqual(['Events', 'WhatsApp', 'Activity', 'Emails'])
  })
})
