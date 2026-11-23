<template>
  <Card
    :title="t('Call script checks', 'Проверка по скриптам')"
    class="min-w-0"
  >
    <template #actions>
      <div class="flex flex-wrap justify-end gap-2">
        <Button
          variant="ghost"
          icon-left="lucide-refresh-cw"
          :loading="loading"
          @click="load(0)"
          >{{ t('Refresh', 'Обновить') }}</Button
        >
        <Button
          v-if="report?.can_configure"
          icon-left="lucide-settings-2"
          @click="editSettings"
          >{{ t('Scripts and limit', 'Скрипты и лимит') }}</Button
        >
      </div>
    </template>
    <Alert
      v-if="loadError"
      theme="red"
      :title="
        t('Could not load script checks', 'Не удалось загрузить проверки')
      "
      :dismissible="false"
    />
    <p v-else-if="loading && !report" role="status">
      {{ t('Loading…', 'Загрузка…') }}
    </p>
    <p v-else-if="report && !report.available" class="text-sm text-ink-gray-7">
      {{
        t(
          'Call script checks are unavailable.',
          'Проверки по скриптам недоступны.',
        )
      }}
    </p>
    <template v-else-if="report">
      <p class="mb-3 text-sm text-ink-gray-7">
        {{
          t(
            'The local draft finds configured phrases in a saved transcript. Only confirmed decisions affect the score.',
            'Локальный черновик ищет заданные фразы в сохранённой расшифровке. Оценку формируют подтверждённые решения.',
          )
        }}
      </p>
      <dl class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div v-for="item in kpis" :key="item.key">
          <dt class="text-sm text-ink-gray-7">{{ item.label }}</dt>
          <dd class="mt-1 text-lg font-semibold text-ink-gray-9">
            {{ item.value }}
          </dd>
          <dd v-if="item.note" class="mt-1 text-sm text-ink-gray-7">
            {{ item.note }}
          </dd>
        </div>
      </dl>
      <p v-if="report.line_restricted" class="mt-3 text-sm text-ink-gray-7">
        {{
          t('Ready on selected lines', 'Готово к проверке на выбранных линиях')
        }}
        {{ report.eligible_ready }} / {{ report.transcript_coverage.ready }}
      </p>
      <details class="mt-4">
        <summary>
          {{ t('Transcript coverage', 'Покрытие расшифровками') }}
        </summary>
        <dl class="mt-2 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
          <div
            v-for="item in transcriptStates"
            :key="item.value"
            class="min-w-0"
          >
            <dt class="break-words text-sm text-ink-gray-7">
              {{ item.label }}
            </dt>
            <dd class="text-base font-medium tabular-nums text-ink-gray-9">
              {{ report.transcript_coverage[item.value] }}
            </dd>
          </div>
        </dl>
      </details>
      <p v-if="!report.configured" class="mt-3 text-sm text-ink-gray-7">
        {{
          t(
            'No script selected for the pilot yet.',
            'Для пилота ещё не настроены скрипты.',
          )
        }}
      </p>
      <details v-if="report.can_review" class="mt-4">
        <summary>
          {{ t('By script criterion', 'По критериям скрипта') }}
        </summary>
        <p
          v-if="!report.script_breakdown?.length"
          class="mt-2 text-sm text-ink-gray-7"
        >
          {{
            t(
              'No confirmed reviews in this selection.',
              'В выбранном срезе пока нет подтверждённых проверок.',
            )
          }}
        </p>
        <template v-else>
          <p class="mt-2 text-sm text-ink-gray-7">
            {{
              t(
                'The latest confirmed review of the current transcript counts once per call. The pass rate uses applicable decisions.',
                'Для каждого звонка учитывается последняя подтверждённая проверка текущей расшифровки. Доля выполнения считается по применимым решениям.',
              )
            }}
          </p>
          <div
            v-for="script in report.script_breakdown"
            :key="script.key"
            class="mt-4"
          >
            <p class="break-words text-base font-medium text-ink-gray-9">
              {{ script.title }}
            </p>
            <p class="mb-2 mt-1 text-sm text-ink-gray-7">
              {{ t('Version', 'Версия') }} {{ script.revision.slice(0, 8) }} ·
              {{ t('Calls reviewed', 'Проверено звонков') }}
              {{ script.confirmed }}
            </p>
            <AnalyticsTable
              class="hidden md:block"
              :rows="script.criteria"
              :columns="criterionColumns"
              :label="
                t('Criteria for', 'Критерии скрипта') +
                ' ' +
                script.title +
                ' · ' +
                script.revision.slice(0, 8)
              "
              min-width="560px"
            >
              <template #cell="{ column, value }">
                <span class="break-words">{{
                  column.key === 'pass_rate' ? percent(value) : value
                }}</span>
              </template>
            </AnalyticsTable>
            <ul
              class="divide-y divide-outline-gray-2 rounded border border-outline-gray-2 md:hidden"
              :aria-label="
                t('Criteria for', 'Критерии скрипта') +
                ' ' +
                script.title +
                ' · ' +
                script.revision.slice(0, 8)
              "
            >
              <li
                v-for="item in script.criteria"
                :key="item.key"
                class="space-y-2 p-3"
              >
                <p class="break-words font-medium text-ink-gray-9">
                  {{ item.label }}
                </p>
                <dl
                  class="grid grid-cols-2 gap-x-2 gap-y-1 text-sm text-ink-gray-7"
                >
                  <div
                    v-for="column in criterionColumns.slice(1)"
                    :key="column.key"
                  >
                    <dt>{{ column.label }}</dt>
                    <dd class="font-medium tabular-nums text-ink-gray-9">
                      {{
                        column.key === 'pass_rate'
                          ? percent(item.pass_rate)
                          : item[column.key]
                      }}
                    </dd>
                  </div>
                </dl>
              </li>
            </ul>
          </div>
        </template>
      </details>
      <div class="mt-4">
        <div class="mb-3 grid gap-3 sm:grid-cols-2">
          <FormControl
            v-model="transcriptFilter"
            type="select"
            :label="t('Call selection', 'Отбор звонков')"
            :options="transcriptOptions"
          />
          <FormControl
            v-if="queueMode && report.queue?.scripts.length"
            v-model="queueScript"
            type="select"
            :label="t('Review script', 'Скрипт для проверки')"
            :options="scriptChoices(report.queue.scripts)"
          />
        </div>
        <p v-if="loading" role="status">
          {{ t('Loading calls…', 'Загрузка звонков…') }}
        </p>
        <template v-else>
          <p
            v-if="queueMode && !report.queue?.script"
            class="mb-3 text-sm text-ink-gray-7"
          >
            {{
              report.queue?.scripts.length
                ? t(
                    'This script is no longer available. Choose another.',
                    'Скрипт недоступен. Выберите другой.',
                  )
                : t(
                    'Configure a script to see calls for review.',
                    'Настройте скрипт, чтобы увидеть звонки на проверку.',
                  )
            }}
          </p>
          <p v-else-if="queueMode" class="mb-3 text-sm text-ink-gray-7">
            {{ t('Calls to review', 'Звонков к проверке') }}
            <strong>{{ report.total }}</strong>
          </p>
          <ul
            v-if="queueMode && report.rows.length"
            :aria-label="
              t('Calls to review by script', 'Звонки на проверку по скрипту')
            "
            class="divide-y divide-outline-gray-2 rounded-md border border-outline-gray-2 md:hidden"
          >
            <li
              v-for="row in report.rows"
              :key="row.name"
              class="space-y-2 p-3"
            >
              <p class="break-words text-base font-medium text-ink-gray-9">
                {{ row.agent || t('Unassigned', 'Не назначен') }}
              </p>
              <p class="text-sm text-ink-gray-7">{{ date(row.at) }}</p>
              <div class="flex flex-wrap items-center justify-between gap-2">
                <Badge theme="gray">{{ queueLabel(row.queue_state) }}</Badge>
                <Button
                  variant="outline"
                  :aria-label="reviewLabel(row)"
                  @click="inspect(row)"
                  >{{ t('Review', 'Проверить') }}</Button
                >
              </div>
            </li>
          </ul>
          <AnalyticsTable
            :class="queueMode && report.rows.length ? 'hidden md:block' : ''"
            :rows="report.rows"
            :columns="columns"
            row-key="name"
            :label="
              queueMode
                ? t(
                    'Calls to review by script',
                    'Звонки на проверку по скрипту',
                  )
                : transcriptFilter
                  ? t(
                      'Calls by transcript state',
                      'Звонки по состоянию расшифровки',
                    )
                  : t(
                      'Calls marked with a completed transcript',
                      'Звонки с завершённой расшифровкой',
                    )
            "
            :empty-text="
              queueMode
                ? t(
                    'No calls need review in this selection.',
                    'В этом срезе нет звонков, которым нужна проверка.',
                  )
                : t(
                    'No accessible calls for this state.',
                    'В текущем срезе нет звонков с таким состоянием.',
                  )
            "
          >
            <template #cell="{ row, column, value }">
              <span v-if="column.key === 'at'">{{ date(value) }}</span>
              <span v-else-if="column.key === 'transcript_state'">{{
                transcriptLabel(value)
              }}</span>
              <Badge v-else-if="column.key === 'queue_state'" theme="gray">
                {{ queueLabel(value) }}
              </Badge>
              <Badge
                v-else-if="column.key === 'status'"
                :theme="value === 'Confirmed' ? 'green' : 'gray'"
                >{{
                  value === 'Not reviewed' &&
                  row.transcript_state === 'ready' &&
                  !row.review_line_allowed
                    ? t('Line outside selection', 'Линия вне отбора')
                    : status(value)
                }}</Badge
              >
              <span v-else-if="column.key === 'score'">{{
                percent(value)
              }}</span>
              <Button
                v-else-if="
                  column.key === 'action' &&
                  report.can_review &&
                  row.review_line_allowed &&
                  row.transcript_state === 'ready'
                "
                variant="ghost"
                :aria-label="reviewLabel(row)"
                @click="inspect(row)"
                >{{ t('Open', 'Открыть') }}</Button
              >
              <Button
                v-else-if="column.key === 'action'"
                variant="ghost"
                :route="journalRoute(row.name)"
                :aria-label="
                  t('Open call in journal', 'Открыть звонок в журнале') +
                  ' · ' +
                  date(row.at)
                "
                >{{ t('Journal', 'Журнал') }}</Button
              >
              <span v-else>{{ value || '—' }}</span>
            </template>
          </AnalyticsTable>
          <div class="mt-2 flex gap-2">
            <Button v-if="report.start" @click="load(report.start - 25)">{{
              t('Previous', 'Назад')
            }}</Button>
            <Button
              v-if="report.start + 25 < report.total"
              @click="load(report.start + 25)"
              >{{ t('Next', 'Далее') }}</Button
            >
          </div>
        </template>
      </div>
      <details v-if="report.days.length" class="mt-3">
        <summary>{{ t('Daily coverage', 'Динамика по дням') }}</summary>
        <AnalyticsTable
          :rows="report.days"
          :columns="dayColumns"
          :label="
            t('Confirmed reviews by day', 'Подтверждённые проверки по дням')
          "
        >
          <template #cell="{ column, value }"
            ><span>{{
              column.key === 'average' ? percent(value) : value
            }}</span></template
          >
        </AnalyticsTable>
      </details>
    </template>
  </Card>

  <Dialog
    v-model="configOpen"
    :title="
      t('Call scripts and local review limit', 'Скрипты и лимит проверок')
    "
    size="2xl"
    :dismissible="!busy"
    :show-close-button="!busy"
  >
    <p v-if="loadingConfig" role="status">
      {{ t('Loading settings…', 'Загрузка настроек…') }}
    </p>
    <Alert
      v-if="configError"
      theme="red"
      :title="configError"
      :dismissible="false"
    />
    <form v-if="configDraft" class="space-y-4" @submit.prevent="saveConfig">
      <FormControl
        v-model="configDraft.daily_limit"
        type="number"
        :min="0"
        :max="500"
        :label="t('New drafts per day', 'Новых черновиков в день')"
        required
        :disabled="busy"
      />
      <p class="text-sm text-ink-gray-7">
        {{
          t(
            'Zero suspends new drafts. Local checks have no model charges.',
            'Ноль приостанавливает создание черновиков. Локальная проверка не расходует бюджет внешних моделей.',
          )
        }}
      </p>
      <FormControl
        v-model="lineMode"
        type="select"
        :label="t('Lines for script review', 'Линии для проверки по скрипту')"
        :options="[
          { value: 'all', label: t('All lines', 'Все линии') },
          { value: 'selected', label: t('Selected lines', 'Выбранные линии') },
        ]"
        :disabled="busy"
      />
      <fieldset
        v-if="lineMode === 'selected'"
        class="grid gap-3 rounded-md border border-outline-gray-2 p-3"
      >
        <legend class="px-1 text-sm font-medium text-ink-gray-9">
          {{ t('Lines visible for this period', 'Линии за выбранный период') }}
        </legend>
        <p v-if="!lineChoices.length" class="text-sm text-ink-gray-7">
          {{
            t(
              'Select a period with calls to configure lines.',
              'Выберите период со звонками, чтобы настроить линии.',
            )
          }}
        </p>
        <FormControl
          v-for="line in lineChoices"
          :key="line.value"
          type="checkbox"
          :label="line.label"
          :model-value="configDraft.allowed_lines.includes(line.value)"
          :disabled="busy"
          @update:model-value="setLine(line.value, $event)"
        />
      </fieldset>
      <FormControl
        v-if="configDraft.scripts.length"
        v-model="editKey"
        type="select"
        :label="t('Script to edit', 'Скрипт для настройки')"
        :options="scriptChoices(configDraft.scripts)"
        :disabled="busy"
      />
      <div v-if="editedScript" class="space-y-3">
        <FormControl
          v-model="editedScript.title"
          :label="t('Script title', 'Название скрипта')"
          maxlength="120"
          required
          :disabled="busy"
        />
        <div
          v-for="criterion in editedScript.criteria"
          :key="criterion.key"
          class="rounded-md border border-outline-gray-2 p-3"
        >
          <FormControl
            v-model="criterion.label"
            :label="t('Criterion', 'Критерий')"
            maxlength="120"
            required
            :disabled="busy"
          />
          <FormControl
            v-model="criterion.lines"
            type="textarea"
            :label="
              t(
                'One accepted phrase per line',
                'Допустимые фразы по одной на строку',
              )
            "
            class="mt-2"
            required
            :disabled="busy"
          />
          <Button
            v-if="editedScript.criteria.length > 1"
            variant="ghost"
            class="mt-1"
            @click="
              editedScript.criteria = editedScript.criteria.filter(
                (item) => item.key !== criterion.key,
              )
            "
            >{{ t('Remove criterion', 'Убрать критерий') }}</Button
          >
        </div>
        <div class="flex flex-wrap gap-2">
          <Button
            v-if="editedScript.criteria.length < 12"
            icon-left="lucide-plus"
            :disabled="busy"
            @click="editedScript.criteria.push(newCriterion())"
            >{{ t('Add criterion', 'Добавить критерий') }}</Button
          >
          <Button variant="ghost" :disabled="busy" @click="removeScript">{{
            t('Remove script from settings', 'Убрать скрипт из настроек')
          }}</Button>
        </div>
      </div>
      <div class="flex flex-wrap gap-2">
        <Button
          v-if="configDraft.scripts.length < 5"
          icon-left="lucide-plus"
          :disabled="busy"
          @click="addScript"
          >{{ t('Add script', 'Добавить скрипт') }}</Button
        >
        <Button type="submit" variant="solid" :loading="busy">{{
          t('Save settings', 'Сохранить настройки')
        }}</Button>
      </div>
    </form>
  </Dialog>

  <Dialog
    v-model="workOpen"
    :title="t('Call script review', 'Проверка звонка по скрипту')"
    size="2xl"
    :dismissible="!busy"
    :show-close-button="!busy"
  >
    <Alert
      v-if="workError"
      theme="red"
      :title="workError"
      :dismissible="false"
    />
    <p v-if="loadingWork" role="status">
      {{ t('Loading review…', 'Загрузка проверки…') }}
    </p>
    <div v-if="workSettings" class="space-y-3">
      <p v-if="!workSettings.scripts.length">
        {{ t('There are no configured scripts.', 'Скрипты не настроены.') }}
      </p>
      <FormControl
        v-else
        v-model="workScript"
        type="select"
        :label="t('Review script', 'Скрипт проверки')"
        :options="scriptChoices(workSettings.scripts)"
        :disabled="busy"
      />
      <p v-if="workspace" class="text-sm text-ink-gray-7">
        {{ t('Drafts today', 'Черновиков сегодня') }}
        {{ workspace.budget.used }} / {{ workspace.budget.limit }}
      </p>
      <p
        v-if="workspace && !workspace.available"
        class="text-sm text-ink-gray-7"
      >
        {{
          t(
            'This call has no usable local transcript.',
            'Для звонка нет доступной локальной расшифровки.',
          )
        }}
      </p>
      <div v-if="workspace?.available">
        <Button
          variant="ghost"
          icon-left="lucide-file-text"
          :loading="transcriptLoading"
          @click="toggleTranscript"
        >
          {{
            transcript
              ? t('Hide transcript', 'Скрыть расшифровку')
              : t('Read transcript', 'Читать расшифровку')
          }}
        </Button>
        <p
          v-if="transcript"
          class="mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap break-words rounded-md bg-surface-gray-2 p-3 text-sm text-ink-gray-8"
          tabindex="0"
        >
          {{ transcript }}
        </p>
      </div>
      <Button
        v-if="workspace?.available && !workspace.review"
        variant="solid"
        :loading="busy"
        :disabled="workspace.budget.used >= workspace.budget.limit"
        @click="perform('start_review')"
      >
        {{ t('Create local draft', 'Создать локальный черновик') }}
      </Button>
      <form
        v-if="workspace?.review"
        class="space-y-3"
        @submit.prevent="perform('confirm_review')"
      >
        <p class="text-sm">
          <strong>{{ status(workspace.review.state) }}</strong
          ><span
            v-if="
              workspace.review.score !== '' && workspace.review.score != null
            "
          >
            · {{ percent(workspace.review.score) }}</span
          >
        </p>
        <div
          v-for="criterion in workspace.review.criteria"
          :key="criterion.key"
          class="rounded-md border border-outline-gray-2 p-3"
        >
          <p class="mb-2 font-medium">{{ criterion.label }}</p>
          <blockquote
            v-if="criterion.evidence"
            class="mb-2 break-words text-sm text-ink-gray-7"
          >
            «{{ criterion.evidence }}»
          </blockquote>
          <p v-else class="mb-2 text-sm text-ink-gray-7">
            {{
              t(
                'No matching phrase found. Review manually.',
                'Совпадение не найдено. Проверьте вручную.',
              )
            }}
          </p>
          <FormControl
            v-model="decisions[criterion.key]"
            type="select"
            :label="t('Decision', 'Решение') + ' · ' + criterion.label"
            :options="decisionOptions"
            :disabled="busy"
          />
        </div>
        <Button
          type="submit"
          variant="solid"
          :loading="busy"
          :disabled="
            !workspace.review.criteria.every((item) => decisions[item.key])
          "
          >{{ t('Confirm review', 'Подтвердить оценку') }}</Button
        >
      </form>
    </div>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Alert,
  Badge,
  Button,
  Card,
  Dialog,
  FormControl,
  call,
} from 'frappe-ui'
import { formatAnalyticsNumber } from '@/utils/analyticsNumbers'
import { callScopeQuery } from '@/utils/callAnalyticsRoute'
import AnalyticsTable from './AnalyticsTable.vue'

const props = defineProps({
  filters: { type: Object, required: true },
  zone: { type: String, required: true },
  t: { type: Function, required: true },
  lang: { type: String, required: true },
  journalRoute: { type: Function, required: true },
})
const emit = defineEmits(['editing'])
const route = useRoute()
const router = useRouter()
const report = ref(null)
const transcriptFilter = computed({
  get: () => callScopeQuery(route.query).call_transcript_state || '',
  set: (value) =>
    router.replace({
      query: { ...route.query, call_transcript_state: value || undefined },
    }),
})
const queueMode = computed(() => transcriptFilter.value === 'pending_review')
const requestedScript = computed(() =>
  queueMode.value ? callScopeQuery(route.query).call_review_script || '' : '',
)
const queueScript = computed({
  get: () => report.value?.queue?.script || '',
  set: (value) =>
    router.replace({
      query: { ...route.query, call_review_script: value || undefined },
    }),
})
const loading = ref(false)
const loadError = ref(false)
const configOpen = ref(false)
const loadingConfig = ref(false)
const configDraft = ref(null)
const lineMode = ref('all')
const configError = ref('')
const editKey = ref(null)
const workOpen = ref(false)
const loadingWork = ref(false)
const workError = ref('')
const workSettings = ref(null)
const workCall = ref(null)
const workScript = ref(null)
const workspace = ref(null)
const decisions = ref({})
const transcript = ref('')
const transcriptLoading = ref(false)
const busy = ref(false)
let generation = 0
let workGeneration = 0
let configGeneration = 0
const endpoint = 'crm.analytics.call_quality.'

const encode = computed(() => JSON.stringify(props.filters))
const locale = computed(() => (props.lang === 'ru' ? 'ru-RU' : 'en-US'))
const percent = (value) =>
  value == null || value === ''
    ? '—'
    : formatAnalyticsNumber(value, locale.value) + '%'
const date = (value) =>
  new Intl.DateTimeFormat(locale.value, {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone: props.zone,
  }).format(new Date(value))
const reviewLabel = (row) =>
  props.t('Review call', 'Проверить звонок') + ' · ' + date(row.at)
const col = (key, en, ru) => ({ key, label: props.t(en, ru) })
const columns = computed(() => [
  col('at', 'Date', 'Дата'),
  col('agent', 'Employee', 'Сотрудник'),
  ...(queueMode.value
    ? [col('queue_state', 'Review state', 'Состояние проверки')]
    : [
        col('transcript_state', 'Transcript', 'Расшифровка'),
        col('status', 'Status', 'Статус'),
        col('score', 'Score', 'Оценка'),
      ]),
  col('action', 'Actions', 'Действия'),
])
const dayColumns = computed(() => [
  col('key', 'Day', 'День'),
  col('connected', 'Connections', 'Соединения'),
  col('ready_transcripts', 'Transcripts ready', 'Готовые расшифровки'),
  col('confirmed', 'Confirmed', 'Подтверждено'),
  col('scored', 'Scored', 'С баллом'),
  col('average', 'Average score', 'Средняя оценка'),
])
const criterionColumns = computed(() => [
  col('label', 'Criterion', 'Критерий'),
  col('passed', 'Passed', 'Выполнено'),
  col('failed', 'Failed', 'Не выполнено'),
  col('not_applicable', 'Not applicable', 'Неприменимо'),
  col('pass_rate', 'Pass rate', 'Доля выполнения'),
])
const kpis = computed(() => [
  {
    key: 'ready',
    label: props.t('Transcripts ready for review', 'Расшифровки для проверки'),
    value:
      report.value.transcript_coverage.ready + ' / ' + report.value.connected,
    note: props.t('Out of all connections', 'Из всех соединений'),
  },
  {
    key: 'drafts',
    label: props.t('Calls with a draft', 'Звонки с черновиком'),
    value: report.value.drafts,
  },
  {
    key: 'coverage',
    label: props.t(
      'Confirmed out of all connections',
      'Подтверждено из всех соединений',
    ),
    value:
      report.value.confirmed +
      ' / ' +
      report.value.connected +
      ' · ' +
      percent(report.value.coverage),
  },
  {
    key: 'score',
    label: props.t('Average confirmed score', 'Средняя подтверждённая оценка'),
    value: percent(report.value.average),
    note:
      props.t('Calls scored', 'Звонков с баллом') + ' · ' + report.value.scored,
  },
])
const transcriptLabels = {
  ready: ['Ready for review', 'Готова к проверке'],
  not_started: ['No processing status', 'Без статуса обработки'],
  in_progress: ['Queued or processing', 'В очереди или обрабатывается'],
  failed: ['Processing failed', 'Ошибка обработки'],
  empty: ['Empty transcript', 'Пустая расшифровка'],
  too_long: ['Transcript exceeds length limit', 'Расшифровка слишком длинная'],
  unavailable: ['State unavailable', 'Состояние недоступно'],
}
const transcriptLabel = (value) => props.t(...transcriptLabels[value])
const transcriptStates = computed(() =>
  Object.keys(transcriptLabels).map((value) => ({
    value,
    label: transcriptLabel(value),
  })),
)
const transcriptOptions = computed(() => [
  {
    value: '',
    label: props.t('Marked as completed', 'Отмечены как завершённые'),
  },
  ...transcriptStates.value,
  {
    value: 'eligible',
    label: props.t('Ready on allowed lines', 'Готовы на разрешённых линиях'),
  },
  ...(report.value?.can_review && (report.value.configured || queueMode.value)
    ? [
        {
          value: 'pending_review',
          label: props.t('Need script review', 'Нужна проверка по скрипту'),
        },
      ]
    : []),
])
function queueLabel(value) {
  if (value === 'draft')
    return props.t('Draft to confirm', 'Черновик к подтверждению')
  if (value === 'transcript_changed')
    return props.t('Transcript changed', 'Изменилась расшифровка')
  if (value === 'script_changed')
    return props.t('Script changed', 'Изменился скрипт')
  if (value === 'changed')
    return props.t(
      'Script and transcript changed',
      'Изменились скрипт и расшифровка',
    )
  return props.t('Awaiting first review', 'Первая проверка')
}
const decisionOptions = computed(() => [
  { value: 'Passed', label: props.t('Passed', 'Выполнено') },
  { value: 'Failed', label: props.t('Failed', 'Не выполнено') },
  { value: 'Not applicable', label: props.t('Not applicable', 'Неприменимо') },
])
const editedScript = computed(() =>
  configDraft.value?.scripts.find((item) => item.key === editKey.value),
)
const lineChoices = computed(() => {
  const visible = configDraft.value?.line_options || []
  const known = new Set(visible.map((line) => line.value))
  return [
    ...visible,
    ...(configDraft.value?.allowed_lines || [])
      .filter((value) => !known.has(value))
      .map((value) => ({
        value,
        label:
          props.t('Outside this period', 'Вне выбранного периода') +
          ' · ' +
          value.slice(0, 8),
      })),
  ]
})
function setLine(value, checked) {
  const selected = new Set(configDraft.value.allowed_lines)
  if (checked) selected.add(value)
  else selected.delete(value)
  configDraft.value.allowed_lines = [...selected]
}
function status(value) {
  const labels = {
    Draft: ['Draft', 'Черновик'],
    Confirmed: ['Confirmed', 'Подтверждено'],
    'Not reviewed': ['Not reviewed', 'Без оценки'],
    'Needs renewed review': ['Review again', 'Нужна повторная проверка'],
  }
  return labels[value] ? props.t(...labels[value]) : value
}
const scriptChoices = (values) =>
  values.map((item) => ({
    value: item.key,
    label: item.title || props.t('New script', 'Новый скрипт'),
  }))
const id = (prefix) => prefix + crypto.randomUUID().slice(0, 12)
const newCriterion = () => ({ key: id('criterion-'), label: '', lines: '' })
function addScript() {
  const script = { key: id('script-'), title: '', criteria: [newCriterion()] }
  configDraft.value.scripts.push(script)
  editKey.value = script.key
}
function removeScript() {
  configDraft.value.scripts = configDraft.value.scripts.filter(
    (item) => item.key !== editKey.value,
  )
  editKey.value = configDraft.value.scripts[0]?.key
}
async function api(method, params = {}) {
  const response = await fetch(
    '/api/method/' + endpoint + method + '?' + new URLSearchParams(params),
    { cache: 'no-store' },
  )
  if (!response.ok) throw new Error(method)
  return (await response.json()).message
}
async function load(start = 0) {
  const current = ++generation
  loading.value = true
  loadError.value = false
  try {
    const result = await api('get_quality_report', {
      filters: encode.value,
      start,
      transcript_state: transcriptFilter.value,
      ...(requestedScript.value ? { script_key: requestedScript.value } : {}),
    })
    if (current === generation) report.value = result
  } catch {
    if (current === generation) loadError.value = true
  } finally {
    if (current === generation) loading.value = false
  }
}
watch(
  encode,
  () => {
    report.value = null
    load()
  },
  { immediate: true },
)
watch([transcriptFilter, requestedScript], () => load())
watch([configOpen, workOpen], ([config, work]) =>
  emit('editing', config || work),
)
watch(configOpen, (value) => {
  if (!value) configGeneration++
})
watch(workOpen, (value) => {
  if (!value) {
    workGeneration++
    transcript.value = ''
    transcriptLoading.value = false
  }
})
onBeforeUnmount(() => {
  generation++
  configGeneration++
  workGeneration++
  emit('editing', false)
})
async function editSettings() {
  const current = ++configGeneration
  configError.value = ''
  configDraft.value = null
  configOpen.value = true
  loadingConfig.value = true
  try {
    const settings = await api('get_settings', {
      from_date: props.filters.from_date,
      to_date: props.filters.to_date,
    })
    if (current !== configGeneration) return
    configDraft.value = {
      ...settings,
      allowed_lines: settings.allowed_lines || [],
      scripts: settings.scripts.map((script) => ({
        ...script,
        criteria: script.criteria.map((criterion) => ({
          ...criterion,
          lines: criterion.phrases.join('\n'),
        })),
      })),
    }
    lineMode.value = settings.allowed_lines ? 'selected' : 'all'
    editKey.value = settings.scripts[0]?.key
  } catch {
    if (current === configGeneration)
      configError.value = props.t(
        'Could not load scripts.',
        'Не удалось загрузить скрипты.',
      )
  } finally {
    if (current === configGeneration) loadingConfig.value = false
  }
}
async function saveConfig() {
  if (busy.value) return
  const draft = configDraft.value
  if (lineMode.value === 'selected' && !draft.allowed_lines.length) {
    configError.value = props.t(
      'Select at least one line.',
      'Выберите хотя бы одну линию.',
    )
    return
  }
  busy.value = true
  configError.value = ''
  try {
    await call(endpoint + 'save_settings', {
      definition: {
        daily_limit: Number(draft.daily_limit),
        allowed_lines:
          lineMode.value === 'selected' ? draft.allowed_lines : null,
        scripts: draft.scripts.map((item) => ({
          key: item.key,
          title: item.title,
          criteria: item.criteria.map((criterion) => ({
            key: criterion.key,
            label: criterion.label,
            phrases: criterion.lines
              .split('\n')
              .map((value) => value.trim())
              .filter(Boolean),
          })),
        })),
      },
      expected_version: draft.version,
      expected_viewer: draft.viewer,
    })
    configOpen.value = false
    await load()
  } catch {
    configError.value = props.t(
      'Check the title, criteria and phrases. Reload if settings changed.',
      'Проверьте название, критерии и фразы. Если настройки изменились, откройте их заново.',
    )
  } finally {
    busy.value = false
  }
}
async function inspect(row) {
  const current = ++workGeneration
  const selectedScript = report.value?.queue?.script
  workCall.value = row.name
  workSettings.value = null
  workScript.value = null
  workspace.value = null
  workError.value = ''
  workOpen.value = true
  loadingWork.value = true
  try {
    const result = await api('get_settings')
    if (current !== workGeneration) return
    workSettings.value = result
    if (
      selectedScript &&
      !result.scripts.some((script) => script.key === selectedScript)
    ) {
      workError.value = props.t(
        'The selected script is no longer available. Reload the list.',
        'Выбранный скрипт недоступен. Обновите список.',
      )
    } else {
      workScript.value = selectedScript || result.scripts[0]?.key
    }
  } catch {
    if (current === workGeneration)
      workError.value = props.t(
        'Could not open review.',
        'Не удалось открыть проверку.',
      )
  } finally {
    if (current === workGeneration) loadingWork.value = false
  }
}
function setDecisions(review) {
  decisions.value = Object.fromEntries(
    (review?.criteria || []).map((item) => [item.key, item.decision]),
  )
}
async function readWorkspace() {
  if (!workOpen.value || !workScript.value) return
  const current = ++workGeneration
  workError.value = ''
  workspace.value = null
  transcript.value = ''
  transcriptLoading.value = false
  loadingWork.value = true
  try {
    const result = await api('get_workspace', {
      call_log: workCall.value,
      script_key: workScript.value,
    })
    if (current !== workGeneration) return
    workspace.value = result
    setDecisions(result.review)
  } catch {
    if (current === workGeneration)
      workError.value = props.t(
        'Could not open review.',
        'Не удалось открыть проверку.',
      )
  } finally {
    if (current === workGeneration) loadingWork.value = false
  }
}
watch(workScript, readWorkspace)
async function toggleTranscript() {
  if (transcript.value) {
    transcript.value = ''
    return
  }
  const current = workGeneration
  transcriptLoading.value = true
  workError.value = ''
  try {
    const result = await api('get_transcript', {
      call_log: workCall.value,
      ...(workspace.value.review
        ? { review_name: workspace.value.review.name }
        : {}),
    })
    if (current === workGeneration) transcript.value = result.text
  } catch {
    if (current === workGeneration)
      workError.value = props.t(
        'The transcript has changed or is unavailable.',
        'Расшифровка изменилась или недоступна.',
      )
  } finally {
    if (current === workGeneration) transcriptLoading.value = false
  }
}
async function perform(method) {
  if (busy.value) return
  busy.value = true
  workError.value = ''
  const review = workspace.value.review
  try {
    await call(endpoint + method, {
      call_log: workCall.value,
      expected_viewer: workspace.value.viewer,
      ...(method === 'start_review'
        ? {
            script_key: workScript.value,
            expected_version: workspace.value.version,
          }
        : {
            name: review.name,
            expected_version: review.version,
            decisions: decisions.value,
          }),
    })
    await readWorkspace()
    await load()
  } catch (failure) {
    workError.value =
      failure?.exc_type === 'TimestampMismatchError'
        ? props.t(
            'The transcript or review changed. Reopen the call.',
            'Расшифровка или оценка изменилась. Откройте звонок заново.',
          )
        : props.t(
            'Check the daily limit and availability of the transcript.',
            'Проверьте дневной лимит и наличие расшифровки.',
          )
  } finally {
    busy.value = false
  }
}
</script>
