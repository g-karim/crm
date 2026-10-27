<template>
  <section
    class="space-y-4 rounded-xl border border-outline-gray-2 p-4 text-ink-gray-9"
    data-testid="call-insights"
  >
    <div class="flex items-center justify-between gap-2">
      <h3 class="flex items-center gap-2 text-base font-semibold">
        <FeatherIcon name="file-text" class="size-4" aria-hidden="true" />{{
          __('Разбор разговора')
        }}
      </h3>
      <Button
        v-if="data?.settings.can_manage"
        :label="__('AI и бюджет')"
        variant="ghost"
        class="min-h-11"
        @click="settingsOpen = true"
      />
    </div>
    <p v-if="loading && !data" role="status" class="text-sm text-ink-gray-6">
      {{ __('Загрузка разбора…') }}
    </p>
    <template v-if="data">
      <FormControl
        v-if="data.versions?.length > 1"
        v-model="selectedVersion"
        type="select"
        :label="__('Версия анализа')"
        :options="[
          { value: '', label: __('Последняя версия') },
          ...data.versions.map((v) => ({
            value: v.name,
            label: `${v.creation} · ${v.state}`,
          })),
        ]"
      />
      <p
        v-if="
          (!result || result.state !== 'Completed') &&
          (!data.settings.configured || !data.settings.enabled)
        "
        class="text-sm leading-5 text-ink-gray-6"
      >
        {{
          !data.settings.configured
            ? __(
                'Для распознавания нужен отдельный AI-ключ. Телефония работает независимо.',
              )
            : __(
                'AI-анализ выключен. Его можно включить отдельно с дневным бюджетом.',
              )
        }}
      </p>
      <p
        v-if="data.recording_unavailable"
        role="status"
        class="text-sm leading-5 text-ink-gray-6"
      >
        {{
          __(
            'AI-анализ доступен участнику звонка, у которого есть доступ к записи.',
          )
        }}
      </p>
      <p
        v-if="data.settings.blocked"
        role="status"
        class="text-sm text-ink-gray-6"
      >
        {{ __('Новые анализы приостановлены до сверки расходов AI.') }}
      </p>
      <p
        v-if="result?.recording_matches === false"
        role="status"
        class="text-sm leading-5 text-ink-gray-6"
      >
        {{
          __(
            'Этот разбор относится к предыдущей записи звонка. Метки не перемещают новую запись; её можно проанализировать отдельно.',
          )
        }}
      </p>
      <p v-if="result?.legacy" class="text-sm leading-5 text-ink-gray-6">
        {{
          __(
            'Ранее сохранённый анализ. Исходность текста и временные метки для него не подтверждены.',
          )
        }}
      </p>
      <p v-if="running" role="status" class="flex items-center gap-2 text-sm">
        <LoadingIndicator class="size-4" />{{
          result.stage === 'transcribing'
            ? __('Распознаём речь…')
            : result.stage === 'summarizing'
              ? __('Готовим итог…')
              : __('Анализ в очереди…')
        }}
      </p>
      <p
        v-if="result?.error"
        role="alert"
        class="break-words text-sm leading-5 text-ink-red-4"
      >
        {{ result.error }}
      </p>
      <Button
        v-if="
          data.can_start &&
          !running &&
          result?.state !== 'Uncertain' &&
          (!result ||
            result.state === 'Failed' ||
            result.recording_matches === false)
        "
        :label="result ? __('Повторить анализ') : __('Анализировать запись')"
        icon-left="lucide-sparkles"
        :disabled="
          !data.settings.enabled ||
          !data.settings.configured ||
          data.settings.blocked
        "
        :loading="starting"
        class="min-h-11"
        @click="start"
      />
      <p v-if="!result" class="text-sm leading-5 text-ink-gray-6">
        {{
          __(
            'После анализа здесь появятся расшифровка, договорённости и предложения задач.',
          )
        }}
      </p>
      <template v-if="result?.analysis?.summary">
        <div class="space-y-2">
          <h4 class="text-sm font-semibold">{{ __('Краткий итог AI') }}</h4>
          <p class="whitespace-pre-wrap break-words text-sm leading-6">
            {{ result.analysis.summary }}
          </p>
        </div>
        <div v-if="result.analysis.agreements?.length" class="space-y-2">
          <h4 class="text-sm font-semibold">{{ __('Договорённости') }}</h4>
          <ul class="list-disc space-y-2 pl-4 text-sm leading-5">
            <li v-for="(item, i) in result.analysis.agreements" :key="i">
              {{ item }}
            </li>
          </ul>
        </div>
        <div v-if="result.analysis.tasks?.length" class="space-y-3">
          <h4 class="text-sm font-semibold">{{ __('Предложения задач') }}</h4>
          <p class="text-xs leading-5 text-ink-gray-6">
            {{
              __(
                'Проверь формулировку, карточку, исполнителя и срок перед созданием.',
              )
            }}
          </p>
          <div
            v-for="(task, i) in result.analysis.tasks"
            :key="i"
            class="space-y-2 rounded-lg bg-surface-gray-1 p-3"
            :data-ai-proposal="i"
          >
            <p class="break-words text-sm font-medium">{{ task.title }}</p>
            <blockquote
              class="break-words border-l-2 border-outline-gray-3 pl-3 text-xs leading-5 text-ink-gray-6"
            >
              {{ task.evidence }}
            </blockquote>
            <p v-if="task.created_task" role="status" class="text-sm">
              {{ __('Задача создана') }} ·
              <RouterLink
                class="underline"
                :to="task.created_task.crm_route.replace(/^\/crm/, '')"
                >{{ task.created_task.title }}</RouterLink
              >
            </p>
            <p v-else-if="task.unavailable" class="text-sm text-ink-gray-6">
              {{ __('Задача уже создана; доступ к ней ограничен.') }}
            </p>
            <Button
              v-else
              :label="__('Проверить и создать задачу')"
              class="min-h-11"
              @click="prepareTask(i)"
            />
          </div>
        </div>
        <p class="text-xs leading-5 text-ink-gray-6">
          {{
            __(
              'AI может ошибаться. Заметки менеджера и исходная запись не изменяются.',
            )
          }}
        </p>
      </template>
      <details
        v-if="result?.raw_transcript"
        class="border-t border-outline-gray-1 pt-3"
      >
        <summary class="min-h-11 cursor-pointer text-sm font-semibold">
          {{
            result.legacy
              ? __('Текст прежнего анализа')
              : __('Исходная расшифровка')
          }}
        </summary>
        <div class="mt-2 space-y-3">
          <FormControl
            v-model="search"
            type="search"
            :label="__('Найти в расшифровке')"
          />
          <p
            v-if="result.segments?.length && !segments.length"
            role="status"
            class="text-sm text-ink-gray-6"
          >
            {{ __('Совпадений нет') }}
          </p>
          <div
            v-if="result.segments?.length"
            class="max-h-80 space-y-1 overflow-y-auto pr-1"
          >
            <div
              v-for="(segment, i) in segments"
              :key="i"
              class="flex items-start gap-2 rounded-lg py-1"
            >
              <button
                type="button"
                class="min-h-11 min-w-14 shrink-0 rounded-md px-1 text-sm tabular-nums text-ink-gray-7 underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-ink-gray-9 disabled:opacity-50"
                :disabled="
                  !seekable ||
                  result.recording_matches === false ||
                  hasActiveCall
                "
                :aria-label="
                  __('Перейти к {0} в записи', [
                    transcriptTimestamp(segment.start),
                  ])
                "
                @click="emit('seek', segment.start)"
              >
                {{ transcriptTimestamp(segment.start) }}
              </button>
              <p class="min-w-0 break-words py-2 text-sm leading-6">
                {{ segment.text }}
              </p>
            </div>
          </div>
          <template v-else
            ><p class="text-xs text-ink-gray-6">
              {{ __('Провайдер не вернул временные метки.') }}
            </p>
            <p
              class="max-h-80 overflow-y-auto whitespace-pre-wrap break-words text-sm leading-6"
            >
              {{ result.raw_transcript }}
            </p></template
          >
        </div>
      </details>
      <p
        v-if="result && !result.legacy && result.state === 'Completed'"
        class="text-xs text-ink-gray-6"
      >
        {{
          __('Стоимость анализа: ${0}', [Number(result.actual_cost).toFixed(4)])
        }}
      </p>
    </template>
    <p v-if="error" role="alert" class="text-sm leading-5 text-ink-red-4">
      {{ error }}
    </p>
    <Button
      v-if="error"
      :label="__('Обновить разбор')"
      class="min-h-11"
      @click="load"
    />
    <CallAISettings
      v-if="data"
      v-model="settingsOpen"
      :data="data.settings"
      @changed="load"
    />
    <Dialog
      v-model="taskOpen"
      :options="{ title: __('Задача из разговора'), size: 'xl' }"
    >
      <template #body-content>
        <form
          class="space-y-4 text-ink-gray-9"
          data-testid="ai-task-confirm"
          @submit.prevent="saveTask"
        >
          <FormControl
            v-model="taskTitle"
            :label="__('Task title')"
            :disabled="taskBlocked"
          />
          <FormControl
            v-model="contextKey"
            type="select"
            :label="__('Сохранить в карточку')"
            :options="contextOptions"
            :disabled="taskBlocked"
          />
          <details>
            <summary class="min-h-11 cursor-pointer text-sm">
              {{ __('Find another lead or deal') }}
            </summary>
            <div class="space-y-2">
              <FormControl
                v-model="kind"
                type="select"
                :label="__('Record type')"
                :options="[
                  { value: 'lead', label: __('Lead') },
                  { value: 'deal', label: __('Deal') },
                ]"
                :disabled="taskBlocked"
              /><FormControl
                v-model="customerSearch"
                type="search"
                :label="__('Find a lead or deal')"
                :disabled="taskBlocked"
              />
              <Button
                v-for="item in found"
                :key="item.value"
                :label="item.label"
                variant="ghost"
                class="min-h-11 w-full justify-start"
                :disabled="taskBlocked"
                @click="chooseCustomer(item)"
              />
            </div>
          </details>
          <FormControl
            v-model="assignee"
            type="select"
            :label="__('Assigned to')"
            :options="people"
            :disabled="taskBlocked || !contextKey"
          />
          <FormControl
            v-model="due"
            type="datetime-local"
            :label="__('Срок задачи')"
            :disabled="taskBlocked"
          />
          <p class="text-xs leading-5 text-ink-gray-6">
            {{
              __(
                'Создастся обычная задача CRM, связанная с выбранной карточкой и этим звонком.',
              )
            }}
          </p>
          <p v-if="taskState.error" role="alert" class="text-sm text-ink-red-4">
            {{ __(taskState.error) }}
          </p>
          <Button
            :label="
              taskState.pending
                ? __('Retry the same save')
                : __('Создать задачу')
            "
            type="submit"
            variant="solid"
            class="min-h-11"
            :loading="taskState.saving"
            :disabled="
              taskState.conflict ||
              (!taskState.pending &&
                (!taskTitle.trim() || !contextKey || !assignee || !due))
            "
          />
        </form>
      </template>
    </Dialog>
  </section>
</template>
<script setup>
import {
  Button,
  Dialog,
  FeatherIcon,
  FormControl,
  LoadingIndicator,
  call,
  dayjs,
  getConfig,
} from 'frappe-ui'
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { hasActiveCall } from '@/composables/telephony'
import { callbackDeadline, saveFollowup } from '@/utils/callFollowups'
import { transcriptMatches, transcriptTimestamp } from '@/utils/callInsights'
import CallAISettings from './CallAISettings.vue'
const props = defineProps({
  name: { type: String, required: true },
  references: { type: Array, default: () => [] },
  seekable: { type: Boolean, default: false },
})
const emit = defineEmits(['seek'])
const data = ref(null),
  loading = ref(false),
  error = ref(''),
  starting = ref(false),
  settingsOpen = ref(false),
  search = ref('')
const result = computed(() => data.value?.result)
const segments = computed(() =>
  transcriptMatches(result.value?.segments || [], search.value),
)
const running = computed(() =>
  ['Queued', 'Processing'].includes(result.value?.state),
)
const selectedVersion = ref('')
watch(selectedVersion, () => load())
let disposed = false,
  version = 0
async function load() {
  const id = ++version
  loading.value = true
  try {
    const value = await call('crm.call_analysis.workspace.get', {
      name: props.name,
      run_name: selectedVersion.value || undefined,
    })
    if (!disposed && id === version) {
      data.value = value
      error.value = ''
    }
  } catch {
    if (!disposed && id === version) {
      data.value = null
      error.value = __(
        'Разбор недоступен. Проверь соединение и доступ к звонку.',
      )
    }
  } finally {
    if (id === version) loading.value = false
  }
}
let startMutation = ''
async function start() {
  starting.value = true
  error.value = ''
  startMutation ||= crypto.randomUUID()
  try {
    await call('crm.call_analysis.workspace.start', {
      name: props.name,
      mutation_id: startMutation,
      retry: result.value?.state === 'Failed' ? 1 : 0,
    })
    startMutation = ''
    await load()
  } catch {
    error.value = __(
      'Не удалось запустить анализ. Проверь AI-ключ, дневной бюджет и доступ. Повторная команда использует тот же запрос.',
    )
  } finally {
    starting.value = false
  }
}
const taskOpen = ref(false),
  proposalIndex = ref(-1),
  taskTitle = ref(''),
  due = ref(''),
  assignee = ref(''),
  contextKey = ref(''),
  kind = ref('lead'),
  customerSearch = ref(''),
  found = ref([]),
  people = ref([]),
  extraContexts = ref([])
const taskState = reactive({
  saving: false,
  pending: null,
  conflict: false,
  error: '',
})
const taskBlocked = computed(
  () => taskState.saving || Boolean(taskState.pending),
)
const contexts = computed(() => [
  ...props.references.filter((r) =>
    ['CRM Lead', 'CRM Deal'].includes(r.doctype),
  ),
  ...extraContexts.value,
])
const contextOptions = computed(() => [
  { value: '', label: __('Choose a lead or deal') },
  ...contexts.value.map((r) => ({
    value: `${r.doctype === 'CRM Lead' ? 'lead' : 'deal'}:${r.name}`,
    label: `${__(r.doctype === 'CRM Lead' ? 'Lead' : 'Deal')} · ${r.title}`,
  })),
])
function prepareTask(i) {
  if (taskState.pending && proposalIndex.value !== i) return
  if (!taskState.pending) {
    proposalIndex.value = i
    taskTitle.value = result.value.analysis.tasks[i].title
    due.value = ''
    assignee.value = ''
    contextKey.value =
      contexts.value.length === 1 ? contextOptions.value[1].value : ''
    taskState.error = ''
    taskState.conflict = false
  }
  taskOpen.value = true
}
function chosenContext() {
  const [context_kind, ...rest] = contextKey.value.split(':')
  return { context_kind, context_name: rest.join(':') }
}
let peopleVersion = 0
watch(contextKey, async () => {
  const id = ++peopleVersion
  people.value = []
  assignee.value = ''
  if (!contextKey.value) return
  try {
    const ctx = chosenContext()
    const values = await call('crm.api.call_work.options', {
      kind: ctx.context_kind,
      name: ctx.context_name,
    }).then((result) => result.people)
    if (disposed || id !== peopleVersion) return
    people.value = [{ value: '', label: __('Choose assignee') }, ...values]
    if (values.some((v) => v.value === data.value?.viewer))
      assignee.value = data.value.viewer
  } catch {
    taskState.error = __(
      'Не удалось загрузить исполнителей. Выбери карточку заново и проверь доступ.',
    )
  }
})
const findCustomers = useDebounceFn(async () => {
  const current = kind.value + customerSearch.value
  try {
    const values = await call('crm.api.call_work.search_contexts', {
      kind: kind.value,
      query: customerSearch.value,
    })
    if (!disposed && current === kind.value + customerSearch.value)
      found.value = values.map((v) => ({ value: v.name, label: v.title }))
  } catch {
    found.value = []
  }
}, 250)
watch([kind, customerSearch], findCustomers)
function chooseCustomer(item) {
  const dt = kind.value === 'lead' ? 'CRM Lead' : 'CRM Deal'
  if (!contexts.value.some((r) => r.doctype === dt && r.name === item.value))
    extraContexts.value.push({
      doctype: dt,
      name: item.value,
      title: item.label,
    })
  contextKey.value = `${kind.value}:${item.value}`
}
async function saveTask() {
  const zone = getConfig('systemTimezone'),
    local =
      getConfig('localTimezone') ||
      Intl.DateTimeFormat().resolvedOptions().timeZone
  const saved = await saveFollowup(taskState, {
    request: call,
    endpoint: 'crm.call_analysis.workspace.confirm_task',
    params: {
      name: props.name,
      run_name: result.value.name,
      index: proposalIndex.value,
      expected_viewer: data.value.viewer,
      mutation_id: crypto.randomUUID(),
      values: {
        title: taskTitle.value,
        ...chosenContext(),
        assigned_to: assignee.value,
        due_date: callbackDeadline(due.value, dayjs, zone, local),
      },
    },
    isCurrent: () => !disposed,
  })
  if (saved) {
    taskOpen.value = false
    await load()
    window.dispatchEvent(new Event('crm-call-work-updated'))
  }
}
const poll = setInterval(() => {
  if (running.value && document.visibilityState === 'visible') load()
}, 3000)
onBeforeUnmount(() => {
  disposed = true
  version++
  peopleVersion++
  clearInterval(poll)
})
load()
</script>
