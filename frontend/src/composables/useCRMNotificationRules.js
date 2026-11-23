import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { call, frappeRequest } from 'frappe-ui'

export const newRule = () => ({
  id: crypto.randomUUID().replaceAll('-', ''), name: '', enabled: true,
  object: 'CRM Lead', event: 'lead_status_changed', scope: 'selected',
  record_ids: [], statuses: [], to_statuses: [], owners: [], sources: [], pipelines: [],
  channels: { crm_push: true, one_message: false, one_push: false, email: false }, include_self: false,
})

export function useCRMNotificationRules() {
  const state = ref(null), options = ref(null), draft = ref(newRule())
  const draftRevision = ref(0), dirty = ref(false), busy = ref(false), pending = ref(null)
  const error = ref(''), feedback = ref(''), preview = ref(null), mode = ref('rules')
  const channelDraft = ref({ crm_push: false, one_message: false, one_push: false, email: false, sender: '' })
  const channelDirty = ref(false), channelBase = ref(null)
  const hasDraft = ref(false)
  const conflict = computed(() => dirty.value && state.value?.revision !== draftRevision.value)
  const channelConflict = computed(() => channelDirty.value && channelBase.value && state.value &&
    (channelBase.value.revision !== state.value.revision ||
      channelBase.value.crm_push !== state.value.master_revisions.crm_push ||
      channelBase.value.one_message !== state.value.master_revisions.one_message))
  const viewer = () => state.value?.viewer
  const rpc = (module, method, values = {}) => {
    const params = { ...values, ...(viewer() ? { expected_viewer: viewer() } : {}) }
    const url = `crm.notification_rules.${module}.${method}`
    return ['get_settings', 'options', 'search_records', 'people', 'record_state'].includes(method)
      ? frappeRequest({ url, method: 'GET', params }) : call(url, params)
  }
  const mutationId = () => crypto.randomUUID().replaceAll('-', '')
  const clone = value => JSON.parse(JSON.stringify(value))

  function adopt(next) {
    if (viewer() && next.viewer !== viewer()) throw new Error('SessionChanged')
    state.value = next
    if (!masterChannel && typeof BroadcastChannel === 'function') {
      masterChannel = new BroadcastChannel(`exp-notifications:${next.viewer}`)
      masterChannel.addEventListener('message', refresh)
    }
    if (!dirty.value) draftRevision.value = next.revision
    if (!channelDirty.value) {
      channelDraft.value = { ...next.masters, sender: next.sender || '' }
      channelBase.value = { revision: next.revision, ...next.master_revisions }
    }
  }
  async function reload(quiet = false) {
    try {
      adopt(await rpc('api', 'get_settings'))
      if (!options.value) options.value = await rpc('api', 'options')
      if (!quiet) feedback.value = pending.value ? 'Retry the pending save to confirm its result.' : 'Settings refreshed. Your draft is preserved.'
    } catch { error.value = 'Could not load notification settings.' }
  }
  function edit(rule = newRule()) {
    if (pending.value || busy.value) return
    if (rule.unavailable_selection_count) {
      error.value = 'Some selected records are no longer available. Remove the unavailable selection before saving.'
      return
    }
    const value = clone(rule)
    value.channels = { email: false, ...value.channels }
    delete value.unavailable_selection_count
    draft.value = value
    draftRevision.value = state.value.revision
    dirty.value = false; preview.value = null; error.value = ''; feedback.value = ''
    mode.value = 'builder'
    hasDraft.value = true
  }
  function markDirty() { dirty.value = true; preview.value = null; feedback.value = '' }
  async function execute(operation) {
    if (busy.value) return
    busy.value = true; error.value = ''; feedback.value = 'Saving…'
    pending.value = operation
    try {
      const next = await rpc(operation.module, operation.method, operation.args)
      adopt(next); pending.value = null
      if (operation.method === 'save_rule') { dirty.value = false; draftRevision.value = next.revision }
      if (operation.method === 'save_channels') {
        channelDirty.value = false
        channelDraft.value = { ...next.masters, sender: next.sender || '' }
        channelBase.value = { revision: next.revision, ...next.master_revisions }
        if (dirty.value && draftRevision.value === operation.args.expected_revision) draftRevision.value = next.revision
      }
      feedback.value = 'Notification settings saved.'
      channel?.postMessage({ viewer: next.viewer, revision: next.revision })
    } catch (exception) {
      const text = `${exception?.exc_type || ''} ${exception?.exception || ''} ${exception?.message || ''}`
      const definitive = /TimestampMismatch|ValidationError|PermissionError|AuthenticationError|mandatory|Invalid|not available/i.test(text)
      if (definitive) pending.value = null
      error.value = /TimestampMismatch/.test(text)
        ? 'Settings changed in another window. Refresh and review before saving.'
        : definitive ? 'Check the selected records, conditions and delivery channels.'
          : 'The save result is unknown. Retry the same request.'
      feedback.value = ''
      if (definitive) await reload()
    } finally { busy.value = false }
  }
  function operation(module, method, values, revision = state.value.revision) {
    return { module, method, args: { ...clone(values), expected_revision: revision, mutation_id: mutationId() } }
  }
  function saveRule() {
    return execute(pending.value || operation('api', 'save_rule', { values: draft.value }, draftRevision.value))
  }
  function saveChannels() {
    const base = channelBase.value
    return execute(pending.value || operation('controls', 'save_channels', {
      ...channelDraft.value, sender: channelDraft.value.sender || null,
      expected_primary_revision: base.crm_push, expected_one_revision: base.one_message,
    }, base.revision))
  }
  async function toggleRule(rule) {
    if (pending.value || busy.value) return
    const values = clone(rule); delete values.unavailable_selection_count
    return execute(operation('api', 'save_rule', { values: { ...values, enabled: !rule.enabled } }))
  }
  async function deleteRule(rule) {
    if (pending.value || busy.value) return
    return execute(operation('api', 'delete_rule', { rule_id: rule.id }))
  }
  async function previewRule() {
    error.value = ''; preview.value = null
    try { preview.value = await rpc('preview', 'preview_rule', { values: clone(draft.value) }) }
    catch { error.value = 'Check the selected records and conditions before previewing.' }
  }
  function rebase() { draftRevision.value = state.value.revision; feedback.value = 'Review your draft before saving it against the current version.' }
  function rebaseChannels() {
    channelBase.value = { revision: state.value.revision, ...state.value.master_revisions }
    feedback.value = 'Review your draft before saving it against the current version.'
  }
  const search = (doctype, query) => rpc('api', 'search_records', { doctype, query })
  const people = query => rpc('controls', 'people', { query })
  const channel = typeof BroadcastChannel === 'function' ? new BroadcastChannel('exp-crm-rules') : null
  let masterChannel
  function refresh(event) { if (!busy.value && (!event?.data?.viewer || event.data.viewer === viewer())) void reload(true) }
  let timer
  onMounted(() => {
    void reload(); timer = setInterval(refresh, 30000)
    window.addEventListener('focus', refresh)
    channel?.addEventListener('message', refresh)
  })
  onBeforeUnmount(() => { clearInterval(timer); window.removeEventListener('focus', refresh); channel?.close(); masterChannel?.close() })
  return { state, options, draft, draftRevision, dirty, busy, pending, error, feedback, preview, mode,
    channelDraft, channelDirty, channelConflict, conflict, hasDraft, reload, edit, markDirty, saveRule, saveChannels,
    toggleRule, deleteRule, previewRule, rebase, rebaseChannels, search, people,
    retry: () => pending.value && execute(pending.value) }
}
