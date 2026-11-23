<template>
  <details class="mt-5 rounded border border-outline-gray-2 p-3 text-base" @toggle="opened">
    <summary class="flex min-h-11 cursor-pointer items-center font-medium">{{ __('Remind me') }}</summary>
    <div class="mt-3 space-y-3" data-personal-reminder>
      <p class="leading-6 text-ink-gray-6">{{ __('Choose a date and time for yourself. The task deadline stays unchanged; moving it does not move this reminder.') }}</p>
      <p v-if="state && !state.available" role="status" class="rounded bg-surface-gray-2 p-3">{{ __('Reminder processing is paused on this site. Your reminder can be saved.') }}</p>
      <fieldset :disabled="busy || Boolean(pending)" class="space-y-3">
        <label class="block space-y-2"><span>{{ __('Remind me at') }} · {{ timezone }}</span>
          <input v-model="date" type="datetime-local" class="min-h-11 w-full min-w-0 rounded border border-outline-gray-2 bg-surface-white px-3" data-personal-at />
        </label>
        <label class="flex min-h-11 items-center gap-2"><input v-model="channels.crm_push" type="checkbox" />{{ __('CRM push') }}</label>
        <label class="flex min-h-11 items-center gap-2"><input v-model="channels.email" type="checkbox" />{{ __('Email') }}</label>
        <label class="flex min-h-11 items-center gap-2"><input v-model="channels.one_message" type="checkbox" @change="!channels.one_message && (channels.one_push = false)" />{{ __('Message in One') }}</label>
        <label class="flex min-h-11 items-center gap-2"><input v-model="channels.one_push" type="checkbox" :disabled="!channels.one_message" />{{ __('Push for this One message') }}</label>
      </fieldset>
      <p class="text-sm leading-5 text-ink-gray-6">{{ __('One reminder, checked every minute. Completing the task cancels pending delivery. Missed reminders expire after 15 minutes.') }}</p>
      <p v-if="state" class="text-sm leading-5 text-ink-gray-6">{{ __('Your main delivery switches still apply. Changing this reminder does not change them.') }}</p>
      <p v-if="error" role="alert" class="text-ink-red-3">{{ __(error) }}</p>
      <p v-if="feedback" role="status">{{ __(feedback) }}</p>
      <button type="button" class="min-h-11 rounded bg-surface-gray-7 px-4 text-ink-white disabled:opacity-50" :disabled="busy || (!pending && ['Done', 'Canceled'].includes(taskStatus))" @click="save">{{ busy ? __('Saving…') : pending ? __('Retry the same request') : __('Save reminder') }}</button>
      <ul class="space-y-2" aria-live="polite"><li v-for="item in state?.items || []" :key="item.id" class="flex flex-wrap items-center justify-between gap-2 border-t border-outline-gray-2 pt-2">
        <span>{{ format(item.at) }} · {{ __(item.state) }}</span>
        <button v-if="['Scheduled', 'Fired'].includes(item.state)" type="button" class="min-h-11 rounded border border-outline-gray-2 px-3" :disabled="busy || Boolean(pending)" @click="cancel(item)">{{ __(item.state === 'Fired' ? 'Cancel pending delivery' : 'Cancel reminder') }}</button>
      </li></ul>
    </div>
  </details>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { call, frappeRequest } from 'frappe-ui'
import { sessionStore } from '@/stores/session'
import { scheduleOperation, definitiveReminderError } from '@/utils/personalReminder'

const props = defineProps({ task: { type: [String, Number], required: true }, taskStatus: { type: String, default: '' } })
const { user } = sessionStore()
const state = ref(null), date = ref(''), busy = ref(false), pending = ref(null), error = ref(''), feedback = ref('')
const channels = ref({ crm_push: true, one_message: false, one_push: false, email: false })
const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
const storageKey = computed(() => `exp-personal-reminder:${user}:${props.task}`)
const format = value => new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
function persist() {
  try {
    if (pending.value) sessionStorage.setItem(storageKey.value, JSON.stringify(pending.value))
    else sessionStorage.removeItem(storageKey.value)
  } catch { /* The pending operation remains available in this tab. */ }
}
async function reload() {
  const value = await frappeRequest({ url: 'crm.notification_rules.personal_reminders.list_reminders', method: 'GET', params: { task: String(props.task), expected_viewer: user } })
  if (value.viewer !== user) throw new Error('SessionChanged')
  state.value = value
}
async function opened(event) { if (event.target.open && !state.value) { try { await reload() } catch { error.value = 'Could not load your reminders. Try again.' } } }
async function execute(operation) {
  if (busy.value) return
  busy.value = true; error.value = ''; feedback.value = ''; pending.value = operation; persist()
  try {
    const result = await call(`crm.notification_rules.personal_reminders.${operation.method}`, operation.args)
    if (result.viewer !== user) throw new Error('SessionChanged')
    pending.value = null; persist(); feedback.value = operation.method === 'cancel' ? 'Reminder cancelled.' : 'Reminder saved.'
    try { await reload() } catch { error.value = 'Could not load your reminders. Try again.' }
  } catch (exception) {
    if (definitiveReminderError(exception)) { pending.value = null; persist(); error.value = 'Check the date, task access and delivery channels.'; try { await reload() } catch { /* Preserve the definitive error above. */ } }
    else error.value = 'The result is unknown. Retry the same request.'
  } finally { busy.value = false }
}
function save() {
  try { return execute(pending.value || scheduleOperation(props.task, date.value, channels.value, user)) }
  catch (exception) { error.value = exception.message }
}
const cancel = item => execute({ method: 'cancel', args: { reminder: item.id, expected_revision: item.revision, expected_viewer: user } })
onMounted(() => {
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey.value))
    if (!['schedule', 'cancel'].includes(saved?.method) || saved.args?.expected_viewer !== user || (saved.args.task && saved.args.task !== String(props.task))) return
    pending.value = saved
    if (saved.method === 'schedule') {
      const value = new Date(saved.args.at)
      const pad = number => String(number).padStart(2, '0')
      date.value = `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}T${pad(value.getHours())}:${pad(value.getMinutes())}`
      channels.value = { ...saved.args.channels }
    }
  } catch { /* Ignore invalid local draft data. */ }
})
</script>
