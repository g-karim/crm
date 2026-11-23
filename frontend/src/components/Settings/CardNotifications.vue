<template>
  <template v-if="available">
    <Button class="min-h-11" icon="bell" :aria-label="__('Notifications for this record')" :title="__('Notifications for this record')" @click="openDialog" />
    <Dialog v-model:open="open" :options="{ title: __('Notifications for this record'), size: 'sm' }">
      <template #body-content><div class="space-y-4 text-base leading-6">
        <p>{{ __('Following does not grant record access. Delivery depends on your active CRM rules.') }}</p>
        <p v-if="error" role="alert" class="text-ink-red-8">{{ __(error) }}</p>
        <p v-if="!state" role="status">{{ __('Loading…') }}</p>
        <fieldset v-else :disabled="busy || !!pending" class="space-y-2">
          <label class="flex min-h-11 cursor-pointer items-center gap-3"><input v-model="draft.followed" type="checkbox" class="size-5" />{{ __('Follow this record') }}</label>
          <label class="flex min-h-11 cursor-pointer items-center gap-3"><input v-model="draft.muted" type="checkbox" class="size-5" />{{ __('Mute delivery for this record') }}</label>
        </fieldset>
        <p v-if="state && draft.followed && !state.has_follow_rule" role="status" class="rounded bg-surface-gray-2 p-3 text-sm">{{ __('No active followed-record rule exists. Following alone does not enable delivery.') }}</p>
        <RouterLink :to="{ path: '/notification-rules', query: { object: doctype, record: String(recordId), preset: draft.followed ? 'following' : 'selected' } }" class="inline-flex min-h-11 items-center underline" @click="open = false">{{ __('Configure notification rules') }}</RouterLink>
        <div class="flex flex-wrap gap-3"><Button class="min-h-11" :label="pending ? __('Retry the same save') : __('Save')" :disabled="!state || busy" variant="solid" @click="save" />
          <Button class="min-h-11" :label="__('Refresh settings')" :disabled="busy || !!pending" @click="load" /></div>
        <p v-if="feedback" role="status">{{ __(feedback) }}</p>
      </div></template>
    </Dialog>
  </template>
</template>
<script setup>
import { ref, computed } from 'vue'
import { Button, Dialog, call, frappeRequest } from 'frappe-ui'
const props = defineProps({ doctype: String, recordId: [String, Number] })
const available = computed(() => !!window.exp_notification_rules_available)
const open = ref(false), state = ref(null), draft = ref({ followed: false, muted: false })
const pending = ref(null), busy = ref(false), error = ref(''), feedback = ref('')
async function load() {
  try {
    state.value = await frappeRequest({ url: 'crm.notification_rules.controls.record_state', method: 'GET', params: { doctype: props.doctype, record_id: String(props.recordId) } })
    draft.value = { followed: state.value.followed, muted: state.value.muted }; error.value = ''
  } catch { error.value = 'This CRM record is not available.' }
}
async function openDialog() { open.value = true; if (!pending.value) await load() }
async function save() {
  if (busy.value) return
  pending.value ||= { doctype: props.doctype, record_id: String(props.recordId), ...draft.value,
    expected_revision: state.value.revision, expected_viewer: state.value.viewer,
    mutation_id: crypto.randomUUID().replaceAll('-', '') }
  busy.value = true; error.value = ''
  try {
    const result = await call('crm.notification_rules.api.set_record', pending.value)
    pending.value = null; feedback.value = 'Notification settings saved.'
    const channel = new BroadcastChannel('exp-crm-rules'); channel.postMessage({ viewer: result.viewer, revision: result.revision }); channel.close()
    await load()
  } catch (exception) {
    const text = `${exception?.exc_type || ''} ${exception?.exception || ''} ${exception?.message || ''}`
    const definitive = /TimestampMismatch|ValidationError|PermissionError|AuthenticationError/.test(text)
    if (definitive) pending.value = null
    error.value = definitive ? 'Settings changed in another window. Refresh and review before saving.' : 'The save result is unknown. Retry the same request.'
  } finally { busy.value = false }
}
</script>
