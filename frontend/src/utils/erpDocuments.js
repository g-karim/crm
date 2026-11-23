export function safeDocumentURL(value, origin) {
  if (!value || typeof value !== 'string') return ''
  try {
    const url = new URL(value, origin)
    if (url.origin !== origin || !['http:', 'https:'].includes(url.protocol))
      return ''
    return url.href
  } catch {
    return ''
  }
}

export function currentDocumentIssues(issues) {
  const order = [
    'Quotation',
    'Contract',
    'RU Contract Appendix',
    'RU Payment Invoice',
    'Delivery Note',
    'Sales Invoice',
    'RU Acceptance Act',
    'RU Reconciliation',
    'RU Tax Invoice',
  ]
  const rank = (issue) => {
    const i = order.indexOf(issue.doctype)
    return i < 0 ? order.length : i
  }
  return issues
    .filter((issue) => issue.state === 'Действует')
    .sort((a, b) => rank(a) - rank(b))
}
