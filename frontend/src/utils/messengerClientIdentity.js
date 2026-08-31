export function isProviderIdentifierLabel(value) {
  let label = String(value || '').trim()
  return (
    /^-?\d{5,}$/.test(label) || /^(?:VK|VK_DIRECT)\s+-?\d{5,}$/i.test(label)
  )
}

export function getMessengerClientDisplayName({ lead, conversation } = {}) {
  let leadFullName = [lead?.first_name, lead?.last_name]
    .filter(Boolean)
    .join(' ')
  let candidates = [lead?.lead_name, leadFullName, conversation?.client_name]
  return (
    candidates
      .map((value) => String(value || '').trim())
      .find((value) => value && !isProviderIdentifierLabel(value)) ||
    __('Client')
  )
}
