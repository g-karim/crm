<template>
  <Card :title="t('Calls and campaigns', 'Звонки и кампании')" class="min-w-0">
    <template #actions>
      <Button
        variant="ghost"
        :loading="loading"
        :disabled="stale"
        @click="load"
      >
        {{ t('Refresh', 'Обновить') }}
      </Button>
    </template>
    <p class="mb-3 text-sm text-ink-gray-7">
      {{
        t(
          'Calls are counted by date and grouped by the current campaign of the linked lead or deal.',
          'Звонки считаются по дате вызова и группируются по текущей кампании привязанного лида или сделки.',
        )
      }}
    </p>
    <p v-if="loading" role="status">{{ t('Loading…', 'Загрузка…') }}</p>
    <Alert
      v-else-if="error || stale"
      theme="yellow"
      :title="
        t(
          'Refresh analytics to see current call attribution.',
          'Обновите аналитику, чтобы увидеть актуальную привязку звонков.',
        )
      "
      :dismissible="false"
    />
    <p v-else-if="report && !report.available">
      {{
        t(
          'Call attribution is unavailable for this selection.',
          'Привязка звонков для этого среза недоступна.',
        )
      }}
    </p>
    <template v-else-if="report">
      <p class="mb-3 text-base">
        {{ t('Calls with a campaign', 'Звонков с кампанией') }}
        <strong class="tabular-nums"
          >{{ report.tagged }} / {{ report.total }}</strong
        >
      </p>
      <AnalyticsTable
        :columns="columns"
        :rows="report.rows"
        :label="t('Calls by campaign', 'Звонки по кампаниям')"
        :empty-text="
          t(
            'No accessible calls in this period.',
            'За этот период нет доступных звонков.',
          )
        "
      >
        <template #cell="{ row, column, value }">
          <div v-if="column.key === 'campaign'" class="min-w-0 break-words">
            {{ campaign(row) }}
            <p
              v-if="row.utm_source || row.utm_medium"
              class="text-sm text-ink-gray-7"
            >
              {{ [row.utm_source, row.utm_medium].filter(Boolean).join(' · ') }}
            </p>
          </div>
          <Button
            v-else-if="column.key === 'calls'"
            variant="ghost"
            :aria-label="
              t('Show calls', 'Показать звонки') + ' · ' + campaign(row)
            "
            @click="open(row)"
            >{{ value }}</Button
          >
          <span v-else>{{ value }}</span>
        </template>
      </AnalyticsTable>
    </template>
  </Card>
  <Dialog
    v-model="opened"
    :title="
      selected ? campaign(selected) : t('Campaign calls', 'Звонки кампании')
    "
    size="xl"
  >
    <p v-if="detailLoading" role="status">{{ t('Loading…', 'Загрузка…') }}</p>
    <Alert
      v-else-if="detailError"
      theme="yellow"
      :title="
        t(
          'The call selection changed. Refresh the report.',
          'Выборка звонков изменилась. Обновите отчёт.',
        )
      "
      :dismissible="false"
    />
    <template v-else-if="details">
      <ul
        class="max-h-[min(46vh,28rem)] divide-y divide-outline-gray-2 overflow-y-auto"
        :aria-label="t('Linked calls', 'Связанные звонки')"
        tabindex="0"
      >
        <li v-for="row in details.rows" :key="row.name" class="space-y-1 py-3">
          <Button variant="ghost" :route="journal(row.name)">
            {{ date(row.at) }} · {{ direction(row.direction) }}
          </Button>
          <div class="flex flex-wrap items-center gap-1">
            <Button
              v-if="row.lead"
              variant="outline"
              :route="{ name: 'Lead', params: { leadId: row.lead } }"
              >{{ t('Lead', 'Лид') }} {{ row.lead }}</Button
            >
            <Button
              v-for="deal in row.deals"
              :key="deal"
              variant="outline"
              :route="{ name: 'Deal', params: { dealId: deal } }"
              >{{ t('Deal', 'Сделка') }} {{ deal }}</Button
            >
          </div>
        </li>
      </ul>
      <div class="mt-2 flex flex-wrap gap-2">
        <Button v-if="offset > 0" @click="page(offset - 50)">{{
          t('Previous', 'Назад')
        }}</Button>
        <Button v-if="offset + 50 < details.total" @click="page(offset + 50)">{{
          t('Next', 'Далее')
        }}</Button>
        <Button @click="download">{{
          t('Download CSV', 'Скачать CSV')
        }}</Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Alert, Button, Card, Dialog } from 'frappe-ui'
import { callScopeQuery } from '@/utils/callAnalyticsRoute'
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
const opened = ref(false)
const selected = ref(null)
const detailLoading = ref(false)
const detailError = ref(false)
const details = ref(null)
const offset = ref(0)
let generation = 0
let detailGeneration = 0
const scope = computed(() =>
  Object.fromEntries(
    ['from_date', 'to_date', 'owner', 'pipeline', 'source'].map((key) => [
      key,
      props.context[key],
    ]),
  ),
)
const encoded = computed(() => JSON.stringify(scope.value))
const columns = computed(() =>
  [
    ['campaign', 'Campaign', 'Кампания'],
    ['calls', 'Calls', 'Звонки'],
    ['with_lead', 'With a lead', 'С лидом'],
    ['with_deal', 'With a deal', 'Со сделкой'],
  ].map(([key, en, ru]) => ({
    key,
    label: props.t(en, ru),
    numeric: key !== 'campaign',
  })),
)

function campaign(row) {
  if (row.state === 'campaign') return row.utm_campaign
  if (row.state === 'unlinked')
    return props.t('No lead or deal link', 'Без связи с лидом или сделкой')
  if (row.state === 'untagged')
    return props.t('No campaign tag', 'Без метки кампании')
  return props.t('Campaign unavailable', 'Кампания недоступна')
}
function direction(value) {
  if (value === 'Incoming') return props.t('Incoming', 'Входящий')
  if (value === 'Outgoing') return props.t('Outgoing', 'Исходящий')
  return props.t('Unknown direction', 'Направление неизвестно')
}
const date = (value) =>
  new Intl.DateTimeFormat(props.lang === 'ru' ? 'ru-RU' : 'en-US', {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone: props.context.timezone,
  }).format(new Date(value))

function journal(name) {
  return {
    name: 'Call Logs',
    query: {
      ...callScopeQuery(scope.value),
      call_scope: 'analytics',
      analytics_return: 'call-attribution',
      open: name,
    },
  }
}

async function api(method, params) {
  const response = await fetch(
    '/api/method/crm.analytics.call_attribution.' +
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
  detailGeneration++
  opened.value = false
  report.value = null
  error.value = false
  if (props.stale) {
    loading.value = false
    return
  }
  loading.value = true
  try {
    const result = await api('get_report', { filters: encoded.value })
    if (current === generation) report.value = result
  } catch {
    if (current === generation) error.value = true
  } finally {
    if (current === generation) loading.value = false
  }
}

function open(row) {
  selected.value = row
  opened.value = true
  page(0)
}

async function page(start) {
  const current = ++detailGeneration
  details.value = null
  detailError.value = false
  detailLoading.value = true
  offset.value = start
  try {
    const result = await api('get_details', {
      token: report.value.token,
      group: selected.value.key,
      start,
    })
    if (current === detailGeneration) details.value = result
  } catch {
    if (current === detailGeneration) detailError.value = true
  } finally {
    if (current === detailGeneration) detailLoading.value = false
  }
}

async function download() {
  const current = detailGeneration
  try {
    const result = await api('export_details', {
      token: report.value.token,
      group: selected.value.key,
    })
    if (current !== detailGeneration) return
    const href = URL.createObjectURL(
      new Blob(['\ufeff', result.csv], { type: 'text/csv;charset=utf-8' }),
    )
    const link = Object.assign(document.createElement('a'), {
      href,
      download: result.filename,
    })
    link.click()
    setTimeout(() => URL.revokeObjectURL(href), 0)
  } catch {
    if (current === detailGeneration) {
      details.value = null
      detailError.value = true
    }
  }
}

watch(opened, (value) => {
  if (!value) detailGeneration++
})
watch([encoded, () => props.stale, () => props.revision], load, {
  immediate: true,
})
onBeforeUnmount(() => {
  generation++
  detailGeneration++
})
</script>
