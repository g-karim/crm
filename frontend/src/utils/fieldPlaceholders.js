const PLACEHOLDER_LABELS = {
  'Planned Deal Pipeline': 'ожидаемую воронку',
  Territory: 'территорию',
  'Primary phone': 'основной телефон',
  'Primary Phone': 'основной телефон',
}

export function getPlaceholderLabel(label) {
  if (!label) return ''
  return PLACEHOLDER_LABELS[label] || __(label)
}
