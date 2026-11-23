// Preserve one immutable operation until the server confirms its outcome.
export function scheduleOperation(task, value, channels, viewer, id = crypto.randomUUID().replaceAll('-', '')) {
  const date = new Date(value)
  if (!value || !Number.isFinite(date.getTime()) || date.getTime() <= Date.now()) throw new Error('Choose a future date and time.')
  const at = date.toISOString().replace('.000Z', 'Z')
  if ((!channels.crm_push && !channels.one_message && !channels.email) || (channels.one_push && !channels.one_message)) throw new Error('Choose a delivery channel.')
  return { method: 'schedule', args: { task: String(task), at, channels: { ...channels }, mutation_id: id, expected_viewer: viewer } }
}

export function definitiveReminderError(error) {
  return /ValidationError|PermissionError|AuthenticationError|TimestampMismatch|DoesNotExistError/.test(`${error?.exc_type || ''} ${error?.exception || ''}`)
}
