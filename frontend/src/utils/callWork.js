const rejected = new Set([
  'ValidationError',
  'MandatoryError',
  'LinkValidationError',
  'InvalidSelectValueError',
  'PermissionError',
  'AuthenticationError',
  'DoesNotExistError',
  'TimestampMismatchError',
])

export function workValues(kind, values) {
  if (kind === 'note')
    return { title: values.title.trim(), text: values.text.trim() }
  let due = (values.due_date || '').replace('T', ' ')
  if (due.length === 16) due += ':00'
  return {
    title: values.title.trim(),
    description: (values.description || '').trim(),
    assigned_to: values.assigned_to || '',
    due_date: due,
    status: values.status,
    priority: values.priority,
  }
}

export function workSnapshot(kind, values) {
  return JSON.stringify(workValues(kind, values))
}

export function createWorkItem(kind, values) {
  return {
    key: crypto.randomUUID(),
    kind,
    values,
    name: null,
    modified: null,
    snapshot: workSnapshot(kind, values),
    pending: null,
    saving: false,
    error: '',
    conflict: false,
    backup: null,
  }
}

export function itemDirty(item) {
  return (
    Boolean(item.pending) ||
    item.snapshot !== workSnapshot(item.kind, item.values)
  )
}

export function workHasContent(work) {
  return [work.note, ...work.tasks].some((item) => item.name || itemDirty(item))
}

export function contextLocked(work) {
  return [work.note, ...work.tasks].some(
    (item) => item.name || item.pending || item.saving,
  )
}

export function resultValues(kind, row) {
  if (kind === 'note') return { title: row.title, text: row.text }
  return {
    title: row.title,
    description: row.description_text || '',
    assigned_to: row.assigned_to || '',
    due_date: row.due_date ? row.due_date.replace(' ', 'T').slice(0, 16) : '',
    status: row.status,
    priority: row.priority,
  }
}

// Freeze an uncertain request: retry its exact UUID/payload before later edits.
// The item object belongs to one work session; a late response cannot retarget it.
export async function saveWorkItem(
  item,
  {
    request,
    viewer,
    context,
    mutationId = () => crypto.randomUUID(),
    isCurrentViewer = () => true,
  },
) {
  if (item.saving || item.conflict) return
  if (!context) {
    item.error = 'Choose a lead or deal before saving.'
    return
  }
  if (!item.pending)
    item.pending = {
      name: item.name,
      expected_modified: item.modified,
      expected_viewer: viewer,
      mutation_id: mutationId(),
      values: {
        ...workValues(item.kind, item.values),
        context_kind: context.kind,
        context_name: context.name,
      },
    }
  item.saving = true
  item.error = ''
  const pending = item.pending
  const sent = workSnapshot(item.kind, pending.values)
  try {
    const response = await request(
      `crm.api.call_work.save_${item.kind}`,
      pending,
    )
    if (!isCurrentViewer())
      throw Object.assign(new Error('Account changed'), {
        exc_type: 'AuthenticationError',
      })
    const row = response[item.kind]
    const values = resultValues(item.kind, row)
    const saved = workSnapshot(item.kind, values)
    item.name = String(row.name)
    item.modified = row.modified
    item.snapshot = saved
    if (workSnapshot(item.kind, item.values) === sent && saved === sent)
      item.values = values
    item.conflict = Boolean(response.replayed && saved !== sent)
    item.error = item.conflict
      ? 'This record changed in another window. Your draft is kept.'
      : ''
    item.pending = null
    return row
  } catch (error) {
    if (rejected.has(error.exc_type)) item.pending = null
    item.conflict = error.exc_type === 'TimestampMismatchError'
    item.error = item.conflict
      ? 'This record changed in another window. Your draft is kept.'
      : [
            'PermissionError',
            'AuthenticationError',
            'DoesNotExistError',
          ].includes(error.exc_type)
        ? 'This customer or record is unavailable. Your draft is kept.'
        : item.pending
          ? 'Saving was not confirmed. Retry safely; your draft is kept.'
          : 'Could not save. Check the fields, customer access and assignee.'
  } finally {
    item.saving = false
  }
}
