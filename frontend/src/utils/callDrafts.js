import {
  itemDirty,
  resultValues,
  workHasContent,
  workSnapshot,
} from './callWork'

export function draftSnapshot(work) {
  const item = (row) => ({
    key: row.key,
    kind: row.kind,
    values: JSON.parse(JSON.stringify(row.values)),
    name: row.name || null,
    modified: row.modified || null,
    snapshot: row.snapshot,
    pending: row.pending ? JSON.parse(JSON.stringify(row.pending)) : null,
    conflict: Boolean(row.conflict),
    backup: row.backup ? JSON.parse(JSON.stringify(row.backup)) : null,
  })
  return {
    id: work.id,
    number: work.number,
    created: work.created,
    started: Boolean(work.started),
    ended: Boolean(work.ended),
    incoming: Boolean(work.incoming),
    context: work.context
      ? { kind: work.context.kind, name: String(work.context.name) }
      : null,
    note: item(work.note),
    tasks: work.tasks.map(item),
  }
}
export const draftFingerprint = (work) => JSON.stringify(draftSnapshot(work))
export const durableWork = (work) =>
  Boolean(work.started || work.call_log || workHasContent(work))

export function restoreConversation(record) {
  const data = JSON.parse(JSON.stringify(record.snapshot))
  const hydrate = (item) => ({
    ...item,
    saving: false,
    error: item.pending
      ? 'Saving was not confirmed. Retry safely; your draft is kept.'
      : item.conflict
        ? 'This record changed in another window. Your draft is kept.'
        : '',
  })
  const work = {
    ...data,
    note: hydrate(data.note),
    tasks: data.tasks.map(hydrate),
    candidates: [],
    resolving: false,
    contextError: '',
    contextRequest: 0,
    call_log: record.call_log,
    restored: true,
    draft: {
      revision: record.revision,
      acknowledged: '',
      state: 'saved',
      error: '',
      modified: record.modified,
      pending: null,
      backup: null,
    },
  }
  work.draft.acknowledged = draftFingerprint(work)
  refreshCanonicalWork(work, record.latest)
  if (work.draft.acknowledged !== draftFingerprint(work))
    work.draft.state = 'idle'
  return work
}

export function refreshCanonicalWork(work, latestRecords) {
  for (const item of [work.note, ...work.tasks]) {
    const latest = latestRecords?.[item.key]
    if (latest && !itemDirty(item) && !item.conflict) {
      item.values = resultValues(item.kind, latest)
      item.modified = latest.modified
      item.snapshot = workSnapshot(item.kind, item.values)
    }
  }
}

// One serial queue per conversation, frozen retries and revision checks across tabs.
export function createDraftSync({
  work,
  request,
  viewer,
  isCurrentViewer = () => true,
  delay = 600,
}) {
  let timer,
    flight,
    disposed = false
  work.draft ||= {
    revision: 0,
    acknowledged: '',
    state: 'idle',
    error: '',
    modified: null,
    pending: null,
    backup: null,
  }
  function valid() {
    return !disposed && isCurrentViewer()
  }
  function changed() {
    return draftFingerprint(work) !== work.draft.acknowledged
  }
  async function flush() {
    clearTimeout(timer)
    if (!valid()) throw new Error('Account changed')
    if (flight) {
      await flight
      return flush()
    }
    if (work.draft.state === 'conflict') throw new Error('Draft conflict')
    if (!changed()) return
    const draft = work.draft
    const snapshot = draft.pending?.snapshot || draftSnapshot(work)
    draft.pending ||= {
      snapshot,
      mutation_id: crypto.randomUUID(),
      expected_revision: draft.revision,
      expected_viewer: viewer,
    }
    const payload = draft.pending
    draft.state = 'saving'
    draft.error = ''
    flight = Promise.resolve().then(async () => {
      try {
        const result = await request('crm.api.call_drafts.save_draft', payload)
        if (!valid() || result.viewer !== viewer)
          throw new Error('Account changed')
        draft.revision = result.revision
        draft.modified = result.modified
        draft.acknowledged = JSON.stringify(snapshot)
        draft.pending = null
        draft.state = changed() ? 'idle' : 'saved'
      } catch (error) {
        if (!valid()) throw error
        draft.state =
          error.exc_type === 'TimestampMismatchError' ? 'conflict' : 'error'
        draft.error =
          draft.state === 'conflict'
            ? 'This conversation draft changed in another window. Your text is kept.'
            : 'Could not save the conversation draft. Your text stays in this tab.'
        if (
          [
            'PermissionError',
            'AuthenticationError',
            'ValidationError',
            'DoesNotExistError',
          ].includes(error.exc_type)
        )
          draft.pending = null
        throw error
      }
    })
    const running = flight
    try {
      await running
    } finally {
      if (flight === running) flight = null
    }
    // Typing during a frozen retry is a subsequent version, never overwritten by its reply.
    if (valid() && changed()) return flush()
  }
  function schedule() {
    clearTimeout(timer)
    if (
      !valid() ||
      !durableWork(work) ||
      !changed() ||
      work.draft.state === 'conflict' ||
      work.draft.state === 'error'
    )
      return
    timer = setTimeout(() => flush().catch(() => {}), delay)
  }
  function retry() {
    if (work.draft.state === 'error') work.draft.state = 'idle'
    return flush()
  }
  function dispose() {
    disposed = true
    clearTimeout(timer)
  }
  return { flush, schedule, retry, dispose }
}
