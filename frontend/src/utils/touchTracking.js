export function usesDefaultTouchSort(view) {
  return !view || (Boolean(view.is_standard) && !view.order_by)
}

export function touchExportEndpoint(doctype, orderBy) {
  const touchOrder = String(orderBy || '')
    .split(',')
    .some((part) => part.trim().split(/\s+/)[0] === 'last_touch_at')
  return ['CRM Lead', 'CRM Deal'].includes(doctype) && touchOrder
    ? 'crm.touch_tracking_export.export_query'
    : 'frappe.desk.reportview.export_query'
}

export function touchSettingsDirty(current, original) {
  if (!current || !original) return false
  const canonical = (value) =>
    Object.fromEntries(
      Object.entries(value)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([key, item]) => [
          key,
          Array.isArray(item) ? [...new Set(item)].sort() : item,
        ]),
    )
  return (
    JSON.stringify(canonical(current)) !== JSON.stringify(canonical(original))
  )
}

export async function withTouchTimeout(operation, milliseconds = 20000) {
  let timer
  try {
    return await Promise.race([
      operation(),
      new Promise((_, reject) => {
        timer = setTimeout(
          () => reject(new Error('Request timed out. Please retry.')),
          milliseconds,
        )
      }),
    ])
  } finally {
    clearTimeout(timer)
  }
}
