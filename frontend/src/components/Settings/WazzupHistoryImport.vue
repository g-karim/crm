<template>
  <section
    v-if="supported"
    data-testid="wazzup-history-import"
    class="min-w-0 rounded-lg border border-outline-gray-1 bg-surface-gray-1 p-3 sm:p-4"
  >
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="text-base-medium text-ink-gray-8">
        {{ __('Wazzup history import') }}
      </div>
      <Button
        :label="__('Refresh import status')"
        variant="subtle"
        :loading="loading"
        :disabled="Boolean(action)"
        @click="refresh(true)"
      />
    </div>
    <p class="mt-2 text-p-sm text-ink-gray-5">
      {{ __('Wazzup may return an incomplete history.') }}
    </p>

    <div
      v-if="status && !showForm"
      class="mt-4 border-t border-outline-gray-2 pt-3"
    >
      <p
        data-testid="wazzup-history-phase"
        class="text-p-medium text-ink-gray-8"
        role="status"
        aria-live="polite"
      >
        {{ __(historyImportStatusLabel(status)) }}
      </p>
      <p
        class="mt-1 text-p-sm text-ink-gray-6"
        data-testid="wazzup-history-period"
        :title="timezone"
      >
        {{ formatHistoryImportTime(status.start_at) }} —
        {{ formatHistoryImportTime(status.end_at) }}
      </p>
      <p
        class="mt-1 text-p-sm text-ink-gray-6"
        data-testid="wazzup-history-policy"
      >
        {{ __(historyImportPolicyLabel(status.policy)) }}
      </p>
      <div
        v-if="summary"
        data-testid="wazzup-history-counts"
        class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-p-sm text-ink-gray-6"
      >
        <p v-if="!status.result && summary.total !== null">
          {{
            __('CSV rows processed: {0} of {1}', [
              summary.processed,
              summary.total,
            ])
          }}
        </p>
        <p v-else-if="!status.result">
          {{ __('CSV rows processed: {0}', [summary.processed]) }}
        </p>
        <p
          v-if="
            !status.result &&
            status.progress?.replay_total !== null &&
            status.progress?.replay_total > 0
          "
        >
          {{
            __('Deferred rows processed: {0} of {1}', [
              status.progress.replay_processed,
              status.progress.replay_total,
            ])
          }}
        </p>
        <p v-for="counter in visibleCounters" :key="counter.key">
          {{ __(counter.label, [counter.value]) }}
        </p>
        <p v-if="summary.conversations_created">
          {{
            __('Conversations created: {0}', [summary.conversations_created])
          }}
        </p>
        <p v-if="summary.leads_created">
          {{ __('Leads created: {0}', [summary.leads_created]) }}
        </p>
      </div>
      <p
        v-if="status.result?.outcome === 'partial'"
        class="mt-2 text-p-sm text-ink-orange-7"
      >
        {{
          __(
            'Some messages were not imported. The counters show the saved result.',
          )
        }}
      </p>
      <p
        v-if="savedError"
        data-testid="wazzup-history-error"
        class="mt-2 text-p-sm text-ink-red-7"
        role="alert"
      >
        {{ __(savedError) }}
      </p>
      <p
        v-if="status.state === 'export_unknown'"
        class="mt-2 text-p-sm text-ink-orange-7"
      >
        {{
          __(
            'The export request will not be repeated automatically. An administrator must review the unknown result.',
          )
        }}
      </p>
      <p v-if="status.duplicate" class="mt-2 text-p-sm text-ink-gray-5">
        {{
          __(
            'An import already exists for this channel. Its saved period and settings are shown.',
          )
        }}
      </p>
      <div v-if="canResume" class="mt-3">
        <p class="mb-2 text-p-sm text-ink-gray-5">
          {{
            __(
              'Continue from the saved processing checkpoint. This does not request another export.',
            )
          }}
        </p>
        <Button
          :label="__('Resume saved processing')"
          variant="subtle"
          :loading="action === 'resume'"
          :disabled="!ready || loading || Boolean(action) || recoveryRequired"
          @click="resume"
        />
      </div>
      <Button
        v-if="!status.active && !showForm"
        class="mt-3"
        :label="__('New history import')"
        variant="subtle"
        :disabled="Boolean(action) || loading"
        @click="openNewImport"
      />
    </div>

    <form
      v-if="showForm"
      class="mt-4 border-t border-outline-gray-2 pt-3"
      @submit.prevent="start"
    >
      <div class="grid gap-3 sm:grid-cols-2">
        <FormControl
          v-model="form.from"
          type="date"
          format="DD.MM.YYYY"
          :placeholder="__('DD.MM.YYYY')"
          align="start"
          :label="__('From date')"
          :disabled="formDisabled"
          required
          data-wazzup-history-from
          data-messenger-import-date
        />
        <FormControl
          v-model="form.through"
          type="date"
          format="DD.MM.YYYY"
          :placeholder="__('DD.MM.YYYY')"
          align="end"
          :label="__('Through date')"
          :disabled="formDisabled"
          required
          data-wazzup-history-through
          data-messenger-import-date
        />
      </div>
      <fieldset class="mt-3 grid gap-2" :disabled="formDisabled">
        <legend class="sr-only">{{ __('History import mode') }}</legend>
        <label
          v-for="mode in modes"
          :key="mode.value"
          class="flex cursor-pointer items-start gap-3 rounded-lg border bg-surface-cards p-2.5"
          :class="
            form.mode === mode.value
              ? 'border-outline-gray-4'
              : 'border-outline-gray-2'
          "
        >
          <input
            v-model="form.mode"
            type="radio"
            :name="`wazzup-history-mode-${channel.name}`"
            :value="mode.value"
            class="mt-0.5 accent-blue-600"
            :disabled="formDisabled"
            :data-wazzup-history-mode="mode.value"
          />
          <span>
            <span class="block text-p-medium text-ink-gray-8">{{
              __(mode.label)
            }}</span>
            <span class="mt-0.5 block text-p-sm text-ink-gray-5">{{
              __(mode.description)
            }}</span>
          </span>
        </label>
      </fieldset>
      <p
        v-if="validationError"
        class="mt-2 text-p-sm text-ink-red-7"
        role="alert"
      >
        {{ __(validationError) }}
      </p>
      <Button
        class="mt-3"
        :label="__('Start history import')"
        variant="solid"
        :loading="action === 'start'"
        :disabled="formDisabled"
        @click="start"
      />
      <Button
        v-if="status && !status.active"
        class="ml-2 mt-3"
        :label="__('Cancel')"
        :disabled="Boolean(action) || recoveryRequired"
        @click="showForm = false"
      />
    </form>
    <p v-if="!ready && !action" class="mt-3 text-p-sm text-ink-orange-7">
      {{
        __(
          'Save settings and connect an enabled channel before importing history.',
        )
      }}
    </p>
    <p
      v-if="refreshError"
      data-testid="wazzup-history-refresh-error"
      class="mt-3 text-p-sm text-ink-orange-7"
      role="alert"
    >
      {{ __('Could not refresh the Wazzup history import status.') }}
      {{ __(refreshError) }}
    </p>
    <p
      v-if="actionError"
      data-testid="wazzup-history-action-error"
      class="mt-3 text-p-sm text-ink-orange-7"
      role="alert"
    >
      {{ __(actionError) }}
    </p>
  </section>
</template>

<script setup>
import { Button, FormControl } from 'frappe-ui'
import { computed, onUnmounted, ref, watch } from 'vue'
import {
  isWazzupPartnerChannel,
  wazzupPartnerTransport,
} from '@/utils/wazzupPartnerConnection'
import {
  HISTORY_COUNTERS,
  callWazzupHistory,
  canResumeHistoryImport,
  formatHistoryImportTime,
  historyImportError,
  historyImportPeriod,
  historyImportPolicy,
  historyImportPolicyLabel,
  historyImportRpcError,
  historyImportStatusLabel,
  historyImportTimezone,
  newHistoryImportForm,
} from '@/utils/wazzupHistoryImport'

const props = defineProps({
  channel: { type: Object, default: null },
  enabled: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['busy'])
const supported = computed(
  () =>
    isWazzupPartnerChannel(props.channel) &&
    Boolean(wazzupPartnerTransport(props.channel.platform)),
)
const ready = computed(
  () =>
    supported.value &&
    props.enabled &&
    !props.disabled &&
    props.channel.enabled &&
    props.channel.state === 'connected' &&
    props.channel.wazzup_status === 'active',
)
const timezone = historyImportTimezone()
const status = ref(null)
const summary = computed(() => status.value?.result || status.value?.progress)
const visibleCounters = computed(() =>
  Object.entries(HISTORY_COUNTERS)
    .filter(([key]) => key === 'created' || summary.value?.counts[key] > 0)
    .map(([key, label]) => ({ key, label, value: summary.value?.counts[key] })),
)
const modes = [
  {
    value: 'existing',
    label: 'Existing conversations only',
    description: 'Import messages into existing conversations.',
  },
  {
    value: 'contacts',
    label: 'Existing and new contacts',
    description: 'Create missing conversations and leads.',
  },
]
const savedError = computed(() =>
  status.value?.processing.error
    ? historyImportError(status.value.processing.error)
    : status.value?.error ||
      (status.value?.result?.reason
        ? historyImportError(status.value.result.reason)
        : ''),
)
const canResume = computed(() => canResumeHistoryImport(status.value))
const form = ref(newHistoryImportForm())
const showForm = ref(true)
const known = ref(false)
const loading = ref(false)
const action = ref('')
const refreshError = ref('')
const actionError = ref('')
const validationError = ref('')
const recoveryRequired = ref(false)
const formDisabled = computed(
  () =>
    !ready.value ||
    !known.value ||
    loading.value ||
    Boolean(action.value) ||
    status.value?.active ||
    recoveryRequired.value,
)
let revision = 0
let disposed = false
let timer = null
let reading = null
const POLL_MS = 5000

function clearPoll() {
  clearTimeout(timer)
  timer = null
}

function current(ticket) {
  return !disposed && ticket === revision && supported.value
}

function schedulePoll() {
  clearPoll()
  if (disposed || !supported.value || action.value) return
  if (!known.value || status.value?.active || recoveryRequired.value) {
    timer = setTimeout(() => refresh(), POLL_MS)
  }
}

function accept(next) {
  if (next && next.channel !== props.channel.name) throw new Error()
  const before = status.value
  if (
    next &&
    before?.import_id === next.import_id &&
    next.generation < before.generation
  )
    return
  status.value = next
  known.value = true
  if (next?.active || (next && before?.import_id !== next.import_id))
    showForm.value = false
  if (recoveryRequired.value && next) actionError.value = ''
  recoveryRequired.value = false
}

function refresh(discover = false) {
  if (disposed || !supported.value || action.value) return Promise.resolve()
  if (reading) return reading.promise
  clearPoll()
  const ticket = revision
  const request = {}
  reading = request
  loading.value = true
  const lookup = discover || !status.value || recoveryRequired.value
  request.promise = (async () => {
    try {
      const next = await callWazzupHistory(
        lookup ? 'get_channel_import' : 'get_import_status',
        lookup
          ? { channel: props.channel.name }
          : { import_id: status.value.import_id },
      )
      if (!current(ticket)) return
      accept(next)
      refreshError.value = ''
    } catch (error) {
      if (current(ticket))
        refreshError.value = historyImportRpcError(error?.message)
    } finally {
      if (reading === request && current(ticket)) {
        reading = null
        loading.value = false
        schedulePoll()
      }
    }
  })()
  return request.promise
}

function openNewImport() {
  if (status.value?.active || loading.value || action.value) return
  form.value = newHistoryImportForm(status.value)
  validationError.value = actionError.value = ''
  showForm.value = true
}

async function mutate(kind, args) {
  clearPoll()
  // Invalidate reads started before this explicit action, even if they resolve later.
  const ticket = ++revision
  reading = null
  loading.value = false
  action.value = kind
  actionError.value = ''
  emit('busy', true)
  try {
    const next = await callWazzupHistory(
      kind === 'start' ? 'start_import' : 'start_processing',
      args,
    )
    if (current(ticket)) {
      accept(next)
      refreshError.value = ''
      showForm.value = false
    }
  } catch {
    if (current(ticket)) {
      recoveryRequired.value = true
      actionError.value =
        kind === 'start'
          ? 'The start request could not be confirmed. Refresh its status before trying again.'
          : 'Could not resume saved processing. Refresh its status before trying again.'
    }
  } finally {
    if (current(ticket)) {
      action.value = ''
      emit('busy', false)
      schedulePoll()
    }
  }
}

function start() {
  if (formDisabled.value || !showForm.value) return
  let period
  try {
    period = historyImportPeriod(form.value.from, form.value.through)
  } catch {
    validationError.value = 'Select an ordered date range for history import.'
    return
  }
  validationError.value = ''
  return mutate('start', {
    channel: props.channel.name,
    ...period,
    ...historyImportPolicy(form.value.mode),
  })
}

function resume() {
  if (
    !ready.value ||
    loading.value ||
    action.value ||
    recoveryRequired.value ||
    !canResume.value
  )
    return
  return mutate('resume', {
    import_id: status.value.import_id,
    expected_generation: status.value.generation,
  })
}

watch(
  () =>
    JSON.stringify([
      props.channel?.name,
      props.channel?.provider,
      props.channel?.wazzup_api_mode,
      props.channel?.platform,
    ]),
  () => {
    revision += 1
    clearPoll()
    reading = null
    status.value = null
    known.value = loading.value = recoveryRequired.value = false
    action.value =
      refreshError.value =
      actionError.value =
      validationError.value =
        ''
    emit('busy', false)
    form.value = newHistoryImportForm()
    showForm.value = true
    refresh()
  },
  { immediate: true, flush: 'sync' },
)

onUnmounted(() => {
  disposed = true
  revision += 1
  clearPoll()
  reading = null
  emit('busy', false)
})
</script>
