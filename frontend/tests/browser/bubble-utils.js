// Date labels only; preserve real message components without loading CRM stores.
export function formatDate(value, format) {
  return format === 'HH:mm' ? String(value).slice(11, 16) : value
}
