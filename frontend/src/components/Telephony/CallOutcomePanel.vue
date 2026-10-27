<template>
  <section
    class="space-y-4 text-ink-gray-9"
    data-testid="call-outcome-panel"
    :aria-label="__('Call outcome')"
  >
    <p v-if="loading" role="status" class="text-sm text-ink-gray-6">
      {{ __('Loading call work…') }}
    </p>
    <template v-if="data">
      <div class="flex items-center justify-between gap-3">
        <h3 class="text-base font-semibold">{{ __('Call outcome') }}</h3>
        <span
          v-if="saved"
          role="status"
          class="inline-flex items-center gap-1 text-sm text-ink-gray-7"
          ><span class="lucide-check size-4" aria-hidden="true" />{{
            __('Saved')
          }}</span
        >
      </div>
      <p v-if="!data.can_manage" class="text-sm text-ink-gray-6">
        {{
          data.review?.outcome ? __(data.review.outcome) : __('No outcome yet')
        }}
      </p>
      <template v-else>
        <div
          class="grid grid-cols-2 gap-2"
          role="group"
          :aria-label="__('Choose a call outcome')"
        >
          <button
            v-for="choice in callOutcomes"
            :key="choice"
            type="button"
            :aria-pressed="outcome === choice"
            class="flex min-h-11 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-ink-gray-9 disabled:opacity-50"
            :class="
              outcome === choice
                ? 'border-outline-gray-9 bg-surface-gray-2 font-medium'
                : 'border-outline-gray-2 hover:bg-surface-gray-1'
            "
            :disabled="blocked || Boolean(openCallback)"
            @click="chooseOutcome(choice)"
          >
            <span
              v-if="outcome === choice"
              class="lucide-check size-4 shrink-0"
              aria-hidden="true"
            />{{ __(choice) }}
          </button>
        </div>
        <p v-if="openCallback" class="text-sm leading-5 text-ink-gray-6">
          {{
            __(
              'An open callback task already exists. Complete it or cancel it before scheduling another.',
            )
          }}
        </p>
        <div
          v-else-if="outcome === 'Callback'"
          class="space-y-3 rounded-lg bg-surface-gray-1 p-3"
        >
          <FormControl
            v-model="contextKey"
            type="select"
            :label="__('Save callback to')"
            :options="contextOptions"
            :disabled="blocked"
          />
          <Button
            v-if="!contextOptions.length"
            :label="__('Choose a lead or deal')"
            variant="ghost"
            @click="searchOpen = true"
          />
          <Button
            v-else
            :label="__('Find another lead or deal')"
            variant="ghost"
            @click="searchOpen = !searchOpen"
          />
          <div v-if="searchOpen" class="space-y-2">
            <FormControl
              v-model="searchKind"
              type="select"
              :label="__('Record type')"
              :options="[
                { value: 'lead', label: __('Lead') },
                { value: 'deal', label: __('Deal') },
              ]"
              :disabled="blocked"
            />
            <FormControl
              v-model="search"
              type="search"
              :label="__('Find a lead or deal')"
              :disabled="blocked"
            />
            <div class="max-h-36 overflow-y-auto">
              <Button
                v-for="item in searchResults"
                :key="item.name"
                :label="item.title"
                variant="ghost"
                class="min-h-11 w-full justify-start"
                :disabled="blocked"
                @click="chooseContext(item)"
              />
            </div>
          </div>
          <FormControl
            v-model="title"
            :label="__('Task title')"
            :disabled="blocked"
          />
          <FormControl
            v-model="assignee"
            type="select"
            :label="__('Assigned to')"
            :options="peopleOptions"
            :disabled="blocked || !contextKey"
          />
          <FormControl
            v-model="due"
            type="datetime-local"
            :label="__('Callback time')"
            :disabled="blocked"
          />
        </div>
        <Button
          v-if="!openCallback"
          :label="
            state.pending
              ? __('Retry the same save')
              : outcome === 'Callback'
                ? __('Save outcome and create callback')
                : __('Save outcome')
          "
          variant="solid"
          class="min-h-11 w-full"
          :loading="state.saving"
          :disabled="
            !outcome ||
            state.conflict ||
            (!state.pending &&
              outcome === 'Callback' &&
              (!contextKey || !assignee || !due || !title.trim()))
          "
          @click="saveOutcome"
        />
        <p
          v-if="data.review?.outcome && !openCallback"
          class="text-sm leading-5 text-ink-gray-6"
        >
          {{
            __(
              'The manager outcome is separate from the call connection status.',
            )
          }}
        </p>
      </template>
      <template v-if="showMaterials || openCallback">
        <section
          v-if="data.notes.length && showMaterials"
          class="space-y-3"
          :aria-label="__('Notes linked to call')"
        >
          <h3 class="text-base font-semibold">
            {{ __('Notes linked to call') }}
          </h3>
          <article
            v-for="note in data.notes"
            :key="note.name"
            class="rounded-lg border border-outline-gray-2 p-3"
          >
            <h4 class="text-sm font-medium">{{ note.title }}</h4>
            <p
              class="mt-2 whitespace-pre-wrap break-words text-sm leading-5 text-ink-gray-7"
            >
              {{ note.text }}
            </p>
          </article>
        </section>
        <section
          v-if="visibleTasks.length"
          class="space-y-3"
          :aria-label="__('Linked tasks')"
        >
          <h3 class="text-base font-semibold">{{ __('Linked tasks') }}</h3>
          <article
            v-for="task in visibleTasks"
            :key="task.name"
            class="space-y-2 rounded-lg border border-outline-gray-2 p-3"
            :data-followup-task="task.name"
          >
            <p class="break-words text-sm font-medium">{{ task.title }}</p>
            <p class="text-sm text-ink-gray-6">
              {{ __(task.status)
              }}<span v-if="task.due_date">
                · {{ formatDate(task.due_date, 'D MMM, HH:mm') }}</span
              >
            </p>
            <p class="break-words text-sm text-ink-gray-6">
              {{ task.assigned_to || __('Unassigned') }}
            </p>
            <p
              v-if="task.description_text && showMaterials"
              class="whitespace-pre-wrap break-words text-sm leading-5"
            >
              {{ task.description_text }}
            </p>
            <div
              v-if="task.can_write && task.state_group === 'open'"
              class="flex flex-wrap gap-2"
            >
              <Button
                :label="__('Complete task')"
                icon-left="lucide-check"
                class="min-h-11"
                :disabled="blocked"
                @click="updateTask(task, 'Done')"
              />
              <Button
                v-if="task.name === data.review?.callback_task"
                :label="__('Cancel callback task')"
                variant="ghost"
                class="min-h-11"
                :disabled="blocked"
                @click="updateTask(task, 'Canceled')"
              />
            </div>
          </article>
        </section>
      </template>
    </template>
    <p
      v-if="error || state.error"
      role="alert"
      class="text-sm leading-5 text-ink-red-6"
    >
      {{ error || __(state.error) }}
    </p>
    <Button
      v-if="state.pending && pendingTask"
      :label="__('Retry the same save')"
      class="min-h-11"
      :loading="state.saving"
      @click="updateTask(pendingTask.task, pendingTask.status)"
    />
    <Button
      v-if="error || state.conflict"
      :label="__('Reload saved outcome')"
      class="min-h-11"
      @click="load(true)"
    />
  </section>
</template>
<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { Button, FormControl, call, dayjs, getConfig } from 'frappe-ui'
import { useDebounceFn, useEventListener } from '@vueuse/core'
import { sessionStore } from '@/stores/session'
import { formatDate } from '@/utils'
import {
  callbackDeadline,
  callOutcomes,
  saveFollowup,
} from '@/utils/callFollowups'

const props = defineProps({
  name: { type: String, required: true },
  showMaterials: { type: Boolean, default: true },
  preferredContext: { type: Object, default: null },
})
const emit = defineEmits(['updated'])
const session = sessionStore()
const data = ref(null),
  loading = ref(false),
  error = ref(''),
  saved = ref(false)
const outcome = ref(''),
  contextKey = ref(''),
  contexts = ref([]),
  people = ref([]),
  assignee = ref(''),
  due = ref(''),
  title = ref('')
const searchOpen = ref(false),
  searchKind = ref('lead'),
  search = ref(''),
  searchResults = ref([]),
  pendingTask = ref(null)
const state = reactive({
  saving: false,
  pending: null,
  conflict: false,
  error: '',
})
let generation = 0,
  peopleVersion = 0,
  searchVersion = 0,
  disposed = false
const blocked = computed(
  () => state.saving || Boolean(state.pending) || state.conflict,
)
const inputDirty = computed(
  () =>
    outcome.value !== (data.value?.review?.outcome || '') ||
    (outcome.value === 'Callback' && !openCallback.value),
)
const openCallback = computed(() =>
  data.value?.tasks.find(
    (t) =>
      t.name === data.value.review?.callback_task && t.state_group === 'open',
  ),
)
const visibleTasks = computed(() =>
  props.showMaterials
    ? data.value?.tasks || []
    : openCallback.value
      ? [openCallback.value]
      : [],
)
const contextOptions = computed(() => [
  ...(contexts.value.length !== 1
    ? [{ value: '', label: __('Choose a lead or deal') }]
    : []),
  ...contexts.value.map((c) => ({
    value: c.doctype + ':' + c.name,
    label: `${c.doctype === 'CRM Lead' ? __('Lead') : __('Deal')} · ${c.title || c.name}`,
  })),
])
const peopleOptions = computed(() => [
  { value: '', label: __('Choose assignee') },
  ...people.value,
])
const selectedContext = computed(() =>
  contexts.value.find((c) => c.doctype + ':' + c.name === contextKey.value),
)
function chooseOutcome(choice) {
  outcome.value = choice
  saved.value = false
}
function fill(result) {
  data.value = result
  outcome.value = result.review?.outcome || ''
  contexts.value = result.references.filter((r) =>
    ['CRM Lead', 'CRM Deal'].includes(r.doctype),
  )
  const preferred = props.preferredContext
  const context =
    result.review?.context ||
    (preferred
      ? {
          doctype: preferred.kind === 'lead' ? 'CRM Lead' : 'CRM Deal',
          name: preferred.name,
        }
      : null)
  contextKey.value = context
    ? context.doctype + ':' + context.name
    : contexts.value.length === 1
      ? contextOptions.value[0].value
      : ''
  const callback = result.tasks.find(
    (t) => t.name === result.review?.callback_task,
  )
  if (
    context &&
    !contexts.value.some(
      (c) => c.doctype === context.doctype && c.name === context.name,
    )
  )
    contexts.value.push({
      ...context,
      title: callback?.context?.label || preferred?.title || context.name,
    })
  title.value = __('Call back to customer')
  assignee.value = callback?.assigned_to || ''
  due.value = ''
}
async function load(preserveInput = false) {
  const current = ++generation,
    name = props.name,
    viewer = session.user
  loading.value = true
  error.value = ''
  try {
    const result = await call('crm.api.call_followups.get_workspace', { name })
    if (disposed || current !== generation || session.user !== viewer) return
    if (preserveInput) {
      data.value = result
      state.conflict = false
      state.error = ''
      saved.value = false
    } else fill(result)
  } catch {
    if (!disposed && current === generation) {
      data.value = null
      error.value = __('Call work is unavailable. Check access and try again.')
    }
  } finally {
    if (current === generation) loading.value = false
  }
}
async function send(endpoint, params) {
  const current = generation,
    name = props.name,
    viewer = session.user
  const result = await saveFollowup(state, {
    request: call,
    endpoint,
    params,
    isCurrent: () =>
      !disposed &&
      current === generation &&
      name === props.name &&
      viewer === session.user,
  })
  if (!result) return
  data.value = result
  saved.value = true
  pendingTask.value = null
  emit('updated')
  window.dispatchEvent(
    new CustomEvent('crm-call-work-updated', { detail: { name } }),
  )
}
function saveOutcome() {
  const context = selectedContext.value
  return send('crm.api.call_followups.save_outcome', {
    name: props.name,
    outcome: outcome.value,
    expected_revision: data.value.review?.revision || 0,
    expected_viewer: session.user,
    mutation_id: crypto.randomUUID(),
    callback:
      outcome.value === 'Callback'
        ? {
            context_kind: context?.doctype === 'CRM Lead' ? 'lead' : 'deal',
            context_name: context?.name || '',
            title: title.value.trim(),
            assigned_to: assignee.value,
            due_date: callbackDeadline(
              due.value,
              dayjs,
              getConfig('systemTimezone'),
              getConfig('localTimezone') ||
                Intl.DateTimeFormat().resolvedOptions().timeZone,
            ),
          }
        : null,
  })
}
function updateTask(task, status) {
  pendingTask.value = { task, status }
  return send('crm.api.call_followups.complete_task', {
    name: props.name,
    task: task.name,
    expected_modified: task.modified,
    mutation_id: crypto.randomUUID(),
    expected_viewer: session.user,
    status,
  })
}
function chooseContext(item) {
  const context = {
    doctype: item.kind === 'lead' ? 'CRM Lead' : 'CRM Deal',
    name: item.name,
    title: item.title,
  }
  if (
    !contexts.value.some(
      (c) => c.doctype === context.doctype && c.name === context.name,
    )
  )
    contexts.value.push(context)
  contextKey.value = context.doctype + ':' + context.name
  searchOpen.value = false
}
watch(contextKey, async () => {
  const version = ++peopleVersion,
    context = selectedContext.value,
    current = generation
  people.value = []
  if (!context) {
    assignee.value = ''
    return
  }
  try {
    const result = await call('crm.api.call_work.options', {
      kind: context.doctype === 'CRM Lead' ? 'lead' : 'deal',
      name: context.name,
    })
    if (disposed || version !== peopleVersion || current !== generation) return
    people.value = result.people
    if (!people.value.some((p) => p.value === assignee.value))
      assignee.value = people.value.some((p) => p.value === session.user)
        ? session.user
        : ''
  } catch {
    if (version === peopleVersion)
      error.value = __('Could not load callback assignees.')
  }
})
const find = useDebounceFn(async () => {
  const version = searchVersion,
    current = generation
  try {
    const results = await call('crm.api.call_work.search_contexts', {
      kind: searchKind.value,
      query: search.value,
    })
    if (!disposed && version === searchVersion && current === generation)
      searchResults.value = results
  } catch {
    if (version === searchVersion)
      error.value = __('Could not find customer records.')
  }
}, 250)
watch([search, searchKind, searchOpen], () => {
  searchVersion++
  searchResults.value = []
  if (searchOpen.value) find()
})
watch(
  () => [props.name, session.user],
  () => {
    data.value = null
    state.pending = null
    state.conflict = false
    state.error = ''
    pendingTask.value = null
    saved.value = false
    load()
  },
  { immediate: true },
)
function refreshSaved() {
  if (!document.hidden && !loading.value && !blocked.value && !inputDirty.value)
    load()
}
useEventListener(window, 'focus', refreshSaved)
const refreshTimer = setInterval(refreshSaved, 30000)
onBeforeUnmount(() => {
  clearInterval(refreshTimer)
  disposed = true
  generation++
  peopleVersion++
  searchVersion++
})
</script>
