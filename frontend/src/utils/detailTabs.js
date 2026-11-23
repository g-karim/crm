const GROUPS = [
  { name: 'data', label: 'Data', icon: 'sliders', views: ['Details', 'Data'] },
  {
    name: 'activity',
    label: 'Activity',
    icon: 'activity',
    views: ['Activity', 'Tasks', 'Events', 'Comments', 'Notes'],
  },
  {
    name: 'communication',
    label: 'Communication',
    icon: 'message-square',
    views: ['Emails', 'Calls', 'Messenger', 'WhatsApp'],
  },
  {
    name: 'documents',
    label: 'Documents',
    icon: 'file-text',
    views: ['Documents', 'Settlements', 'Fulfillment', 'Attachments'],
  },
]

const VIEW_LABELS = {
  Activity: 'History',
  Events: 'Meetings',
  Attachments: 'Files',
  Settlements: 'Расчёты',
  Fulfillment: 'Исполнение',
  Details: 'Record details',
  Data: 'Additional fields',
}

export function detailViewLabel(tab) {
  return VIEW_LABELS[tab?.name] || tab?.label || tab?.name || ''
}

// Keep the existing view names and indices: links and activity actions still
// address the same view even though the navigation now groups them.
export function groupDetailTabs(tabs = []) {
  const known = new Set(GROUPS.flatMap((group) => group.views))
  return GROUPS.map((group) => {
    const names =
      group.name === 'data'
        ? [
            ...group.views,
            ...tabs
              .filter((tab) => !known.has(tab.name))
              .map((tab) => tab.name),
          ]
        : group.views
    const views = names.flatMap((name) => {
      const index = tabs.findIndex((tab) => tab.name === name)
      return index < 0 ? [] : [{ ...tabs[index], index }]
    })
    return { ...group, views }
  }).filter((group) => group.views.length)
}

export function detailTabIndex(tabs = [], name) {
  const normalized = String(name || '')
    .replace(/^#/, '')
    .toLowerCase()
  const index = tabs.findIndex((tab) => tab.name.toLowerCase() === normalized)
  if (index >= 0) return index
  if (!normalized) {
    const details = tabs.findIndex((tab) => tab.name === 'Details')
    if (details >= 0) return details
    const data = tabs.findIndex((tab) => tab.name === 'Data')
    if (data >= 0) return data
  }
  const history = tabs.findIndex((tab) => tab.name === 'Activity')
  return history >= 0 ? history : 0
}
