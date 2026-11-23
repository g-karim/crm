<template>
  <Alert
    v-if="stale"
    theme="yellow"
    :title="
      t(
        'Refresh the report to see current movements',
        'Обновите отчёт, чтобы увидеть актуальное движение',
      )
    "
    :dismissible="false"
  />
  <Alert
    v-else-if="error"
    theme="red"
    :title="
      t(
        'Could not load pipeline movements',
        'Не удалось загрузить движение сделок',
      )
    "
    :dismissible="false"
  >
    <template #footer
      ><Button @click="load">{{ t('Retry', 'Повторить') }}</Button></template
    >
  </Alert>
  <p v-else-if="loading" role="status" class="text-ink-gray-7">
    {{ t('Loading pipeline movements…', 'Загрузка движения сделок…') }}
  </p>
  <Alert
    v-else-if="report && !report.available"
    theme="gray"
    :title="
      report.reason === 'in_future'
        ? t(
            'The selected period has not started',
            'Выбранный период ещё не начался',
          )
        : t(
            'Recorded history is unavailable',
            'Подтверждённая история недоступна',
          )
    "
    :dismissible="false"
  />
  <div v-else-if="report" class="grid gap-3">
    <Card
      :title="
        t('Transitions in the selected period', 'Переходы за выбранный период')
      "
    >
      <template #actions>
        <Button variant="ghost" icon-left="lucide-refresh-cw" @click="load">{{
          t('Refresh', 'Обновить')
        }}</Button>
      </template>
      <p class="mb-3 text-sm text-ink-gray-7">
        {{
          t(
            'A deal can move along the same pair of stages several times. Time refers to the stage the deal left.',
            'Сделка может пройти один переход несколько раз. Время считается для этапа, с которого сделка ушла.',
          )
        }}
      </p>
      <AnalyticsTable
        :columns="transitionColumns"
        :rows="report.rows"
        :label="t('Confirmed stage transitions', 'Подтверждённые переходы')"
        :empty-text="
          t(
            'No confirmed transitions in this period',
            'За этот период нет подтверждённых переходов',
          )
        "
      >
        <template #cell="{ row, column, value }">
          <Button
            v-if="column.key === 'moves'"
            variant="ghost"
            :aria-label="
              t('Open transitions', 'Открыть переходы') +
              ' · ' +
              row.from_label +
              ' → ' +
              row.to_label
            "
            @click="openDetails(row)"
          >
            {{ value }}
          </Button>
          <span
            v-else-if="column.key === 'median_days'"
            :title="
              t('Known intervals', 'Известные интервалы') +
              ' · ' +
              row.duration_count
            "
          >
            {{ value ?? '—' }}
          </span>
          <span v-else>{{ value }}</span>
        </template>
      </AnalyticsTable>
    </Card>
    <Card
      :title="
        t(
          'Deals by stage at the start and end',
          'Сделки по этапам на начало и конец периода',
        )
      "
    >
      <p class="mb-3 text-sm text-ink-gray-7">
        {{ t('History confirmed for', 'История подтверждена для') }}
        {{ report.known }} {{ t('of', 'из') }} {{ report.eligible }}
        {{ t('deals.', 'сделок.') }}
        {{
          t(
            'The table counts those deals. Filters use current deal attributes.',
            'В таблице учтены эти сделки. Фильтры используют текущие поля карточек.',
          )
        }}
      </p>
      <AnalyticsTable
        :columns="stageColumns"
        :rows="report.stages"
        :label="t('Stage changes', 'Изменение по этапам')"
        :empty-text="
          t(
            'No deals with complete history for this period',
            'В этом периоде нет сделок с полной историей',
          )
        "
      />
    </Card>
  </div>

  <Dialog v-model="detailOpen" :title="detailTitle" size="4xl">
    <p v-if="detailLoading" role="status">{{ t('Loading…', 'Загрузка…') }}</p>
    <Alert
      v-else-if="detailError"
      theme="yellow"
      :title="
        t(
          'The figures changed. Refresh the movement report.',
          'Данные изменились. Обновите отчёт о переходах.',
        )
      "
      :dismissible="false"
    >
      <template #footer
        ><Button @click="load">{{ t('Refresh', 'Обновить') }}</Button></template
      >
    </Alert>
    <template v-else-if="detail">
      <AnalyticsTable
        :columns="detailColumns"
        :rows="detail.rows"
        row-key="name"
        :label="t('Recorded transitions', 'Записи о переходах')"
      >
        <template #cell="{ row, column, value }">
          <RouterLink
            v-if="column.key === 'title'"
            :to="{ name: 'Deal', params: { dealId: row.deal } }"
            class="underline"
          >
            {{ value }}
          </RouterLink>
          <span v-else-if="column.key === 'at'">{{ date(value) }}</span>
          <span v-else>{{ value }}</span>
        </template>
      </AnalyticsTable>
      <div class="mt-3 flex flex-wrap gap-2">
        <Button v-if="offset > 0" @click="readDetail(offset - 50)">{{
          t('Previous', 'Назад')
        }}</Button>
        <Button
          v-if="offset + 50 < detail.total"
          @click="readDetail(offset + 50)"
          >{{ t('Next', 'Далее') }}</Button
        >
        <Button icon-left="lucide-download" @click="download">{{
          t('Download CSV', 'Скачать CSV')
        }}</Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Alert, Button, Card, Dialog } from 'frappe-ui'
import AnalyticsTable from './AnalyticsTable.vue'

const props = defineProps({
  context: { type: Object, required: true },
  revision: { type: String, required: true },
  t: { type: Function, required: true },
  lang: { type: String, required: true },
  stale: Boolean,
})
const report = ref(null)
const loading = ref(false)
const error = ref(false)
const detail = ref(null)
const detailOpen = ref(false)
const detailLoading = ref(false)
const detailError = ref(false)
const offset = ref(0)
const selected = ref(null)
let generation = 0
let detailGeneration = 0

const col = (key, en, ru, numeric = false) => ({
  key,
  label: props.t(en, ru),
  numeric,
})
const transitionColumns = computed(() => [
  col('from_label', 'From', 'С этапа'),
  col('to_label', 'To', 'На этап'),
  col('moves', 'Moves', 'Переходы', true),
  col('deals', 'Deals', 'Сделки', true),
  col('median_days', 'Median, days', 'Медиана, дн.', true),
])
const stageColumns = computed(() => [
  col('label', 'Stage', 'Этап'),
  col('start', 'Start', 'В начале', true),
  col('end', 'End', 'На конец', true),
  col('change', 'Change', 'Изменение', true),
])
const detailColumns = computed(() => [
  col('title', 'Deal', 'Сделка'),
  col('at', 'Time', 'Дата и время'),
  col('duration_seconds', 'Stage time, sec.', 'На этапе, сек.', true),
])
const detailTitle = computed(() =>
  selected.value
    ? selected.value.from_label + ' → ' + selected.value.to_label
    : props.t('Transition details', 'Детали переходов'),
)
const filters = computed(() =>
  JSON.stringify(
    Object.fromEntries(
      ['from_date', 'to_date', 'owner', 'source', 'pipeline']
        .map((key) => [key, props.context[key]])
        .filter(([, value]) => value),
    ),
  ),
)
function date(value) {
  return new Intl.DateTimeFormat(props.lang === 'ru' ? 'ru-RU' : 'en-US', {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone: props.context.timezone,
  }).format(new Date(value))
}
async function api(method, params) {
  const response = await fetch(
    '/api/method/crm.analytics.pipeline_movement.' +
      method +
      '?' +
      new URLSearchParams(params),
    { cache: 'no-store' },
  )
  if (!response.ok) throw new Error(method)
  return (await response.json()).message
}
async function load() {
  const current = ++generation
  detailOpen.value = false
  report.value = null
  if (props.stale) {
    loading.value = false
    return
  }
  loading.value = true
  error.value = false
  try {
    const data = await api('get_movement', { filters: filters.value })
    if (current === generation) report.value = data
  } catch {
    if (current === generation) error.value = true
  } finally {
    if (current === generation) loading.value = false
  }
}
watch([filters, () => props.revision, () => props.stale], load, {
  immediate: true,
})
watch(detailOpen, (open) => {
  if (!open) detailGeneration++
})
onBeforeUnmount(() => {
  generation++
  detailGeneration++
})

function openDetails(row) {
  selected.value = row
  detailOpen.value = true
  readDetail(0)
}
async function readDetail(start) {
  const current = ++detailGeneration
  detailLoading.value = true
  detailError.value = false
  try {
    const result = await api('get_details', {
      token: report.value.token,
      group: selected.value.key,
      start,
    })
    if (current === detailGeneration) {
      detail.value = result
      offset.value = start
    }
  } catch {
    if (current === detailGeneration) detailError.value = true
  } finally {
    if (current === detailGeneration) detailLoading.value = false
  }
}
async function download() {
  const current = detailGeneration
  try {
    const result = await api('export', {
      token: report.value.token,
      group: selected.value.key,
    })
    if (current !== detailGeneration) return
    const url = URL.createObjectURL(
      new Blob(['\ufeff', result.csv], { type: 'text/csv;charset=utf-8' }),
    )
    const link = document.createElement('a')
    link.href = url
    link.download = result.filename
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 0)
  } catch {
    if (current === detailGeneration) detailError.value = true
  }
}
</script>
