import { normalizeExolveNumber } from '@/utils/exolveClient'

export function dialNumber(value) {
  try {
    return normalizeExolveNumber(value)
  } catch {
    return ''
  }
}

export function customerTypeKey(doctype) {
  return (
    { 'CRM Lead': 'Lead', 'CRM Deal': 'Deal', Contact: 'Contact' }[doctype] ||
    doctype
  )
}

export function displayPhone(value) {
  const number = dialNumber(value)
  if (!number) return String(value || '')
  if (number.length === 11 && number.startsWith('7')) {
    return `+7 ${number.slice(1, 4)} ${number.slice(4, 7)}-${number.slice(7, 9)}-${number.slice(9)}`
  }
  return '+' + number
}

export function callDuration(value) {
  const seconds = Math.max(0, Math.floor(Number(value) || 0))
  const minutes = Math.floor(seconds / 60)
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`
}

export function callCalendarDate(value, locale = 'en') {
  const date = new Date(String(value || '').slice(0, 10) + 'T12:00:00Z')
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat(String(locale).replace('_', '-'), {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(date)
}

export function isMissedCall(call) {
  return (
    call.type === 'Incoming' &&
    ['No Answer', 'Busy', 'Failed', 'Canceled'].includes(call.status)
  )
}

export function callStatusKey(call) {
  if (call.status === 'No Answer' && call.type === 'Incoming')
    return 'Missed Call'
  return (
    {
      Completed: 'Call completed',
      Failed: 'Call failed',
      Busy: 'Line busy',
      'No Answer': 'No answer',
      Canceled: 'Call canceled',
      Initiated: 'Initiated',
      Ringing: 'Ringing',
      'In Progress': 'Call in Progress',
      Queued: 'Queued',
    }[call.status] || 'Unknown status'
  )
}

export function groupCalls(calls) {
  const groups = new Map()
  for (const call of calls) {
    const date = String(call.timestamp || '').slice(0, 10)
    if (!groups.has(date)) groups.set(date, [])
    groups.get(date).push(call)
  }
  return [...groups].map(([date, calls]) => ({ date, calls }))
}

export function mergeCalls(current, incoming) {
  return [
    ...new Map(
      [...current, ...incoming].map((call) => [call.name, call]),
    ).values(),
  ]
}
