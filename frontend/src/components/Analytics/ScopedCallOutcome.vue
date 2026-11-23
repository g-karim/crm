<template>
  <section
    v-if="workspace || error"
    class="grid gap-3 rounded-lg border border-outline-gray-2 bg-surface-elevation-1 p-4 text-ink-gray-9"
  >
    <h4 class="text-base font-semibold">{{ __('Итог звонка') }}</h4>
    <Alert v-if="error" theme="red" :title="error" :dismissible="false">
      <template #footer>
        <Button variant="ghost" :disabled="saving" @click="load">{{
          __('Перезагрузить')
        }}</Button>
      </template>
    </Alert>
    <template v-if="workspace">
      <form
        v-if="workspace.can_manage"
        class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end"
        @submit.prevent="save"
      >
        <FormControl
          v-model="outcome"
          type="select"
          :label="__('Результат разговора')"
          :options="outcomes"
          :disabled="saving"
        />
        <Button
          type="submit"
          variant="solid"
          :loading="saving"
          :disabled="!outcome || (outcome === workspace.outcome && !due)"
        >
          {{ __('Сохранить итог') }}
        </Button>
        <FormControl
          v-if="
            outcome === 'Callback' &&
            workspace.can_schedule &&
            (!workspace.task ||
              ['Done', 'Completed', 'Canceled', 'Cancelled'].includes(
                workspace.task.status,
              ))
          "
          v-model="due"
          type="datetime-local"
          :label="__('Создать задачу на перезвон')"
          :description="workspace.timezone"
          :disabled="saving"
          class="sm:col-span-2"
        />
      </form>
      <p v-else class="text-sm">
        {{ outcomeNames[workspace.outcome] || __('Итог не записан') }}
      </p>
      <Button
        v-if="workspace.task"
        :route="{ name: 'Tasks', query: { open: workspace.task.name } }"
        class="w-fit"
        icon-left="lucide-list-todo"
      >
        {{ workspace.task.title }}
      </Button>
      <div
        v-if="workspace.outcome === 'Callback' && workspace.can_confirm"
        class="grid gap-3 border-t border-outline-gray-2 pt-3"
      >
        <h5 class="text-sm font-semibold">
          {{ __('Подтверждение перезвона') }}
        </h5>
        <div
          v-if="workspace.linked?.name"
          class="flex flex-wrap items-center gap-2"
        >
          <span class="text-sm">{{ __('Подтверждённая попытка') }}</span>
          <Button
            :route="{
              name: 'Call Logs',
              query: { ...route.query, open: workspace.linked.name },
            }"
            variant="ghost"
          >
            {{ formatAttempt(workspace.linked) }}
          </Button>
        </div>
        <p
          v-else-if="workspace.linked?.unavailable"
          class="text-sm text-ink-gray-7"
        >
          {{ __('Связанный звонок недоступен') }}
        </p>
        <template v-if="workspace.can_manage && workspace.candidates.length">
          <div
            class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end"
          >
            <FormControl
              v-model="reply"
              type="select"
              :label="__('Исходящая попытка')"
              :options="attempts"
              :disabled="saving"
            />
            <Button
              :disabled="!reply || reply === workspace.linked?.name"
              :loading="saving"
              @click="confirm"
            >
              {{ __('Подтвердить связь') }}
            </Button>
          </div>
        </template>
        <p v-else-if="!workspace.linked" class="text-sm text-ink-gray-7">
          {{ __('Доступных исходящих попыток пока нет') }}
        </p>
      </div>
    </template>
  </section>
</template>

<script setup>
import { Alert, Button, FormControl, call } from 'frappe-ui'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const props = defineProps({ name: { type: String, required: true } })
const emit = defineEmits(['saved'])
const route = useRoute()
const workspace = ref(null)
const outcome = ref('')
const reply = ref('')
const due = ref('')
const error = ref('')
const saving = ref(false)
let request
let mutation
const endpoint = 'crm.analytics.call_journal.'
const outcomeNames = {
  Agreed: __('Договорились'),
  Callback: __('Перезвонить'),
  'Not interested': __('Неинтересно'),
  'Wrong number': __('Неверный номер'),
}
const outcomes = [
  { value: '', label: __('Выбрать итог') },
  ...Object.entries(outcomeNames).map(([value, label]) => ({ value, label })),
]
const attempts = computed(() => [
  { value: '', label: __('Выбрать звонок') },
  ...workspace.value.candidates.map((item) => ({
    value: item.name,
    label: formatAttempt(item),
  })),
])

function formatAttempt(item) {
  const time = new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone: workspace.value.timezone,
  }).format(new Date(item.at))
  return [time, __(item.status), item.employee].filter(Boolean).join(' · ')
}

function apply(value) {
  workspace.value = value
  outcome.value = value.outcome
  reply.value = value.linked?.name || ''
  due.value = ''
  mutation = null
}

async function load() {
  request?.abort()
  const current = new AbortController()
  request = current
  error.value = ''
  try {
    const query = new URLSearchParams({ name: props.name })
    const response = await fetch(
      '/api/method/' + endpoint + 'get_workspace?' + query,
      { signal: current.signal, cache: 'no-store' },
    )
    if (response.status === 403) {
      if (request === current) workspace.value = null
      return
    }
    if (!response.ok) throw new Error()
    const { message } = await response.json()
    if (request === current) apply(message)
  } catch (failure) {
    if (request === current && failure.name !== 'AbortError')
      error.value = __('Не удалось загрузить итог звонка')
  }
}

async function send(method, values) {
  if (saving.value || !workspace.value) return
  const name = props.name
  saving.value = true
  error.value = ''
  try {
    const result = await call(endpoint + method, {
      name,
      expected_viewer: workspace.value.viewer,
      expected_revision: workspace.value.revision,
      ...values,
    })
    if (props.name === name) apply(result)
    emit('saved')
    window.dispatchEvent(new Event('crm-call-work-updated'))
  } catch (failure) {
    if (props.name === name)
      error.value =
        failure?.exc_type === 'TimestampMismatchError'
          ? __('Итог изменился в другой сессии. Перезагрузите карточку.')
          : __(
              'Не удалось сохранить. Проверьте доступ, состояние текущей задачи и выбранный звонок.',
            )
  } finally {
    saving.value = false
  }
}

function save() {
  const values = {
    outcome: outcome.value,
    due_at: outcome.value === 'Callback' ? due.value || null : null,
  }
  const key = JSON.stringify(values)
  if (mutation?.key !== key)
    mutation = { key, id: globalThis.crypto.randomUUID() }
  return send('save_outcome', { ...values, mutation_id: mutation.id })
}

function confirm() {
  if (reply.value) return send('confirm_callback', { outgoing: reply.value })
}

watch(() => props.name, load, { immediate: true })
watch(outcome, (value) => {
  if (value !== 'Callback') due.value = ''
})
onBeforeUnmount(() => request?.abort())
</script>
