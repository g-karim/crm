export function orderTabs(tabs, savedOrder) {
  const byName = new Map(tabs.map((tab) => [tab.name, tab]))
  const seen = new Set()
  const ordered = []

  for (const name of Array.isArray(savedOrder) ? savedOrder : []) {
    if (!byName.has(name) || seen.has(name)) continue
    ordered.push(byName.get(name))
    seen.add(name)
  }

  return [...ordered, ...tabs.filter((tab) => !seen.has(tab.name))]
}

export function moveVisibleTab(allTabs, visibleTabs, oldIndex, newIndex) {
  if (
    oldIndex === newIndex ||
    oldIndex < 0 ||
    newIndex < 0 ||
    oldIndex >= visibleTabs.length ||
    newIndex >= visibleTabs.length
  ) {
    return null
  }

  const visibleNames = visibleTabs.map((tab) => tab.name)
  const moved = visibleNames.splice(oldIndex, 1)[0]
  visibleNames.splice(newIndex, 0, moved)

  const visible = new Set(visibleNames)
  const nextVisible = visibleNames[Symbol.iterator]()
  return allTabs.map((tab) =>
    visible.has(tab.name) ? nextVisible.next().value : tab.name,
  )
}
