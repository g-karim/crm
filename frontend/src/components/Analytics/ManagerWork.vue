<template>
  <Card class="manager-card" :title="t('Work by manager', 'Работа менеджеров')">
    <template #actions>
      <Button
        v-if="data && !stale"
        icon-left="lucide-list-checks"
        @click="goalsOpen = true"
      >
        {{ t('Goals and KPIs', 'Цели и KPI') }}
      </Button>
      <Button
        v-if="data?.can_edit_plans && !stale"
        variant="solid"
        icon-left="lucide-target"
        @click="openPlan()"
      >
        {{ t('Set a plan', 'Настроить план') }}
      </Button>
    </template>
    <div class="manager-period">
      <div class="min-w-0">
        <div class="manager-period-title">
          <Icon name="lucide-calendar-days" class="size-4 shrink-0" />
          <span>{{ monthLabel }}</span>
        </div>
        <p class="mt-1 text-base text-ink-gray-7">{{ periodNote }}</p>
      </div>
      <div class="manager-period-controls">
        <Button
          icon="lucide-chevron-left"
          variant="outline"
          :label="t('Previous month', 'Предыдущий месяц')"
          :disabled="month <= '1900-01'"
          @click="moveMonth(-1)"
        />
        <FormControl
          :model-value="month"
          type="month"
          variant="outline"
          :aria-label="t('KPI month', 'Месяц KPI')"
          @update:model-value="selectMonth"
          @blur="restoreMonthInput"
        />
        <Button
          icon="lucide-chevron-right"
          variant="outline"
          :label="t('Next month', 'Следующий месяц')"
          :disabled="month >= '2199-12'"
          @click="moveMonth(1)"
        />
      </div>
    </div>
    <p v-if="planNotice" class="manager-notice" role="status">
      <Icon name="lucide-circle-check" class="size-4 shrink-0" />
      {{ planNotice }}
    </p>
    <Alert
      v-if="stale"
      theme="yellow"
      :dismissible="false"
      :title="
        t(
          'Refresh analytics to view current figures',
          'Обновите аналитику, чтобы увидеть актуальные показатели',
        )
      "
    />
    <Alert
      v-else-if="error"
      theme="red"
      :dismissible="false"
      :title="
        t(
          'Manager data could not be loaded',
          'Не удалось загрузить показатели менеджеров',
        )
      "
    >
      <template #footer
        ><Button variant="ghost" @click="load">{{
          t('Retry', 'Повторить')
        }}</Button></template
      >
    </Alert>
    <div
      v-else-if="loading && !data"
      class="py-6 text-ink-gray-6"
      role="status"
    >
      {{ t('Loading…', 'Загрузка…') }}
    </div>
    <template v-else-if="data">
      <p v-if="data.plans_filtered" class="mb-3 text-base text-ink-gray-7">
        {{
          t(
            'This view shows filtered results. Goals apply to the entire month.',
            'Здесь показан факт по выбранным сделкам. План относится ко всему месяцу.',
          )
        }}
      </p>
      <AnalyticsTable
        class="hidden md:block"
        :columns="columns"
        :rows="data.rows"
        :label="t('Managers summary', 'Показатели по менеджерам')"
        :empty-text="
          t(
            'No managers in this selection',
            'По выбранным фильтрам менеджеров нет',
          )
        "
      >
        <template #cell="{ column, row }">
          <Button
            v-if="column.key === 'label'"
            variant="ghost"
            icon-right="lucide-chevron-right"
            @click="selectManager(row.key)"
            >{{ row.label }}</Button
          >
          <ManagerPlanProgress
            v-else-if="
              column.key === 'value_goal' || column.key === 'wins_goal'
            "
            v-bind="goal(row, column.key)"
            :show-label="false"
          />
          <span v-else-if="column.key === 'callbacks'" class="tabular-nums">{{
            row.calls?.callback_unconfirmed ?? '—'
          }}</span>
          <span v-else>{{ row[column.key] ?? '—' }}</span>
        </template>
      </AnalyticsTable>
      <List
        v-if="data.rows.length"
        class="md:hidden"
        :aria-label="t('Managers summary', 'Показатели по менеджерам')"
        :columns="['minmax(0, 1fr)']"
      >
        <ListRow
          v-for="row in data.rows"
          :key="row.key"
          class="relative grid grid-cols-1 gap-0 py-2.5"
        >
          <ListCell class="flex-col items-start gap-1">
            <Button
              variant="ghost"
              icon-right="lucide-chevron-right"
              class="-ml-2"
              @click="selectManager(row.key)"
            >
              {{ row.label }}
            </Button>
            <div
              v-if="row.overdue_tasks || row.calls?.callback_unconfirmed"
              class="flex flex-wrap gap-2"
            >
              <Badge
                v-if="row.overdue_tasks"
                theme="amber"
                :label="t('Overdue: ', 'Просрочено: ') + row.overdue_tasks"
              />
              <Badge
                v-if="row.calls?.callback_unconfirmed"
                theme="amber"
                :label="
                  t('No callback: ', 'Без перезвона: ') +
                  row.calls.callback_unconfirmed
                "
              />
            </div>
            <div class="manager-goals w-full py-1">
              <ManagerPlanProgress
                v-for="key in goalKeys"
                :key="key"
                v-bind="goal(row, key)"
              />
            </div>
          </ListCell>
        </ListRow>
      </List>
      <p v-else class="py-4 text-sm text-ink-gray-6 md:hidden">
        {{
          t(
            'No managers in this selection',
            'По выбранным фильтрам менеджеров нет',
          )
        }}
      </p>
      <p
        v-if="
          data.rows.some(
            (row) =>
              (row.won_value != null && !row.won_value_complete) ||
              (row.won != null && !row.outcomes_complete),
          )
        "
        class="mt-3 text-sm text-ink-gray-7"
      >
        {{ t('* Known portion of the result', '* Известная часть результата') }}
      </p>
      <p v-if="data.rows.length" class="mt-3 text-sm text-ink-gray-7">
        {{
          t(
            'Tasks reflect the current queue. Calls are counted for the selected month.',
            'Задачи показывают текущую очередь. Звонки считаются за выбранный месяц.',
          )
        }}
      </p>
    </template>
  </Card>

  <AnalyticsGoals
    v-model:open="goalsOpen"
    :initial-month="month"
    :lang="lang"
    :t="t"
    @saved="load"
  />

  <ManagerPlanEditor
    :open="planOpen"
    :month="month"
    :month-label="monthLabel"
    :lang="lang"
    :selected-manager="planManager"
    @update:open="setPlanOpen"
    @saved="planSaved"
  />

  <Dialog
    v-model="managerOpen"
    :title="selected?.label"
    size="4xl"
    @close="closeManager"
  >
    <div v-if="selected" class="manager-detail">
      <TabButtons
        v-model="view"
        :options="views"
        :aria-label="t('Manager details', 'Детали работы менеджера')"
      />
      <template v-if="view === 'kpi'">
        <div class="manager-metrics">
          <div v-for="item in kpis" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
        <section class="manager-kpi-goals">
          <h3 class="text-base-medium text-ink-gray-9">{{ monthLabel }}</h3>
          <div class="manager-goals">
            <ManagerPlanProgress
              v-for="key in goalKeys"
              :key="key"
              v-bind="goal(selected, key)"
            />
          </div>
        </section>
      </template>
      <template v-else>
        <div class="manager-metrics">
          <div v-for="item in activity" :key="item.label">
            <span>{{ item.label }}</span
            ><strong>{{ item.value }}</strong>
          </div>
        </div>
        <p v-if="view === 'calls'" class="mb-3 text-base text-ink-gray-6">
          {{
            t(
              'The journal counts recorded calls. The callback metric uses a confirmed link to an outgoing connection.',
              'В расчёте звонки из журнала. Перезвон учитывается по подтверждённой связи с исходящим соединением.',
            )
          }}
        </p>
        <p
          v-if="view === 'calls' && selected.calls?.callback_unknown"
          class="mb-3 text-base text-ink-amber-9"
        >
          {{
            t(
              'Missed calls whose callback cannot be verified:',
              'Пропущенные, для которых нельзя проверить перезвон:',
            )
          }}
          {{ selected.calls.callback_unknown }}
        </p>
        <Alert
          v-if="detailError"
          theme="red"
          :dismissible="false"
          :title="t('Could not load records', 'Не удалось загрузить записи')"
        >
          <template #footer
            ><Button variant="ghost" @click="loadDetail">{{
              t('Retry', 'Повторить')
            }}</Button></template
          >
        </Alert>
        <p v-else-if="detailLoading" role="status">
          {{ t('Loading…', 'Загрузка…') }}
        </p>
        <p v-else-if="detail && !detail.available" role="status">
          {{
            t(
              'Records are unavailable with your current access.',
              'Записи недоступны с вашими правами.',
            )
          }}
        </p>
        <template v-else-if="detail">
          <AnalyticsTable
            :columns="detailColumns"
            :rows="detail.rows"
            row-key="name"
            :label="
              view === 'tasks'
                ? t('Current tasks', 'Текущие задачи')
                : t('Call history', 'История звонков')
            "
            :empty-text="
              view === 'tasks'
                ? t('No current tasks', 'Открытых задач нет')
                : t(
                    'No calls found in the journal',
                    'За этот период в журнале нет доступных звонков',
                  )
            "
          >
            <template #cell="{ column, row }">
              <Button
                v-if="column.key === 'title'"
                variant="ghost"
                :route="{ name: 'Tasks', query: { open: row.name } }"
                >{{ row.title || row.name }}</Button
              >
              <Button
                v-else-if="column.key === 'at'"
                variant="ghost"
                :route="{ name: 'Call Logs', query: { open: row.name } }"
                >{{ date(row.at) }}</Button
              >
              <span v-else-if="column.key === 'due'">{{ date(row.due) }}</span>
              <span v-else-if="column.key === 'direction'">{{
                row.direction === 'Incoming'
                  ? t('Incoming', 'Входящий')
                  : t('Outgoing', 'Исходящий')
              }}</span>
              <Badge
                v-else-if="column.key === 'status'"
                :theme="
                  row.overdue || row.status === 'No Answer' ? 'amber' : 'gray'
                "
                :label="status(row.status)"
              />
              <span v-else-if="column.key === 'callback'">{{
                row.callback_unknown
                  ? t('Unknown', 'Не определён')
                  : row.callback_unconfirmed
                    ? t('Not confirmed', 'Не подтверждён')
                    : duration(row.callback_seconds)
              }}</span>
              <span v-else>{{ row[column.key] ?? '—' }}</span>
            </template>
          </AnalyticsTable>
          <div
            v-if="detail.start || detail.has_more"
            class="mt-3 flex flex-wrap items-center gap-2"
          >
            <Button :disabled="detail.start === 0" @click="start -= 25">{{
              t('Back', 'Назад')
            }}</Button>
            <span class="text-sm text-ink-gray-6"
              >{{ detail.start + 1 }}–{{ detail.start + detail.rows.length }} /
              {{ detail.total }}</span
            >
            <Button :disabled="!detail.has_more" @click="start += 25">{{
              t('Next', 'Далее')
            }}</Button>
          </div>
        </template>
      </template>
    </div>
    <template #actions>
      <Button
        v-if="view === 'calls' && selected && data"
        :route="{
          name: 'Dashboard',
          query: {
            section: 'calls',
            owner: selected.key,
            from_date: data.period.from_date,
            to_date: data.period.to_date,
            pipeline: context.pipeline || undefined,
            source: context.source || undefined,
          },
        }"
        @click="closeManager"
        >{{ t('Full call report', 'К аналитике звонков') }}</Button
      >
      <Button @click="closeManager">{{ t('Close', 'Закрыть') }}</Button>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import {
  Alert,
  Badge,
  Button,
  Card,
  Dialog,
  FormControl,
  Icon,
  TabButtons,
} from 'frappe-ui'
import { List, ListCell, ListRow } from 'frappe-ui/list'
import AnalyticsTable from './AnalyticsTable.vue'
import AnalyticsGoals from './AnalyticsGoals.vue'
import ManagerPlanEditor from './ManagerPlanEditor.vue'
import ManagerPlanProgress from './ManagerPlanProgress.vue'
import { formatAnalyticsNumber } from '@/utils/analyticsNumbers'

const props = defineProps({
  context: { type: Object, required: true },
  stale: { type: Boolean, default: false },
  lang: { type: String, required: true },
  revision: { type: String, default: '' },
})

const data = ref(null)
const error = ref(false)
const loading = ref(false)
const managerOpen = ref(false)
const manager = ref(null)
const view = ref('kpi')
const start = ref(0)
const detail = ref(null)
const detailError = ref(false)
const detailLoading = ref(false)
const month = ref(props.context.as_of.slice(0, 7))
const planOpen = ref(false)
const goalsOpen = ref(false)
const planManager = ref('')
const planNotice = ref('')
let request, detailRequest, opener, planOpener
const t = (en, ru) => (props.lang === 'ru' ? ru : en)
const format = (value) =>
  value == null
    ? '—'
    : formatAnalyticsNumber(value, props.lang === 'ru' ? 'ru-RU' : 'en-US')
const cash = (value) =>
  value == null ? '—' : format(value) + ' ' + props.context.currency
const monthLabel = computed(() =>
  dateAtUTC(month.value + '-01', { month: 'long', year: 'numeric' }),
)
const periodNote = computed(() => {
  if (data.value?.future)
    return t('This month has not started', 'Месяц ещё не начался')
  if (month.value === props.context.as_of.slice(0, 7)) {
    const day = dateAtUTC(
      data.value?.period.to_date || props.context.as_of.slice(0, 10),
      {
        day: 'numeric',
        month: 'long',
      },
    )
    return (
      t('Actual through ', 'Факт по ') +
      day +
      t(' · full month target', ' · план на весь месяц')
    )
  }
  return t(
    'Actual and goals for the calendar month',
    'Факт и план за календарный месяц',
  )
})
function dateAtUTC(value, options) {
  return new Intl.DateTimeFormat(props.lang, {
    ...options,
    timeZone: 'UTC',
  }).format(new Date(value + 'T00:00:00Z'))
}
function selectMonth(value) {
  if (/^(19|20|21)\d{2}-(0[1-9]|1[0-2])$/.test(value)) month.value = value
}
function restoreMonthInput(event) {
  event.target.value = month.value
}
function moveMonth(offset) {
  const [year, selectedMonth] = month.value.split('-').map(Number)
  selectMonth(
    new Date(Date.UTC(year, selectedMonth - 1 + offset, 1))
      .toISOString()
      .slice(0, 7),
  )
}
function openPlan() {
  planOpener = document.activeElement
  planManager.value = scope.value.owner || ''
  planNotice.value = ''
  planOpen.value = true
}
function setPlanOpen(value) {
  planOpen.value = value
  if (!value) nextTick(() => planOpener?.focus())
}
async function planSaved() {
  await load()
  planNotice.value = error.value
    ? t(
        'Plan saved. Retry to refresh the figures.',
        'План сохранён. Повторите загрузку показателей.',
      )
    : t('Plan saved', 'План сохранён')
}
const goalKeys = ['value_goal', 'wins_goal']
function goal(row, key) {
  const money = key === 'value_goal'
  const countOrValue = money ? cash : format
  const actual = money ? row.won_value : row.won
  const complete = money ? row.won_value_complete : row.outcomes_complete
  const target = money ? row.plan : row.wins_plan
  const percent = money ? row.plan_percent : row.wins_plan_percent

  let emptyLabel = t('Plan not set', 'План не задан')
  if (data.value.plans_filtered)
    emptyLabel = t('Goals hidden for this filter', 'План скрыт по фильтру')
  else if (money && row.plan_currency_mismatch)
    emptyLabel = t('Plan uses another currency', 'План в другой валюте')
  else if (target != null)
    emptyLabel = data.value.future
      ? t('Waiting for the month to start', 'Месяц ещё не начался')
      : t('Incomplete data', 'Данные неполные')

  return {
    label: money
      ? t('Won value', 'Сумма побед')
      : t('Won deals', 'Выигранные сделки'),
    actual: countOrValue(actual) + (actual != null && !complete ? ' *' : ''),
    target: target == null ? null : countOrValue(target),
    percent,
    emptyLabel,
    percentLabel: percent == null ? '' : format(percent) + '%',
  }
}
const duration = (seconds) => {
  if (seconds == null) return '—'
  return seconds < 60
    ? seconds + t(' sec', ' с')
    : Math.floor(seconds / 60) +
        t(' min ', ' мин ') +
        (seconds % 60) +
        t(' sec', ' с')
}
const date = (value) =>
  value
    ? new Intl.DateTimeFormat(props.lang, {
        dateStyle: 'short',
        timeStyle: 'short',
        timeZone: props.context.timezone,
      }).format(new Date(value))
    : '—'
const translated = {
  'No Answer': 'Без ответа',
  Completed: 'Завершён',
  Busy: 'Занято',
  Failed: 'Ошибка',
  Canceled: 'Отменён',
  'In Progress': 'В работе',
  Todo: 'К выполнению',
  Backlog: 'В очереди',
  Initiated: 'Начат',
  Ringing: 'Вызов',
  Queued: 'В очереди',
}
const status = (value) =>
  props.lang === 'ru' ? translated[value] || value : value
const selected = computed(() =>
  data.value?.rows.find((row) => row.key === manager.value),
)
const views = computed(() => [
  { value: 'kpi', label: 'KPI' },
  { value: 'tasks', label: t('Tasks', 'Задачи') },
  { value: 'calls', label: t('Calls', 'Звонки') },
])
const columns = computed(() => [
  {
    key: 'label',
    label: t('Manager', 'Менеджер'),
    width: 'minmax(10rem, 1.3fr)',
  },
  {
    key: 'value_goal',
    label: t('Won value', 'Сумма побед'),
    width: 'minmax(12rem, 1.5fr)',
  },
  {
    key: 'wins_goal',
    label: t('Won deals', 'Выигранные сделки'),
    width: 'minmax(9rem, 1.1fr)',
  },
  {
    key: 'overdue_tasks',
    label: t('Overdue tasks', 'Просрочено задач'),
    width: '7.5rem',
    numeric: true,
  },
  {
    key: 'callbacks',
    label: t('Callback needed', 'Без перезвона'),
    width: '7.5rem',
    numeric: true,
  },
])
const kpis = computed(() => {
  const row = selected.value
  if (!row) return []
  return [
    {
      label: t('Won value', 'Сумма побед'),
      value:
        cash(row.won_value) +
        (row.won_value != null && !row.won_value_complete ? ' *' : ''),
    },
    {
      label: t('Wins / losses', 'Победы / потери'),
      value:
        row.won == null
          ? '—'
          : row.won + ' / ' + row.lost + (row.outcomes_complete ? '' : ' *'),
    },
    {
      label: t('Win rate', 'Доля побед'),
      value: row.win_rate == null ? '—' : format(row.win_rate) + '%',
    },
  ]
})
const activity = computed(() => {
  const row = selected.value
  if (view.value === 'tasks')
    return [
      {
        label: t('Open tasks', 'Открытые задачи'),
        value: row.open_tasks ?? '—',
      },
      {
        label: t('Overdue tasks', 'Просроченные задачи'),
        value: row.overdue_tasks ?? '—',
      },
    ]
  const calls = row.calls
  return [
    {
      label: t('Incoming / outgoing', 'Входящие / исходящие'),
      value: calls ? calls.incoming + ' / ' + calls.outgoing : '—',
    },
    {
      label: t('Outgoing answer rate', 'Дозвон исходящих'),
      value: calls?.outgoing_known_outcomes
        ? new Intl.NumberFormat(props.lang, {
            style: 'percent',
            maximumFractionDigits: 1,
          }).format(calls.outgoing_connected / calls.outgoing_known_outcomes)
        : '—',
    },
    {
      label: t('Missed incoming', 'Пропущено входящих'),
      value: calls?.missed ?? '—',
    },
    {
      label: t('Callback needed', 'Без перезвона'),
      value: calls?.callback_unconfirmed ?? '—',
    },
    {
      label: t(
        'Average time to recorded connection',
        'Среднее время до соединения',
      ),
      value: duration(calls?.average_callback_seconds),
    },
  ]
})
const detailColumns = computed(() =>
  view.value === 'tasks'
    ? [
        {
          key: 'title',
          label: t('Task', 'Задача'),
          width: 'minmax(14rem,2fr)',
        },
        { key: 'status', label: t('Status', 'Статус') },
        { key: 'due', label: t('Due', 'Срок') },
      ]
    : [
        { key: 'at', label: t('Date', 'Дата'), width: 'minmax(9rem,1fr)' },
        { key: 'direction', label: t('Direction', 'Направление') },
        { key: 'status', label: t('Status', 'Статус') },
        { key: 'callback', label: t('Callback', 'Перезвон') },
      ],
)
const scope = computed(() =>
  Object.fromEntries(
    ['owner', 'pipeline', 'source']
      .filter((key) => props.context[key])
      .map((key) => [key, props.context[key]]),
  ),
)

async function get(params, signal) {
  const query = new URLSearchParams({
    filters: JSON.stringify(scope.value),
    month: month.value,
    ...params,
  })
  const response = await fetch(
    '/api/method/crm.analytics.manager_work.get_manager_work?' + query,
    {
      credentials: 'same-origin',
      cache: 'no-store',
      signal,
    },
  )
  if (!response.ok) throw new Error('Manager report request failed')
  return (await response.json()).message
}
async function load() {
  request?.abort()
  if (props.stale) return
  const current = new AbortController()
  request = current
  error.value = false
  loading.value = true
  try {
    const response = await get({}, current.signal)
    if (request === current) data.value = response
  } catch {
    if (request === current && !current.signal.aborted) {
      data.value = null
      error.value = true
    }
  } finally {
    if (request === current) loading.value = false
  }
}
async function loadDetail() {
  detailRequest?.abort()
  detail.value = null
  detailError.value = false
  if (!manager.value || props.stale || view.value === 'kpi') return
  const current = new AbortController()
  detailRequest = current
  detailLoading.value = true
  try {
    const response = await get(
      { manager: manager.value, view: view.value, start: start.value },
      current.signal,
    )
    if (detailRequest === current) detail.value = response.detail
  } catch {
    if (detailRequest === current && !current.signal.aborted)
      detailError.value = true
  } finally {
    if (detailRequest === current) detailLoading.value = false
  }
}
function selectManager(value) {
  opener = document.activeElement
  manager.value = value
  view.value = 'kpi'
  start.value = 0
  managerOpen.value = true
}
function closeManager() {
  managerOpen.value = false
  manager.value = null
  detailRequest?.abort()
  nextTick(() => {
    if (opener?.isConnected) opener.focus()
  })
}
watch(view, () => {
  start.value = 0
})
watch([manager, view, start], loadDetail)
const selection = computed(() => JSON.stringify([month.value, scope.value]))
watch(selection, () => {
  if (managerOpen.value) closeManager()
  data.value = null
  planNotice.value = ''
})
watch(
  [selection, () => props.stale, () => props.revision],
  () => {
    if (props.stale && managerOpen.value) closeManager()
    load()
    if (managerOpen.value) loadDetail()
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  request?.abort()
  detailRequest?.abort()
})
</script>

<style scoped>
.manager-card {
  background: var(--surface-elevation-1, var(--surface-gray-1));
  border-color: var(--outline-gray-3);
  min-width: 0;
}
.manager-card :deep(> div:first-child) {
  flex-wrap: wrap;
  gap: 8px 12px;
}
.manager-card :deep(h2) {
  color: var(--ink-gray-9);
}
.manager-period {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  padding: 12px 14px;
  border: 1px solid var(--outline-gray-3);
  border-radius: 8px;
  background: var(--surface-gray-2);
}
.manager-period-title,
.manager-period-controls,
.manager-notice {
  display: flex;
  align-items: center;
  gap: 8px;
}
.manager-period-title {
  color: var(--ink-gray-9);
  font-weight: 600;
  font-size: 16px;
}
.manager-period-title span::first-letter {
  text-transform: uppercase;
}
.manager-period-controls :deep(input) {
  width: 11.5rem;
}
.manager-goals {
  display: grid;
  gap: 10px;
}
.manager-kpi-goals {
  display: grid;
  gap: 12px;
  border: 1px solid var(--outline-gray-3);
  border-radius: 8px;
  padding: 14px;
  margin-bottom: 12px;
}
.manager-notice {
  color: var(--ink-green-9);
  margin-bottom: 12px;
  font-size: 14px;
}
.manager-detail {
  max-height: calc(100dvh - 170px);
  overflow: auto;
}
.manager-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(135px, 1fr));
  gap: 8px;
  margin: 16px 0;
}
.manager-metrics > div {
  padding: 12px;
  background: var(--surface-gray-2);
  border-radius: 6px;
}
.manager-metrics span {
  display: block;
  color: var(--ink-gray-6);
  font-size: 12px;
}
.manager-metrics strong {
  display: block;
  margin-top: 6px;
  font-size: 18px;
  font-variant-numeric: tabular-nums;
}
/* Apply the viewport constraint only to the manager analytics dialog. */
:global(.dialog-content:has(.manager-detail)) {
  margin: 0;
  max-height: calc(100dvh - 32px);
  overflow-y: auto;
}
</style>
