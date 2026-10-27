export const callOutcomes = [
  'Agreed',
  'Callback',
  'Not interested',
  'Wrong number',
]

// Native CRM datetimes use the site's timezone. This is the inverse of native
// dayjsLocal, using the public frappe-ui dayjs/config interface.
export function callbackDeadline(value, dayjs, systemTimezone, localTimezone) {
  if (!value) return ''
  const date = systemTimezone
    ? dayjs.tz(value, localTimezone).tz(systemTimezone)
    : dayjs(value)
  return date.isValid() ? date.format('YYYY-MM-DD HH:mm:ss') : ''
}

export function seekRecording(current, duration, delta) {
  if (!Number.isFinite(duration) || duration < 0) return null
  return Math.min(
    duration,
    Math.max(0, (Number.isFinite(current) ? current : 0) + delta),
  )
}

// An unknown response retries the exact operation. Fields are disabled until it
// resolves; changing the selected call never applies an old response to a new one.
export async function saveFollowup(
  state,
  { request, endpoint, params, isCurrent = () => true },
) {
  if (state.saving || state.conflict) return null
  if (!state.pending)
    state.pending = { endpoint, params: JSON.parse(JSON.stringify(params)) }
  state.saving = true
  state.error = ''
  try {
    const result = await request(state.pending.endpoint, state.pending.params)
    if (!isCurrent()) return null
    state.pending = null
    return result
  } catch (error) {
    if (!isCurrent()) return null
    const type =
      error?.exc_type || error?.exception?.split(':')[0]?.split('.').pop()
    if (
      [
        'ValidationError',
        'PermissionError',
        'AuthenticationError',
        'DoesNotExistError',
        'TimestampMismatchError',
      ].includes(type)
    ) {
      state.pending = null
      state.conflict = type === 'TimestampMismatchError'
      state.error = state.conflict
        ? 'The call outcome or task changed. Your input is kept; reload before saving.'
        : 'Could not save. Check the customer, assignee, deadline and access.'
    } else {
      state.error =
        'The result is unknown. Retry the same save before making changes.'
    }
    return null
  } finally {
    state.saving = false
  }
}
