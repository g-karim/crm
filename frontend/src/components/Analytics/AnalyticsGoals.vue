<template>
  <Dialog
    v-model="visible"
    :title="t('Goals and KPIs', 'Цели и KPI')"
    size="2xl"
    :dismissible="!saving"
    :show-close-button="!saving"
  >
    <div class="flex flex-col gap-4">
      <div class="grid gap-3 sm:grid-cols-2">
        <FormControl
          v-model="period"
          type="select"
          :label="t('Goal period', 'Период цели')"
          :options="periods"
          :disabled="saving || !!draft"
        />
        <FormControl
          v-model="day"
          type="text"
          inputmode="numeric"
          :label="t('Date in selected period', 'Дата внутри периода')"
          placeholder="YYYY-MM-DD"
          maxlength="10"
          :disabled="saving || !!draft"
        />
      </div>
      <p v-if="report" class="text-sm text-ink-gray-7">
        {{ showDate(report.start) }} — {{ showDate(report.end) }}
        <span v-if="report.future">
          · {{ t('The period has not started', 'Период ещё не начался') }}
        </span>
      </p>
      <Alert v-if="error" theme="red" :title="error" :dismissible="false" />
      <p v-if="loading" role="status" class="text-ink-gray-7">
        {{ t('Loading goals…', 'Загрузка целей…') }}
      </p>
      <p v-if="notice" role="status" class="text-ink-green-8">{{ notice }}</p>

      <template v-if="report && !loading">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <h3 class="text-base font-semibold text-ink-gray-9">
            {{ t('Plan and actual performance', 'План и факт') }}
          </h3>
          <Button
            v-if="report.can_edit"
            icon-left="lucide-plus"
            :disabled="saving"
            @click="edit()"
            >{{ t('Add a goal', 'Добавить цель') }}</Button
          >
        </div>
        <div v-if="report.rows.length" class="grid gap-2 sm:grid-cols-2">
          <Card
            v-for="row in report.rows"
            :key="row.name"
            :title="row.label"
            class="min-w-0"
          >
            <template #actions>
              <Button
                v-if="row.can_edit"
                icon="lucide-pencil"
                variant="ghost"
                :label="
                  t('Edit goal', 'Изменить цель') +
                  ' · ' +
                  row.label +
                  ' · ' +
                  scopeLabel(row)
                "
                :disabled="saving"
                @click="edit(row)"
              />
            </template>
            <p class="text-sm font-medium text-ink-gray-8">
              {{ scopeLabel(row) }}
            </p>
            <dl class="mt-3 grid grid-cols-2 gap-2 tabular-nums">
              <div>
                <dt class="text-sm text-ink-gray-6">
                  {{ t('Target', 'План') }}
                </dt>
                <dd class="font-semibold text-ink-gray-9">
                  {{ row.direction === 'max' ? '≤ ' : ''
                  }}{{ format(row.target, row) }}
                </dd>
              </div>
              <div>
                <dt class="text-sm text-ink-gray-6">
                  {{ t('Actual', 'Факт') }}
                </dt>
                <dd class="font-semibold text-ink-gray-9">
                  {{ format(row.actual, row) }}
                </dd>
              </div>
            </dl>
            <div class="mt-2 flex flex-wrap items-center gap-2">
              <Badge
                :theme="
                  row.met === null ? 'gray' : row.met ? 'green' : 'orange'
                "
              >
                {{ status(row) }}
              </Badge>
              <span
                v-if="row.progress !== null"
                class="text-sm text-ink-gray-8"
              >
                {{ format(row.progress, { unit: 'percent' }) }}
              </span>
            </div>
            <p class="mt-2 text-sm text-ink-gray-6">{{ row.basis }}</p>
          </Card>
        </div>
        <p v-else class="text-ink-gray-7">
          {{
            t('No goals in this period yet', 'На этот период целей пока нет')
          }}
        </p>
      </template>

      <form
        v-if="draft && report"
        data-goal-editor
        class="rounded-md border border-outline-gray-2 p-3"
        @submit.prevent="save"
      >
        <h3 class="mb-3 font-semibold text-ink-gray-9">
          {{
            draft.version
              ? t('Edit goal', 'Изменить цель')
              : t('New goal', 'Новая цель')
          }}
        </h3>
        <div class="grid gap-3 sm:grid-cols-2">
          <FormControl
            v-model="draft.scope"
            type="select"
            :label="t('Goal scope', 'Кому поставить цель')"
            :options="scopes"
            :disabled="!!draft.version || saving"
            @update:model-value="chooseScope"
          />
          <FormControl
            v-if="draft.scope !== 'Company'"
            v-model="draft.subject"
            type="select"
            :label="
              draft.scope === 'Team'
                ? t('Team', 'Команда')
                : t('Employee', 'Сотрудник')
            "
            :options="people"
            :disabled="!!draft.version || saving"
          />
          <FormControl
            v-model="draft.metric"
            type="select"
            :label="t('KPI', 'Показатель')"
            :options="metrics"
            :disabled="!!draft.version || saving"
          />
          <FormControl
            v-model="draft.target"
            inputmode="decimal"
            maxlength="16"
            :label="targetLabel"
            :disabled="saving"
            required
          />
        </div>
        <p class="mt-2 text-sm text-ink-gray-7">
          {{ report.metrics[draft.metric]?.basis }}
        </p>
        <div class="mt-3 flex flex-wrap gap-2">
          <Button variant="solid" type="submit" :loading="saving">
            {{ t('Save goal', 'Сохранить цель') }}
          </Button>
          <Button variant="ghost" :disabled="saving" @click="draft = null">
            {{ t('Cancel', 'Отмена') }}
          </Button>
        </div>
      </form>
    </div>
  </Dialog>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
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

const props = defineProps({
  initialMonth: { type: String, required: true },
  lang: { type: String, required: true },
  t: { type: Function, required: true },
})
const visible = defineModel('open', { type: Boolean, default: false })
const emit = defineEmits(['saved'])
const endpoint = 'crm.analytics.goals.'
const period = ref('Month')
const day = ref('')
const report = ref(null)
const draft = ref(null)
const error = ref('')
const notice = ref('')
const loading = ref(false)
const saving = ref(false)
let generation = 0

const periods = computed(() => [
  { value: 'Week', label: props.t('Week', 'Неделя') },
  { value: 'Month', label: props.t('Month', 'Месяц') },
  { value: 'Quarter', label: props.t('Quarter', 'Квартал') },
])
const scopes = computed(() => {
  const result = []
  if (report.value?.employees.length)
    result.push({ value: 'Employee', label: props.t('Employee', 'Сотрудник') })
  if (report.value?.teams.length)
    result.push({ value: 'Team', label: props.t('Team', 'Команда') })
  if (report.value?.company)
    result.push({
      value: 'Company',
      label: props.t('Entire company', 'Вся компания'),
    })
  return result
})
const people = computed(() =>
  (
    report.value?.[draft.value?.scope === 'Team' ? 'teams' : 'employees'] || []
  ).map(({ key, label }) => ({ value: key, label })),
)
const metrics = computed(() =>
  Object.entries(report.value?.metrics || {}).map(([value, metric]) => ({
    value,
    label: metric.label,
  })),
)
const targetLabel = computed(() => {
  const metric = report.value?.metrics[draft.value?.metric]
  const suffix =
    metric?.unit === 'currency'
      ? ' (' + report.value.currency + ')'
      : metric?.unit === 'percent'
        ? ' (%)'
        : ''
  return (
    (metric?.direction === 'max'
      ? props.t('Maximum', 'Не более')
      : props.t('Target', 'План')) + suffix
  )
})
const locale = computed(() => (props.lang === 'ru' ? 'ru-RU' : 'en-US'))

function showDate(value) {
  return new Intl.DateTimeFormat(locale.value, { timeZone: 'UTC' }).format(
    new Date(value + 'T00:00:00Z'),
  )
}
function scopeLabel(row) {
  if (row.scope === 'Company') return props.t('Entire company', 'Вся компания')
  return row.scope === 'Team'
    ? props.t('Team', 'Команда') + ' · ' + row.subject_label
    : row.subject_label
}
function format(value, row) {
  if (value === null || value === undefined) return '—'
  const unit =
    row.unit === 'percent'
      ? '%'
      : row.unit === 'currency'
        ? ' ' + row.currency
        : ''
  return formatAnalyticsNumber(value, locale.value, 2) + unit
}
function status(row) {
  if (row.currency_mismatch)
    return props.t('Currency changed', 'Изменилась валюта')
  if (report.value.future) return props.t('Scheduled', 'Запланировано')
  if (!row.complete) return props.t('Insufficient data', 'Недостаточно данных')
  if (row.direction === 'max')
    return row.met
      ? props.t('Within limit', 'В пределах цели')
      : props.t('Above limit', 'Выше цели')
  return row.met
    ? props.t('Achieved', 'Выполнено')
    : props.t('Below target', 'Ниже цели')
}

async function load() {
  const current = ++generation
  if (!visible.value || !/^\d{4}-\d{2}-\d{2}$/.test(day.value)) {
    report.value = null
    loading.value = false
    return
  }
  draft.value = null
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams({ period: period.value, day: day.value })
    const response = await fetch(
      '/api/method/' + endpoint + 'get_goals?' + params,
      { cache: 'no-store' },
    )
    if (!response.ok) throw new Error('get_goals')
    const data = (await response.json()).message
    if (current === generation) report.value = data
  } catch {
    if (current === generation) {
      report.value = null
      error.value = props.t(
        'Could not load goals. Check the date and try again.',
        'Не удалось загрузить цели. Проверьте дату и повторите.',
      )
    }
  } finally {
    if (current === generation) loading.value = false
  }
}
watch(visible, (open) => {
  if (open && !day.value) day.value = props.initialMonth + '-01'
  if (!open) {
    draft.value = null
    notice.value = ''
  }
})
watch([visible, period, day], () => {
  notice.value = ''
  load()
})

function chooseScope() {
  draft.value.subject =
    draft.value.scope === 'Company' ? null : people.value[0]?.value
}
function edit(row) {
  notice.value = ''
  error.value = ''
  draft.value = row
    ? { ...row }
    : {
        scope: scopes.value[0]?.value,
        metric: metrics.value[0]?.value,
        target: '',
      }
  if (!row) chooseScope()
  nextTick(() => document.querySelector('[data-goal-editor] input')?.focus())
}
async function save() {
  if (saving.value) return
  const input = draft.value
  if (
    !input.scope ||
    !input.metric ||
    (input.scope !== 'Company' && !input.subject)
  )
    return
  const previous = report.value.rows.find(
    (row) =>
      row.scope === input.scope &&
      row.subject === input.subject &&
      row.metric === input.metric,
  )
  if (!input.version && previous) {
    error.value = props.t(
      'This goal already exists. Edit its current value.',
      'Такая цель уже есть. Измените её текущее значение.',
    )
    return
  }
  const monthlySales =
    period.value === 'Month' &&
    input.scope === 'Employee' &&
    ['won_count', 'won_value'].includes(input.metric)
  const monthlyPair =
    monthlySales &&
    report.value.rows.find(
      (row) =>
        row.scope === 'Employee' &&
        row.subject === input.subject &&
        ['won_count', 'won_value'].includes(row.metric),
    )
  saving.value = true
  notice.value = ''
  error.value = ''
  try {
    await call(endpoint + 'save_goal', {
      period: period.value,
      day: day.value,
      scope: input.scope,
      subject: input.subject,
      metric: input.metric,
      target: String(input.target).trim().replace(',', '.'),
      currency:
        report.value.metrics[input.metric].unit === 'currency'
          ? report.value.currency
          : null,
      version: input.version || monthlyPair?.version,
      expected_viewer: report.value.viewer,
    })
    draft.value = null
    await load()
    emit('saved')
    if (report.value)
      notice.value = props.t(
        'Goal saved. Actual values recalculated.',
        'Цель сохранена. Факт пересчитан.',
      )
  } catch (failure) {
    error.value =
      failure?.exc_type === 'TimestampMismatchError'
        ? props.t(
            'The goal changed. Reopen the latest version before saving.',
            'Цель изменилась. Откройте последнюю версию перед сохранением.',
          )
        : props.t(
            'Could not save the goal. Check the value and access.',
            'Не удалось сохранить цель. Проверьте значение и доступ.',
          )
  } finally {
    saving.value = false
  }
}
</script>
