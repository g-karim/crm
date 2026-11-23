<template>
  <div class="flex min-h-0 flex-1 flex-col">
    <LayoutHeader>
      <template #left-header
        ><h1 class="text-lg font-semibold">{{ __('Мои отчёты') }}</h1></template
      >
      <template #right-header>
        <Button
          :route="{ name: 'Dashboard' }"
          icon-left="lucide-chart-column"
          >{{ __('Аналитика') }}</Button
        >
        <Button :route="{ name: 'DashboardLayout' }" variant="ghost">{{
          __('Мои графики')
        }}</Button>
      </template>
    </LayoutHeader>
    <main class="board-workspace" :aria-busy="loading">
      <aside class="board-library">
        <Button
          variant="solid"
          icon-left="lucide-plus"
          :disabled="!options || !verified"
          @click="create()"
          >{{ __('Новый отчёт') }}</Button
        >
        <section class="space-y-2">
          <h2 class="text-sm font-semibold text-ink-gray-7">
            {{ __('Сохранённые доски') }}
          </h2>
          <Button
            v-for="item in verified ? boards : []"
            :key="item.name"
            :route="{ name: 'AnalyticsReports', query: { board: item.name } }"
            :variant="item.name === board?.name ? 'subtle' : 'ghost'"
            class="w-full justify-start"
          >
            {{ item.title
            }}<span v-if="item.audience === 'Team'" class="ml-2 text-xs">{{
              __('Команда')
            }}</span>
          </Button>
          <p
            v-if="verified && options && !boards.length"
            class="text-sm text-ink-gray-7"
          >
            {{ __('Сохранённых досок пока нет') }}
          </p>
        </section>
        <section v-if="verified && options" class="space-y-2">
          <h2 class="text-sm font-semibold text-ink-gray-7">
            {{ __('Шаблоны') }}
          </h2>
          <Button
            v-for="template in options.templates"
            :key="template.title"
            variant="ghost"
            class="w-full justify-start"
            @click="create(template)"
          >
            {{ template.title }}
          </Button>
        </section>
      </aside>

      <div class="board-content">
        <Alert
          v-if="workspaceError || error"
          theme="red"
          :title="workspaceError || error"
          :dismissible="false"
        />
        <p v-else-if="loading" role="status">{{ __('Загрузка отчёта…') }}</p>

        <div
          v-if="verified && options && !draft && !reportPrompt"
          class="flex justify-start"
        >
          <Button
            icon-left="lucide-message-square"
            @click="reportPrompt = { text: '' }"
          >
            {{ __('Отчёт по запросу') }}
          </Button>
        </div>
        <Card
          v-if="verified && reportPrompt"
          :title="__('Черновик отчёта по запросу')"
        >
          <form class="space-y-3" @submit.prevent="suggest">
            <FormControl
              v-model="reportPrompt.text"
              type="textarea"
              :label="__('Что нужно показать')"
              :placeholder="
                __('Пропущенные звонки и SLA по сотрудникам за 30 дней')
              "
              :description="
                __('Показатели подбираются по ключевым словам из каталога CRM.')
              "
              maxlength="320"
              :disabled="suggesting"
            />
            <div class="flex flex-wrap gap-2">
              <Button
                type="submit"
                variant="solid"
                :loading="suggesting"
                :disabled="reportPrompt.text.trim().length < 3"
              >
                {{ __('Подобрать показатели') }}
              </Button>
              <Button
                variant="ghost"
                :disabled="suggesting"
                @click="reportPrompt = null"
              >
                {{ __('Отмена') }}
              </Button>
            </div>
          </form>
        </Card>
        <p
          v-if="verified && draftNote && draft"
          role="status"
          class="text-sm text-ink-gray-7"
        >
          {{ draftNote }}
        </p>
        <form
          v-if="verified && draft && options && draftAccessible"
          class="space-y-4"
          @submit.prevent="refreshPreview"
        >
          <Card :title="__('Настройка отчёта')">
            <div class="grid gap-3 sm:grid-cols-2">
              <FormControl
                v-model="draft.title"
                id="analytics-board-title"
                :label="__('Название')"
                maxlength="100"
                required
              />
              <FormControl
                v-model="periodMode"
                type="select"
                :label="__('Период')"
                :options="periods"
              />
              <template v-if="periodMode === 'fixed'">
                <FormControl
                  v-model="draft.definition.period.from_date"
                  type="date"
                  format="YYYY-MM-DD"
                  :label="__('Дата начала')"
                  data-field="board-from-date"
                  required
                />
                <FormControl
                  v-model="draft.definition.period.to_date"
                  type="date"
                  format="YYYY-MM-DD"
                  :label="__('Дата окончания')"
                  data-field="board-to-date"
                  required
                />
                <p
                  v-if="periodError"
                  role="alert"
                  class="text-sm text-ink-red-9 sm:col-span-2"
                >
                  {{ periodError }}
                </p>
              </template>
              <FormControl
                v-model="draft.audience"
                type="select"
                :label="__('Доступ')"
                :options="audiences"
              />
              <FormControl
                v-if="draft.audience === 'Team'"
                v-model="draft.team_lead"
                type="select"
                :label="__('Команда')"
                :options="options.teams"
              />
              <FormControl
                v-for="filter in filterControls"
                :key="filter.key"
                v-model="draft.definition.filters[filter.key]"
                type="select"
                :label="filter.label"
                :placeholder="__('Все')"
                :options="[
                  { value: '', label: __('Все') },
                  ...(options.filters[filter.key] || []),
                ]"
              />
            </div>
          </Card>

          <Card
            v-for="(item, index) in draft.definition.cards"
            :key="index"
            :title="options.catalog[item.metric]?.label || __('Показатель')"
          >
            <template #actions>
              <Button
                v-if="draft.definition.cards.length > 1"
                variant="ghost"
                icon="lucide-x"
                :label="__('Убрать показатель')"
                @click="draft.definition.cards.splice(index, 1)"
              />
            </template>
            <div class="grid gap-3 sm:grid-cols-2">
              <FormControl
                :model-value="item.metric"
                type="select"
                :label="__('Показатель')"
                :options="metrics"
                @update:model-value="changeMetric(item, $event)"
              />
              <template v-if="item.metric === 'goal_progress'">
                <FormControl
                  :model-value="goalChoiceKey(item.goal)"
                  type="select"
                  :label="__('Цель CRM')"
                  :options="goalOptionsFor(item.goal)"
                  :disabled="goalLoading || Boolean(goalOptions.reason)"
                  :placeholder="__('Выберите цель')"
                  @update:model-value="setGoal(item, $event)"
                />
                <p
                  v-if="
                    goalOptions.reason ||
                    (!goalLoading && !goalOptions.choices.length)
                  "
                  class="text-sm text-ink-gray-7 sm:col-span-2"
                >
                  {{ goalMessage(goalOptions.reason || 'goal_unavailable') }}
                </p>
              </template>
              <template v-else>
                <FormControl
                  :model-value="item.group"
                  type="select"
                  :label="__('Группировка')"
                  :options="groups(item)"
                  @update:model-value="changeGroup(item, $event)"
                />
                <FormControl
                  v-if="item.group"
                  v-model="item.display"
                  type="select"
                  :label="__('Вид')"
                  :options="displays"
                />
                <FormControl
                  v-if="Object.keys(customFields(item)).length"
                  :model-value="item.custom_field"
                  type="select"
                  :label="__('Пользовательское поле')"
                  :options="customOptions(item)"
                  @update:model-value="changeField(item, $event)"
                />
                <FormControl
                  v-if="item.custom_field"
                  v-model="item.custom_value"
                  type="select"
                  :label="__('Значение поля')"
                  :options="[
                    { value: '', label: __('Любое') },
                    ...(customFields(item)[item.custom_field]?.values || []),
                  ]"
                />
                <FormControl
                  v-if="!item.group && !item.custom_field"
                  :model-value="item.calculation"
                  type="select"
                  :label="__('Формула')"
                  :options="calculations"
                  @update:model-value="setCalculation(item, $event)"
                />
                <FormControl
                  v-if="item.calculation"
                  v-model="item.operand"
                  type="select"
                  :label="__('Сравнить с показателем')"
                  :options="compatible(item)"
                />
                <template
                  v-if="options.catalog[item.metric]?.object === 'call'"
                >
                  <FormControl
                    v-for="filter in callControls.filter(
                      ({ key }) =>
                        callOptions[key]?.length || item.call_filters[key],
                    )"
                    :key="filter.key"
                    v-model="item.call_filters[filter.key]"
                    type="select"
                    :label="filter.label"
                    :placeholder="__('Все')"
                    :options="
                      availableCallOptions(
                        filter.key,
                        item.call_filters[filter.key],
                      )
                    "
                  />
                </template>
              </template>
            </div>
            <p class="mt-3 text-sm text-ink-gray-7">
              {{ dateLabel(options.catalog[item.metric]?.date)
              }}<template v-if="options.catalog[item.metric]?.formula">
                · {{ options.catalog[item.metric].formula }}</template
              >
            </p>
          </Card>

          <div class="flex flex-wrap items-center gap-2">
            <Button
              v-if="draft.definition.cards.length < 8"
              icon-left="lucide-plus"
              @click="addCard"
              >{{ __('Добавить показатель') }}</Button
            >
            <Button
              type="submit"
              :loading="previewing"
              :disabled="Boolean(periodError || goalError)"
              >{{ __('Пересчитать') }}</Button
            >
            <Button
              variant="solid"
              :loading="saving"
              :disabled="
                !draft.title.trim() ||
                Boolean(periodError || goalError) ||
                goalOptions.reason === 'goal_period'
              "
              @click="save"
              >{{ __('Сохранить отчёт') }}</Button
            >
            <Button variant="ghost" @click="cancel">{{ __('Отмена') }}</Button>
          </div>
        </form>

        <template v-if="verified && board && !draft">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 class="text-xl font-semibold text-ink-gray-9">
                {{ board.title }}
              </h2>
            </div>
            <div class="flex flex-wrap gap-2">
              <Button
                v-if="board.can_edit"
                icon-left="lucide-pencil"
                @click="edit"
                >{{ __('Настроить') }}</Button
              >
              <Button
                v-if="board.can_edit"
                variant="ghost"
                icon-left="lucide-copy"
                @click="duplicate"
                >{{ __('Скопировать доску') }}</Button
              >
              <Button
                v-if="board.can_edit"
                id="analytics-board-history"
                variant="ghost"
                icon-left="lucide-history"
                @click="openHistory"
                >{{ __('История настроек') }}</Button
              >
              <Button icon-left="lucide-refresh-cw" @click="open(board.name)">{{
                __('Обновить')
              }}</Button>
            </div>
          </div>
        </template>

        <p
          v-if="
            verified &&
            !loading &&
            !draft &&
            !board &&
            !workspaceError &&
            !error
          "
          class="rounded-lg border border-outline-gray-2 bg-surface-elevation-1 p-5 text-ink-gray-7"
        >
          {{ __('Выберите сохранённую доску или начните с шаблона.') }}
        </p>

        <section
          v-if="verified && report"
          class="board-cards"
          :aria-label="__('Результаты отчёта')"
        >
          <p class="col-span-full text-sm text-ink-gray-7">
            {{ __('Период результатов') }} · {{ report.context.from_date }} —
            {{ report.context.to_date }} · {{ report.context.timezone }}
            <span
              v-if="report.selected_period?.to_date > report.context.to_date"
            >
              · {{ __('Выбранный период заканчивается') }}
              {{ report.selected_period.to_date }}
            </span>
          </p>
          <Card
            v-for="(card, index) in report.cards"
            :key="index"
            :title="card.label"
            class="board-result"
          >
            <template #actions>
              <Button
                v-if="
                  report.token &&
                  !draft &&
                  (card.object !== 'goal' || card.goal)
                "
                variant="ghost"
                icon="lucide-download"
                :label="__('Выгрузить CSV')"
                @click="download(index)"
              />
            </template>
            <template v-if="card.object === 'goal'">
              <template v-if="card.goal">
                <p class="text-sm text-ink-gray-7">
                  {{ goalScopeName(card.goal) }}
                </p>
                <dl class="my-3 flex flex-wrap gap-x-6 gap-y-3">
                  <div>
                    <dt class="text-sm text-ink-gray-7">{{ __('Факт') }}</dt>
                    <dd class="text-2xl-semibold tabular-nums text-ink-gray-9">
                      {{ format(card.value, card.unit, card.goal.currency) }}
                    </dd>
                  </div>
                  <div>
                    <dt class="text-sm text-ink-gray-7">
                      {{
                        card.goal.direction === 'max' ? __('Лимит') : __('План')
                      }}
                    </dt>
                    <dd class="text-2xl-semibold tabular-nums text-ink-gray-9">
                      {{
                        format(card.goal.target, card.unit, card.goal.currency)
                      }}
                    </dd>
                  </div>
                  <div v-if="card.goal.progress != null">
                    <dt class="text-sm text-ink-gray-7">
                      {{ __('Выполнение') }}
                    </dt>
                    <dd class="text-2xl-semibold tabular-nums text-ink-gray-9">
                      {{ format(card.goal.progress, 'percent') }}
                    </dd>
                  </div>
                </dl>
                <Badge
                  v-if="card.goal.met != null"
                  :theme="card.goal.met ? 'green' : 'amber'"
                >
                  {{ goalStatus(card.goal) }}
                </Badge>
                <p class="mt-2 text-sm text-ink-gray-7">
                  {{ card.goal.from_date }} — {{ card.goal.to_date }} ·
                  {{ card.goal.basis }}
                </p>
              </template>
            </template>
            <div v-else class="text-2xl-semibold tabular-nums text-ink-gray-9">
              {{ format(card.value, card.unit) }}
            </div>
            <p v-if="card.rate_base" class="mt-1 text-sm text-ink-gray-7">
              {{ rateBasis(card.rate_base) }}
            </p>
            <p
              v-if="card.date && card.object !== 'goal'"
              class="mt-1 text-sm text-ink-gray-7"
            >
              {{ dateLabel(card.date) }}
              <template v-if="card.date === 'expected_close_on'">
                · {{ report.context.forecast_from }} —
                {{ report.context.forecast_to }}
              </template>
            </p>
            <p v-if="card.operand_label" class="mt-2 text-sm text-ink-gray-7">
              {{
                card.calculation === 'ratio' ? __('В доле от') : __('Разница с')
              }}
              · {{ card.operand_label }}
            </p>
            <p
              v-if="!card.complete || card.reason"
              class="mt-2 text-sm text-ink-amber-9"
            >
              {{ goalMessage(card.reason) }}
            </p>
            <div v-if="card.display === 'bar' && card.rows.length" class="h-48">
              <AnalyticsChart :config="chart(card)" />
            </div>
            <AnalyticsTable
              v-if="card.rows.length"
              :columns="resultColumns(card.group)"
              :rows="card.rows"
              :label="card.label"
              min-width="0"
              class="mt-2"
            >
              <template #cell="{ row, column, value }">
                <div v-if="column.key === 'value'" class="grid text-right">
                  <span>{{ format(value, card.unit) }}</span>
                  <span v-if="row.rate_base" class="text-sm text-ink-gray-7">
                    {{ rateBasis(row.rate_base) }}
                  </span>
                </div>
                <span v-else>{{ value || __('Без значения') }}</span>
              </template>
            </AnalyticsTable>
          </Card>
        </section>
      </div>
    </main>
    <Dialog
      :model-value="verified && Boolean(history)"
      :title="__('История настроек')"
      size="lg"
      @update:model-value="closeHistory"
      @after-leave="focusAfterHistory"
    >
      <div v-if="history" class="grid gap-3">
        <p class="text-sm text-ink-gray-7">
          {{
            __(
              'Прежние настройки открываются в редакторе. Расчёт использует текущие данные.',
            )
          }}
        </p>
        <Alert
          v-if="history.error"
          theme="red"
          :title="history.error"
          :dismissible="false"
        />
        <p v-if="history.busy && !history.rows.length" role="status">
          {{ __('Загрузка истории…') }}
        </p>
        <p
          v-else-if="
            !history.rows.length && history.nextStart == null && !history.error
          "
        >
          {{ __('Прежних настроек пока нет.') }}
        </p>
        <ul
          v-if="history.rows.length"
          class="grid max-h-[45vh] gap-2 overflow-y-auto pr-1"
        >
          <li
            v-for="item in history.rows"
            :key="item.name"
            class="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-outline-gray-2 p-3"
          >
            <div class="min-w-0">
              <p class="font-medium">
                {{ __('Настройки до изменения') }}
                <time
                  class="block text-sm tabular-nums text-ink-gray-7"
                  :datetime="item.changed_at.replace(' ', 'T')"
                  >{{ item.changed_at }}</time
                >
              </p>
              <p
                v-for="(formula, index) in item.formulas"
                :key="index"
                class="mt-1 text-sm text-ink-gray-7"
              >
                {{ formula.label }}
                {{ formula.calculation === 'ratio' ? '/' : '−' }}
                {{ formula.operand }}
              </p>
            </div>
            <Button :disabled="history.busy" @click="editRevision(item.name)">{{
              __('В редактор')
            }}</Button>
          </li>
        </ul>
        <Button
          v-if="history.nextStart != null"
          class="justify-self-start"
          :loading="history.busy"
          @click="loadHistory(history.nextStart)"
        >
          {{ __('Показать ещё') }}
        </Button>
      </div>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
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
import LayoutHeader from '@/components/LayoutHeader.vue'
import AnalyticsChart from '@/components/Analytics/AnalyticsChart.vue'
import AnalyticsTable from '@/components/Analytics/AnalyticsTable.vue'
import { sessionUser } from '@/stores/session'
import { formatAnalyticsNumber } from '@/utils/analyticsNumbers'

const route = useRoute()
const router = useRouter()
const endpoint = 'crm.analytics.boards.'
const options = ref(null)
const boards = ref([])
const board = ref(null)
const draft = ref(null)
const reportPrompt = ref(null)
const suggesting = ref(false)
const draftNote = ref('')
const report = ref(null)
const history = ref(null)
const verified = ref(false)
const error = ref('')
const workspaceError = ref('')
const loading = ref(false)
const saving = ref(false)
const previewing = ref(false)
const draftAccessible = computed(
  () =>
    !draft.value?.name ||
    (board.value?.name === draft.value.name && board.value.can_edit),
)
let workspaceRequest
let workspaceTimer
let viewer = sessionUser()
let previewNumber = 0
let mutation = null
const units = { count: '', percent: '%', days: __('дн.') }
const clone = (value) => JSON.parse(JSON.stringify(value))
const preset = (value, label) => ({ value, label })
const periods = [
  preset(7, __('7 дней')),
  preset(30, __('30 дней')),
  preset(90, __('90 дней')),
  preset('week', __('Текущая неделя')),
  preset('month', __('Текущий месяц')),
  preset('quarter', __('Текущий квартал')),
  preset('fixed', __('Фиксированные даты')),
]
const periodMode = computed({
  get: () =>
    draft.value?.definition.period?.mode ?? draft.value?.definition.days,
  set: (value) => {
    const definition = draft.value.definition
    if (definition.period?.mode === 'fixed') {
      draft.value.fixedDates = { ...definition.period }
    }
    if (value === 'fixed') {
      delete definition.days
      definition.period = {
        ...options.value.default_period,
        ...draft.value.fixedDates,
        mode: 'fixed',
      }
    } else if (['week', 'month', 'quarter'].includes(value)) {
      delete definition.days
      definition.period = { mode: value }
    } else {
      delete definition.period
      definition.days = Number(value)
    }
  },
})
const periodError = computed(() => {
  const period = draft.value?.definition.period
  if (period?.mode !== 'fixed') return ''
  if (
    !period.from_date ||
    !period.to_date ||
    period.from_date > period.to_date
  ) {
    return __('Укажите обе даты. Начало должно быть не позже окончания.')
  }
  return ''
})
const scopedCallOptions = ref({})
const goalOptions = ref({ choices: [] })
const goalLoading = ref(false)
const draftSelection = computed(() => {
  const definition = draft.value?.definition
  if (!definition || periodError.value) return ''
  return JSON.stringify({
    ...(definition.period
      ? { period: definition.period }
      : { days: Number(definition.days) }),
    filters: activeFilters(definition.filters),
  })
})
const callSelection = computed(() => {
  const definition = draft.value?.definition
  if (
    periodError.value ||
    !definition?.cards.some(
      (card) => options.value?.catalog[card.metric]?.object === 'call',
    )
  )
    return ''
  const filters = activeFilters(definition.filters)
  if (
    !definition.period &&
    Number(definition.days) === 30 &&
    !Object.keys(filters).length
  )
    return ''
  return draftSelection.value
})
const goalSelection = computed(() =>
  draft.value?.definition.cards.some((card) => card.metric === 'goal_progress')
    ? draftSelection.value
    : '',
)
const goalError = computed(() =>
  Boolean(
    draft.value?.definition.cards.some(
      (card) => card.metric === 'goal_progress' && !card.goal,
    ),
  ),
)
const callOptions = computed(() =>
  callSelection.value
    ? scopedCallOptions.value
    : options.value?.call_filters || {},
)
watch(callSelection, async (selection, _previous, onCleanup) => {
  scopedCallOptions.value = {}
  if (!selection) return
  const request = new AbortController()
  onCleanup(() => request.abort())
  try {
    const choices = await api(
      'call_filter_options',
      { selection },
      request.signal,
    )
    if (!request.signal.aborted) scopedCallOptions.value = choices
  } catch {
    // An unavailable filter source leaves existing filter values editable.
  }
})
watch(goalSelection, async (selection, _previous, onCleanup) => {
  goalOptions.value = { choices: [] }
  goalLoading.value = Boolean(selection)
  if (!selection) return
  const request = new AbortController()
  onCleanup(() => request.abort())
  try {
    const result = await api('goal_options', { selection }, request.signal)
    if (!request.signal.aborted) goalOptions.value = result
  } catch {
    if (!request.signal.aborted)
      goalOptions.value = { choices: [], reason: 'goal_unavailable' }
  } finally {
    if (!request.signal.aborted) goalLoading.value = false
  }
})
const displays = [
  preset('table', __('Таблица')),
  preset('bar', __('График и таблица')),
]
const calculations = [
  preset('', __('Значение')),
  preset('ratio', __('Доля в процентах')),
  preset('difference', __('Разница')),
]
const filterControls = [
  { key: 'owner', label: __('Ответственный') },
  { key: 'pipeline', label: __('Воронка') },
  { key: 'source', label: __('Источник') },
]
const callControls = [
  { key: 'line', label: __('Линия') },
  { key: 'direction', label: __('Направление') },
  { key: 'outcome', label: __('Итог звонка') },
]
const groupNames = {
  team: 'Команда',
  forecast_category: 'Категория прогноза',
  source: 'Источник',
  employee: 'Сотрудник',
  closing_owner: 'Ответственный при победе',
  stage: 'Этап',
  pipeline: 'Воронка',
  line: 'Линия',
  day: 'Дата',
  week: 'Начало недели',
  outcome: 'Итог',
  sla: 'Срок перезвона',
  custom: 'Пользовательское поле',
}
const dateNames = {
  created_on: 'По дате создания',
  won_on: 'По дате победы',
  lost_on: 'По дате потери',
  closed_on: 'По дате закрытия',
  now: 'На текущий момент',
  expected_close_on: 'По прогнозной дате',
  started_on: 'По дате звонка',
  goal_period: 'По периоду цели',
}
const dateLabel = (key) => (dateNames[key] ? __(dateNames[key]) : '')
const resultColumns = (group) => [
  { key: 'label', label: __(groupNames[group] || 'Группа') },
  { key: 'value', label: __('Значение'), numeric: true },
]
const audiences = computed(() => [
  preset('Private', __('Личный')),
  ...(options.value?.teams.length ? [preset('Team', __('Командный'))] : []),
])
const metrics = computed(() =>
  Object.entries(options.value?.catalog || {}).map(([value, item]) =>
    preset(value, __(item.label)),
  ),
)
const customFields = (item) => {
  const metric = options.value.catalog[item.metric]
  return metric.custom ? options.value.custom_fields[metric.object] || {} : {}
}
const customOptions = (item) => [
  preset('', __('Без поля')),
  ...Object.entries(customFields(item)).map(([value, field]) =>
    preset(value, field.label),
  ),
]
const groups = (item) => [
  preset('', __('Без группировки')),
  ...[
    ...options.value.catalog[item.metric].groups,
    ...(Object.keys(customFields(item)).length ? ['custom'] : []),
  ].map((value) => preset(value, __(groupNames[value]))),
]
const compatible = (item) => {
  const chosen = options.value.catalog[item.metric]
  return metrics.value.filter(({ value }) => {
    const other = options.value.catalog[value]
    return (
      value !== item.metric &&
      other.object === chosen.object &&
      other.date === chosen.date &&
      other.unit === chosen.unit
    )
  })
}

function makeCard(item = {}) {
  const group = item.group || ''
  return {
    metric: item.metric || 'won_count',
    group,
    display: item.display || (group ? 'table' : 'number'),
    calculation: '',
    operand: '',
    custom_field: '',
    custom_value: '',
    call_filters: {},
    ...item,
  }
}
function goalChoiceKey(goal) {
  if (!goal) return ''
  return JSON.stringify({
    scope: goal.scope,
    subject: goal.subject,
    metric: goal.metric,
  })
}
function goalScopeName(goal) {
  if (goal.scope === 'Company') return __('Вся компания')
  return goal.scope === 'Team'
    ? [__('Команда'), goal.subject_label].join(' · ')
    : goal.subject_label
}
function goalOptionsFor(selected) {
  const choices = goalOptions.value.choices.map((goal) => ({
    value: goalChoiceKey(goal),
    label: `${goal.label} · ${goalScopeName(goal)}`,
  }))
  const current = goalChoiceKey(selected)
  if (current && !choices.some(({ value }) => value === current))
    choices.push({ value: current, label: __('Сохранённая цель') })
  return choices
}
function setGoal(item, value) {
  item.goal = value ? JSON.parse(value) : null
}
function goalStatus(goal) {
  if (goal.direction === 'max')
    return goal.met ? __('В пределах лимита') : __('Лимит превышен')
  return goal.met ? __('Цель выполнена') : __('Цель пока не выполнена')
}
function goalMessage(reason) {
  return (
    {
      goal_period: __(
        'Для цели выберите полную календарную неделю, месяц или квартал.',
      ),
      goal_filters: __(
        'Для цели нужен полный срез. Проверьте воронку, источник и сотрудника.',
      ),
      goal_unavailable: __('Для этого периода нет доступной цели.'),
      goal_currency: __('Валюта цели отличается от валюты отчёта.'),
    }[reason] || __('Часть данных недоступна')
  )
}
function format(value, unit, currency = report.value?.context.currency) {
  if (value == null) return '—'
  const number = formatAnalyticsNumber(value)
  const suffix = unit === 'currency' ? currency : units[unit]
  return suffix ? number + ' ' + suffix : number
}
function rateBasis(base) {
  const counted = formatAnalyticsNumber(base.eligible)
  if (base.eligible === 0) return __('Нет звонков с известным исходом')
  return `${formatAnalyticsNumber(base.matched)} ${__('из')} ${counted}`
}
function chart(card) {
  return {
    title: '',
    data: card.rows.map((row) => ({
      group: row.label || __('Без значения'),
      amount: row.value == null ? null : Number(row.value),
    })),
    xAxis: { key: 'group', type: 'category' },
    series: [{ name: 'amount', type: 'bar', color: 'var(--surface-blue-7)' }],
    echartOptions: {
      animation: false,
      legend: { show: false },
      grid: { top: 12, bottom: 32, left: 48, right: 12 },
    },
  }
}
function addCard() {
  draft.value.definition.cards.push(makeCard())
}
function changeMetric(item, value) {
  delete item.goal
  Object.assign(item, makeCard({ metric: value }))
}
function changeGroup(item, value) {
  Object.assign(item, {
    group: value,
    display: value ? 'table' : 'number',
    calculation: '',
    operand: '',
  })
  if (value === 'custom' && !item.custom_field)
    item.custom_field = Object.keys(customFields(item))[0] || ''
}
function changeField(item, value) {
  Object.assign(item, {
    custom_field: value,
    custom_value: '',
    calculation: '',
    operand: '',
  })
  if (!value && item.group === 'custom') changeGroup(item, '')
}
function setCalculation(item, value) {
  item.calculation = value
  item.operand = value ? compatible(item)[0]?.value || '' : ''
}

async function api(method, args = {}, signal) {
  const response = await fetch(
    '/api/method/' + endpoint + method + '?' + new URLSearchParams(args),
    { cache: 'no-store', signal },
  )
  if (!response.ok)
    throw Object.assign(new Error(method), { status: response.status })
  return (await response.json()).message
}

function routeBoard() {
  return typeof route.query.board === 'string' ? route.query.board : ''
}

function clearEditor() {
  draft.value = null
  reportPrompt.value = null
  draftNote.value = ''
  mutation = null
  report.value = null
}

function suspendWorkspace() {
  workspaceRequest?.abort()
  workspaceRequest = null
  verified.value = false
  history.value = null
  loading.value = false
  previewNumber++
  previewing.value = false
}

function clearWorkspace() {
  suspendWorkspace()
  boards.value = []
  board.value = null
  options.value = null
  report.value = null
}

function syncViewer() {
  const current = sessionUser()
  if (current !== viewer) {
    viewer = current
    clearWorkspace()
    clearEditor()
  }
  return current
}

async function refreshWorkspace(name = routeBoard(), { hide = false } = {}) {
  const actor = syncViewer()
  if (!actor || !navigator.onLine) {
    clearWorkspace()
    workspaceError.value = actor
      ? __('Нет связи. Отчёт откроется после проверки доступа.')
      : __('Войдите в CRM, чтобы открыть отчёты.')
    return
  }
  const editor = draft.value
  const updatePreview = Boolean(editor && report.value)
  if (hide) suspendWorkspace()
  else workspaceRequest?.abort()
  const request = new AbortController()
  workspaceRequest = request
  const deadline = setTimeout(() => request.abort(), 15000)
  loading.value = !verified.value
  workspaceError.value = ''
  try {
    const data = await api(
      'get_workspace',
      {
        name,
        include_options: true,
        include_report: !editor,
      },
      request.signal,
    )
    if (workspaceRequest !== request) return
    if (syncViewer() !== actor)
      return refreshWorkspace(routeBoard(), { hide: true })
    if (data.viewer !== actor) {
      clearWorkspace()
      workspaceError.value = __('Войдите в CRM, чтобы открыть отчёты.')
      return
    }
    options.value = data.options
    boards.value = data.boards
    board.value = data.selected?.board || null
    if (
      history.value &&
      (!board.value?.can_edit ||
        history.value.modified !== board.value.modified)
    )
      history.value = null
    report.value = draft.value ? null : data.selected?.preview || null
    verified.value = true
    if (name && !data.selected && (!draft.value || draft.value.name))
      workspaceError.value = __('Этот отчёт недоступен или был изменён.')
    if (updatePreview && draft.value === editor && draftAccessible.value)
      refreshPreview()
  } catch (failure) {
    if (workspaceRequest !== request) return
    clearWorkspace()
    workspaceError.value = [401, 403].includes(failure.status)
      ? __('Доступ к отчётам недоступен для текущего сеанса.')
      : __(
          'Не удалось проверить доступ к отчётам. Обновите страницу или проверьте связь.',
        )
  } finally {
    clearTimeout(deadline)
    if (workspaceRequest === request) {
      loading.value = false
      workspaceRequest = null
    }
  }
}

function open(name) {
  suspendWorkspace()
  clearEditor()
  board.value = null
  error.value = ''
  return refreshWorkspace(name, { hide: true })
}

function resume() {
  if (document.visibilityState === 'visible')
    refreshWorkspace(routeBoard(), { hide: true })
  else suspendWorkspace()
}

function restorePage(event) {
  if (event.persisted) resume()
}

function sessionCookieChanged(event) {
  const sessionChanged = [...event.changed, ...event.deleted].some(
    ({ name }) => name === 'user_id',
  )
  if (sessionChanged && sessionUser() !== viewer) {
    syncViewer()
    resume()
  }
}

function canUseWorkspace() {
  const previous = viewer
  if (syncViewer() !== previous) {
    refreshWorkspace(routeBoard(), { hide: true })
    return false
  }
  return verified.value
}

watch(routeBoard, open, { immediate: true })

onMounted(() => {
  window.addEventListener('focus', resume)
  window.addEventListener('online', resume)
  window.addEventListener('offline', resume)
  window.addEventListener('pageshow', restorePage)
  window.cookieStore?.addEventListener('change', sessionCookieChanged)
  document.addEventListener('visibilitychange', resume)
  workspaceTimer = setInterval(() => {
    if (
      document.visibilityState === 'visible' &&
      !workspaceRequest &&
      !saving.value
    )
      refreshWorkspace()
  }, 30000)
})

onBeforeUnmount(() => {
  suspendWorkspace()
  clearInterval(workspaceTimer)
  window.removeEventListener('focus', resume)
  window.removeEventListener('online', resume)
  window.removeEventListener('offline', resume)
  window.removeEventListener('pageshow', restorePage)
  window.cookieStore?.removeEventListener('change', sessionCookieChanged)
  document.removeEventListener('visibilitychange', resume)
})

function create(template) {
  if (!canUseWorkspace() || !options.value) return
  report.value = null
  error.value = ''
  mutation = null
  reportPrompt.value = null
  draftNote.value = ''
  draft.value = {
    title: template?.title || '',
    audience: 'Private',
    definition: {
      ...(template?.period ? { period: clone(template.period) } : { days: 30 }),
      filters: {},
      cards: template ? template.cards.map(makeCard) : [makeCard()],
    },
  }
}
async function suggest() {
  if (!canUseWorkspace()) return
  const prompt = reportPrompt.value
  suggesting.value = true
  error.value = ''
  try {
    const result = await call('crm.analytics.board_drafts.suggest', {
      text: prompt.text,
    })
    if (!canUseWorkspace() || prompt !== reportPrompt.value) return
    if (!result?.definition) {
      error.value = __(
        'Укажите показатели из каталога, например пропущенные звонки или просроченные задачи.',
      )
      return
    }
    create({ title: __('Новый отчёт'), cards: result.definition.cards })
    draft.value.definition.days = result.definition.days
    draftNote.value = result.default_period
      ? __(
          'Предложен период 30 дней. Проверьте показатели, период и фильтры перед сохранением.',
        )
      : __(
          'Проверьте предложенные показатели, период и фильтры перед сохранением.',
        )
  } catch {
    if (prompt === reportPrompt.value)
      error.value = __('Не удалось подобрать показатели. Попробуйте ещё раз.')
  } finally {
    suggesting.value = false
  }
}
function edit() {
  if (!canUseWorkspace() || !board.value?.can_edit) return
  mutation = null
  draft.value = clone(board.value)
}
function openHistory() {
  if (!canUseWorkspace() || !board.value?.can_edit) return
  history.value = {
    name: board.value.name,
    modified: board.value.modified,
    rows: [],
    nextStart: null,
    busy: false,
    error: '',
  }
  loadHistory(0)
}
function closeHistory(open) {
  if (!open) history.value = null
}
async function loadHistory(start) {
  const state = history.value
  if (!canUseWorkspace() || !state || state.busy) return
  state.busy = true
  state.error = ''
  try {
    const page = await api('list_revisions', {
      name: state.name,
      modified: state.modified,
      start,
    })
    if (!canUseWorkspace() || history.value !== state) return
    state.rows.push(...page.rows)
    state.nextStart = page.next_start
  } catch {
    state.error = __(
      'Не удалось загрузить историю. Обновите отчёт и попробуйте снова.',
    )
  } finally {
    state.busy = false
  }
}
async function editRevision(revision) {
  const state = history.value
  if (!canUseWorkspace() || !state || state.busy) return
  state.busy = true
  state.error = ''
  try {
    const definition = await api('get_revision', {
      name: state.name,
      modified: state.modified,
      revision,
    })
    if (!canUseWorkspace() || history.value !== state) return
    closeHistory(false)
    edit()
    draft.value.definition = definition
    draftNote.value = __(
      'Прежние настройки загружены. После сохранения появится новая версия.',
    )
    refreshPreview()
  } catch {
    state.error = __(
      'Эту версию открыть не удалось. Проверьте доступ к выбранным полям и обновите отчёт.',
    )
  } finally {
    state.busy = false
  }
}
function focusAfterHistory() {
  const target = draft.value
    ? 'analytics-board-title'
    : 'analytics-board-history'
  document.getElementById(target)?.focus()
}
function duplicate() {
  if (!canUseWorkspace() || !board.value?.can_edit) return
  const source = clone(board.value.definition)
  create({ title: board.value.title + ' ' + __('копия'), cards: source.cards })
  draft.value.definition = source
}
function cancel() {
  open(typeof route.query.board === 'string' ? route.query.board : '')
}
function activeFilters(values) {
  return Object.fromEntries(Object.entries(values).filter(([, value]) => value))
}
function availableCallOptions(key, selected) {
  const choices = callOptions.value[key] || []
  return [
    { value: '', label: __('Все') },
    ...choices,
    ...(selected && !choices.some(({ value }) => value === selected)
      ? [{ value: selected, label: __('Сохранённый фильтр') }]
      : []),
  ]
}
function config() {
  const value = clone(draft.value.definition)
  if ('days' in value) value.days = Number(value.days)
  value.filters = activeFilters(value.filters)
  for (const card of value.cards) {
    if (card.metric !== 'goal_progress')
      card.call_filters = activeFilters(card.call_filters)
  }
  return value
}
watch(
  () => draft.value?.definition,
  (definition) => {
    previewNumber++
    previewing.value = false
    if (definition) report.value = null
  },
  { deep: true, flush: 'sync' },
)
async function refreshPreview() {
  if (
    !canUseWorkspace() ||
    !draft.value ||
    !draftAccessible.value ||
    periodError.value ||
    goalError.value
  )
    return
  const request = ++previewNumber
  previewing.value = true
  error.value = ''
  try {
    const result = await api('preview', {
      definition: JSON.stringify(config()),
    })
    if (canUseWorkspace() && request === previewNumber) report.value = result
  } catch (failure) {
    if (request === previewNumber && [401, 403].includes(failure.status))
      resume()
    else if (request === previewNumber)
      error.value = __(
        'Не удалось пересчитать. Проверьте период, показатели, группировку и формулу.',
      )
  } finally {
    if (request === previewNumber) previewing.value = false
  }
}
async function save() {
  if (
    !canUseWorkspace() ||
    !draft.value ||
    !draftAccessible.value ||
    saving.value ||
    periodError.value ||
    goalError.value ||
    goalOptions.value.reason === 'goal_period'
  )
    return
  saving.value = true
  error.value = ''
  const editor = draft.value
  const actor = viewer
  try {
    const params = {
      title: draft.value.title,
      definition: config(),
      audience: draft.value.audience,
      team_lead: draft.value.audience === 'Team' ? draft.value.team_lead : null,
      expected_viewer: options.value.viewer,
      name: draft.value.name,
      modified: draft.value.modified,
    }
    const key = JSON.stringify(params)
    if (mutation?.key !== key)
      mutation = { key, id: globalThis.crypto.randomUUID() }
    const saved = await call(endpoint + 'save', {
      ...params,
      mutation: mutation.id,
    })
    const sameViewer = syncViewer() === params.expected_viewer
    if (!sameViewer || editor !== draft.value) return
    if (route.query.board === saved.name) await open(saved.name)
    else await router.replace({ query: { board: saved.name } })
  } catch (failure) {
    if (syncViewer() !== actor || editor !== draft.value) return
    if (failure?.exc_type === 'PermissionError') resume()
    error.value =
      failure?.exc_type === 'TimestampMismatchError'
        ? __(
            'Отчёт изменился в другой сессии. Проверьте последнюю версию перед сохранением.',
          )
        : __('Не удалось сохранить. Проверьте настройки и доступ.')
  } finally {
    saving.value = false
  }
}
async function download(index) {
  if (!canUseWorkspace() || !report.value?.token) return
  const sourceReport = report.value
  try {
    const data = await api('export', { token: sourceReport.token, index })
    if (!canUseWorkspace() || sourceReport !== report.value) return
    const link = document.createElement('a')
    const url = URL.createObjectURL(
      new Blob(['\ufeff', data.csv], { type: 'text/csv;charset=utf-8' }),
    )
    link.href = url
    link.download = data.filename
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 0)
  } catch (failure) {
    if (!canUseWorkspace() || sourceReport !== report.value) return
    if ([401, 403].includes(failure.status)) resume()
    else error.value = __('Отчёт изменился. Обновите его перед выгрузкой.')
  }
}
</script>

<style scoped>
.board-workspace {
  display: grid;
  grid-template-columns: 210px minmax(0, 1fr);
  gap: 24px;
  padding: 20px 24px;
  min-height: 0;
  flex: 1;
  overflow-y: auto;
  background: var(--surface-gray-1);
}
.board-library {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-width: 0;
}
.board-content {
  display: grid;
  min-width: 0;
  gap: 16px;
  align-content: start;
}
.board-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 360px), 1fr));
  gap: 12px;
}
.board-result {
  min-width: 0;
}
@media (max-width: 700px) {
  .board-workspace {
    grid-template-columns: minmax(0, 1fr);
    padding: 14px 12px;
    gap: 16px;
  }
}
</style>
