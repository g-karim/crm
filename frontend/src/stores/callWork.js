import { defineStore } from 'pinia'
import { computed, onScopeDispose, ref, watch } from 'vue'
import { call } from 'frappe-ui'
import { sessionStore } from './session'
import { normalizeExolveNumber } from '@/utils/exolveClient'
import {
  createDraftSync,
  draftSnapshot,
  draftFingerprint,
  durableWork,
  restoreConversation,
  refreshCanonicalWork,
} from '@/utils/callDrafts'
import {
  createWorkItem,
  contextLocked,
  itemDirty,
  resultValues,
  saveWorkItem,
  workHasContent,
  workSnapshot,
} from '@/utils/callWork'

function normalized(value) {
  try {
    return normalizeExolveNumber(value)
  } catch {
    return String(value || '').trim()
  }
}

export const callWorkStore = defineStore('crm-call-work', () => {
  const session = sessionStore()
  const viewer = session.user
  const works = ref([])
  const currentId = ref(null)
  const current = computed(
    () => works.value.find((item) => item.id === currentId.value) || null,
  )
  const hasDraft = computed(() =>
    works.value.some((work) => [work.note, ...work.tasks].some(itemDirty)),
  )

  const controllers = new Map()
  const restoring = ref(false),
    restoreError = ref(''),
    hasMoreDrafts = ref(false)
  let restoreOffset = 0,
    restored = false
  function sync(work) {
    if (!controllers.has(work.id))
      controllers.set(
        work.id,
        createDraftSync({
          work,
          request: call,
          viewer,
          isCurrentViewer: () => session.user === viewer,
        }),
      )
    return controllers.get(work.id)
  }
  watch(
    () => works.value.map((work) => draftFingerprint(work)),
    () => {
      for (const work of works.value)
        if (durableWork(work)) sync(work).schedule()
    },
  )
  const hasUnsyncedDraft = computed(() =>
    works.value.some(
      (work) =>
        durableWork(work) &&
        work.draft?.acknowledged !== draftFingerprint(work),
    ),
  )
  async function restore(more = false) {
    if (restoring.value || (restored && !more)) return
    restoring.value = true
    restoreError.value = ''
    try {
      const data = await call('crm.api.call_drafts.list_drafts', {
        offset: more ? restoreOffset : 0,
      })
      if (data.viewer !== viewer || session.user !== viewer) return
      for (const record of data.drafts)
        if (!works.value.some((work) => work.id === record.snapshot.id))
          works.value.push(restoreConversation(record))
      if (!currentId.value && works.value.length)
        currentId.value = works.value[0].id
      restoreOffset = data.next_offset
      hasMoreDrafts.value = data.has_more
      restored = true
    } catch {
      restoreError.value = 'Could not restore conversation drafts. Try again.'
    } finally {
      restoring.value = false
    }
  }
  async function retryDraft(work) {
    try {
      await sync(work).retry()
    } catch {
      /* Status stays next to the editor. */
    }
  }
  async function flushDraft(work) {
    await sync(work).flush()
  }
  async function reloadDraft(work) {
    try {
      // Preserve the local version as another durable private draft before
      // opening the other tab's version. Neither action creates CRM records.
      let backup = works.value.find(
        (row) => row.id === work.draft.localBackupId,
      )
      if (!backup) {
        const snapshot = draftSnapshot(work)
        snapshot.id = crypto.randomUUID()
        snapshot.created = new Date().toISOString()
        backup = restoreConversation({
          snapshot,
          revision: 0,
          call_log: null,
          modified: null,
        })
        backup.draft.acknowledged = ''
        backup.draft.state = 'idle'
        works.value.push(backup)
        backup = works.value[works.value.length - 1]
        work.draft.localBackupId = backup.id
      }
      await flushDraft(backup)
      const data = await call('crm.api.call_drafts.get_draft', {
        work_id: work.id,
      })
      if (data.viewer !== viewer || session.user !== viewer || !data.draft)
        return
      sync(work).dispose()
      controllers.delete(work.id)
      Object.assign(work, restoreConversation(data.draft))
      work.draft.backup = backup.id
    } catch {
      work.draft.error = 'Could not restore conversation drafts. Try again.'
    }
  }
  function restoreLocalDraft(work) {
    if (works.value.some((row) => row.id === work.draft.backup))
      currentId.value = work.draft.backup
  }
  async function openLinked(callLog) {
    const data = await call('crm.api.call_drafts.get_draft', {
      call_log: callLog,
    })
    if (data.viewer !== viewer || session.user !== viewer || !data.draft)
      return null
    const existing = works.value.find(
      (work) => work.id === data.draft.snapshot.id,
    )
    if (existing) {
      refreshCanonicalWork(existing, data.draft.latest)
      existing.call_log = data.draft.call_log
      currentId.value = existing.id
      return existing
    }
    const work = restoreConversation(data.draft)
    works.value.push(work)
    currentId.value = work.id
    return work
  }
  async function linkCall(work, callLog) {
    await flushDraft(work)
    const data = await call('crm.api.call_drafts.link_call', {
      work_id: work.id,
      call_log: callLog,
      expected_revision: work.draft.revision,
      expected_viewer: viewer,
    })
    if (data.viewer !== viewer || session.user !== viewer) return
    work.call_log = data.draft.call_log
    window.dispatchEvent(new CustomEvent('crm-exolve-calls-updated'))
  }
  onScopeDispose(() => {
    for (const controller of controllers.values()) controller.dispose()
  })

  function prepare(number, source = null) {
    // Empty abandoned preparation does not build up a history of blank forms.
    works.value = works.value.filter(
      (work) => work.started || workHasContent(work),
    )
    const work = {
      id: crypto.randomUUID(),
      number: normalized(number),
      created: new Date().toISOString(),
      started: false,
      ended: false,
      context: null,
      candidates: [],
      resolving: false,
      contextError: '',
      contextRequest: 0,
      incoming: false,
      note: createWorkItem('note', {
        title: `${__('Call notes')} · ${new Date().toLocaleString()}`.slice(
          0,
          140,
        ),
        text: '',
      }),
      tasks: [],
    }
    works.value.push(work)
    currentId.value = work.id
    const reactiveWork = current.value
    if (source) resolve(reactiveWork, source)
    return reactiveWork
  }

  async function resolve(work, source) {
    const version = ++work.contextRequest
    work.resolving = true
    work.contextError = ''
    try {
      const result = await call('crm.api.call_work.resolve_context', { source })
      if (
        result.viewer !== viewer ||
        version !== work.contextRequest ||
        contextLocked(work)
      )
        return
      work.candidates = result.contexts
      work.context = result.contexts.length === 1 ? result.contexts[0] : null
    } catch {
      if (version === work.contextRequest)
        work.contextError =
          'Could not read the customer context. Choose an accessible lead or deal.'
    } finally {
      if (version === work.contextRequest) work.resolving = false
    }
  }

  function chooseContext(work, context) {
    if (contextLocked(work)) return
    work.contextRequest++
    work.resolving = false
    work.contextError = ''
    work.context = context
  }

  function numberChanged(number) {
    if (!current.value) {
      if (String(number).trim()) prepare(number)
      return
    }
    if (normalized(number) === current.value.number) return
    if (current.value.started || workHasContent(current.value)) prepare(number)
    else {
      current.value.contextRequest++
      current.value.resolving = false
      current.value.number = normalized(number)
      current.value.context = null
      current.value.candidates = []
    }
  }

  function observe(event) {
    if (['incoming', 'dialing'].includes(event.state)) {
      if (
        !current.value ||
        current.value.ended ||
        (current.value.restored && current.value.started) ||
        (event.state === 'incoming' && !current.value.incoming)
      )
        prepare(event.number)
      current.value.started = true
      current.value.incoming = event.state === 'incoming'
    }
    if (current.value && ['ended', 'failed'].includes(event.state))
      current.value.ended = true
  }

  function addTask(work) {
    work.tasks.push(
      createWorkItem('task', {
        title: '',
        description: '',
        assigned_to: viewer,
        due_date: '',
        status: 'Todo',
        priority: 'Medium',
      }),
    )
  }

  async function save(work, item) {
    if (session.user !== viewer) {
      item.error = 'This customer or record is unavailable. Your draft is kept.'
      return
    }
    const row = await saveWorkItem(item, {
      request: async (url, payload) => {
        await flushDraft(work)
        if (session.user !== viewer)
          throw Object.assign(new Error('Account changed'), {
            exc_type: 'AuthenticationError',
          })
        return call(url, payload)
      },
      viewer,
      context: work.context,
      isCurrentViewer: () => session.user === viewer,
    })
    if (row)
      window.dispatchEvent(
        new CustomEvent('crm-call-work-saved', {
          detail: { kind: item.kind, context: work.context, name: item.name },
        }),
      )
  }

  async function reload(work, item) {
    if (!item.name || item.saving) return
    item.saving = true
    try {
      const data = await call('crm.api.call_work.get_item', {
        kind: item.kind,
        name: item.name,
        context_kind: work.context.kind,
        context_name: work.context.name,
      })
      if (data.viewer !== viewer) throw new Error('Account changed')
      item.backup = structuredClone(JSON.parse(JSON.stringify(item.values)))
      const row = data[item.kind]
      item.values = resultValues(item.kind, row)
      item.modified = row.modified
      item.snapshot = workSnapshot(item.kind, item.values)
      item.conflict = false
      item.error = ''
      item.pending = null
    } catch {
      item.error = 'This customer or record is unavailable. Your draft is kept.'
    } finally {
      item.saving = false
    }
  }

  function setField(item, field, value) {
    item.values[field] = value
  }
  function restoreDraft(item) {
    item.values = item.backup
    item.backup = null
  }

  return {
    works,
    restoring,
    restoreError,
    hasMoreDrafts,
    hasUnsyncedDraft,
    restore,
    retryDraft,
    flushDraft,
    reloadDraft,
    restoreLocalDraft,
    openLinked,
    linkCall,
    currentId,
    current,
    hasDraft,
    prepare,
    resolve,
    chooseContext,
    numberChanged,
    observe,
    addTask,
    save,
    reload,
    setField,
    restoreDraft,
  }
})
