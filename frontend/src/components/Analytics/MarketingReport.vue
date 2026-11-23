<template>
  <Alert
    v-if="stale"
    theme="yellow"
    :title="
      t(
        'Refresh to see the current campaigns',
        'Обновите отчёт для просмотра кампаний',
      )
    "
    :dismissible="false"
  />
  <Alert
    v-else-if="loadError"
    theme="red"
    :title="t('Could not load campaigns', 'Не удалось загрузить кампании')"
    :dismissible="false"
  >
    <template #footer
      ><Button @click="load">{{ t('Retry', 'Повторить') }}</Button></template
    >
  </Alert>
  <p v-else-if="loading" role="status" class="text-ink-gray-7">
    {{ t('Loading campaigns…', 'Загрузка кампаний…') }}
  </p>
  <Alert
    v-else-if="report && !report.available"
    theme="gray"
    :title="
      report.reason === 'in_future'
        ? t('The selected period has not started', 'Период ещё не начался')
        : t('UTM fields are unavailable', 'Поля UTM недоступны')
    "
    :dismissible="false"
  />
  <Card
    v-else-if="report"
    :title="t('Campaigns and UTM', 'Кампании и UTM')"
    class="min-w-0"
  >
    <template #actions>
      <div class="flex flex-wrap justify-end gap-2">
        <Button icon-left="lucide-refresh-cw" variant="ghost" @click="load">{{
          t('Refresh', 'Обновить')
        }}</Button>
        <Button
          v-if="report.costs_enabled"
          icon-left="lucide-plus"
          @click="edit()"
          >{{ t('Record expense', 'Записать расход') }}</Button
        >
      </div>
    </template>
    <p class="mb-2 text-sm text-ink-gray-7">
      {{
        t(
          'Leads use their creation date. Wins use their closing date and recorded UTM tags.',
          'Лиды считаются по дате создания, победы по дате закрытия и сохранённым меткам UTM.',
        )
      }}
    </p>
    <p v-if="!report.costs_enabled" class="mb-3 text-sm text-ink-gray-7">
      {{
        t(
          'Company-wide expenses are visible to administrators in the unfiltered report.',
          'Расходы всей компании доступны администраторам в отчёте без разрезов.',
        )
      }}
    </p>
    <p v-else class="mb-3 text-sm text-ink-gray-7">
      {{
        t(
          'Expenses apply to the exact period and reporting currency. The ratio uses won deals and confirmed expenses.',
          'Расходы относятся к точному периоду и валюте отчёта. Отношение показывает сумму побед на единицу подтверждённых расходов.',
        )
      }}
    </p>
    <p
      v-if="report.omitted.leads || report.omitted.won"
      class="mb-3 text-sm text-ink-amber-9"
      role="status"
    >
      {{
        t(
          'Some records have restricted UTM fields.',
          'Метки UTM в части карточек недоступны.',
        )
      }}
    </p>
    <AnalyticsTable
      :rows="report.rows"
      :columns="columns"
      :label="t('Campaign results', 'Результаты кампаний')"
      :empty-text="
        t(
          'No available campaign data for this period',
          'За этот период нет доступных данных по кампаниям',
        )
      "
    >
      <template #cell="{ column, row, value }">
        <div
          v-if="column.key === 'utm_campaign'"
          class="min-w-0 break-words py-1"
        >
          <strong>{{
            value || t('Campaign unspecified', 'Кампания не указана')
          }}</strong>
          <p
            v-if="row.utm_source || row.utm_medium"
            class="mt-1 text-sm text-ink-gray-7"
          >
            {{ [row.utm_source, row.utm_medium].filter(Boolean).join(' · ') }}
          </p>
        </div>
        <template v-else-if="column.key === 'leads' || column.key === 'won'">
          <Button
            v-if="value"
            variant="ghost"
            :aria-label="
              (column.key === 'leads'
                ? t('Open leads', 'Открыть лиды')
                : t('Open won deals', 'Открыть победы')) +
              ' · ' +
              (row.utm_campaign || t('Unspecified', 'Не указано'))
            "
            @click="openDetail(row, column.key)"
            >{{ value }}</Button
          >
          <span v-else>{{ value ?? '—' }}</span>
        </template>
        <div v-else-if="column.key === 'won_value'">
          <span>{{ format(value) }}</span>
          <small
            v-if="value != null && !row.won_value_complete"
            class="block text-ink-amber-9"
          >
            {{ t('known part', 'известная часть') }}
          </small>
        </div>
        <Button
          v-else-if="
            column.key === 'cost' && report.costs_enabled && row.utm_campaign
          "
          variant="ghost"
          :aria-label="
            t('Edit expense', 'Указать расход') + ' · ' + row.utm_campaign
          "
          @click="edit(row)"
          >{{ value === null ? t('Enter', 'Указать') : format(value) }}</Button
        >
        <span v-else>{{ value == null ? '—' : '×' + format(value) }}</span>
      </template>
    </AnalyticsTable>
  </Card>

  <Dialog
    v-model="costOpen"
    :title="t('Confirmed campaign expense', 'Подтверждённый расход кампании')"
    size="xl"
    :dismissible="!saving"
    :show-close-button="!saving"
  >
    <form v-if="draft" class="space-y-3" @submit.prevent="save">
      <p class="text-sm text-ink-gray-7">
        {{ draft.from_date }} — {{ draft.to_date }} · {{ draft.currency }}
      </p>
      <div class="grid gap-3 sm:grid-cols-2">
        <FormControl
          v-model="draft.utm_campaign"
          :label="t('UTM campaign', 'UTM-кампания')"
          required
          maxlength="120"
          :disabled="draft.fixed || saving"
        />
        <FormControl
          v-model="draft.utm_source"
          :label="t('UTM source', 'UTM-источник')"
          maxlength="120"
          :disabled="draft.fixed || saving"
        />
        <FormControl
          v-model="draft.utm_medium"
          :label="t('UTM medium', 'UTM-канал')"
          maxlength="120"
          :disabled="draft.fixed || saving"
        />
        <FormControl
          v-model="draft.confirmed_amount"
          :label="t('Expense amount', 'Сумма расхода')"
          inputmode="decimal"
          required
          :disabled="saving"
        />
      </div>
      <FormControl
        v-model="draft.source_reference"
        :label="
          t(
            'Confirming source reference',
            'Ссылка или номер подтверждающего документа',
          )
        "
        maxlength="120"
        required
        :disabled="saving"
      />
      <Alert
        v-if="saveError"
        theme="red"
        :title="saveError"
        :dismissible="false"
      />
      <Button type="submit" variant="solid" :loading="saving">{{
        t('Save expense', 'Сохранить расход')
      }}</Button>
    </form>
  </Dialog>

  <Dialog v-model="detailOpen" :title="detailTitle" size="xl">
    <p v-if="detailLoading" role="status">
      {{ t('Loading records…', 'Загрузка карточек…') }}
    </p>
    <Alert
      v-else-if="detailError"
      theme="yellow"
      :title="
        t(
          'Refresh the campaign report and try again',
          'Обновите отчёт и откройте карточки ещё раз',
        )
      "
      :dismissible="false"
    >
      <template #footer
        ><Button @click="load">{{ t('Refresh', 'Обновить') }}</Button></template
      >
    </Alert>
    <template v-else-if="detail">
      <p>{{ t('Records', 'Карточек') }} · {{ detail.total }}</p>
      <ul class="my-3 grid gap-2">
        <li v-for="row in detail.rows" :key="row.name">
          <RouterLink :to="recordRoute(row)" class="underline">{{
            row.title || row.name
          }}</RouterLink>
        </li>
      </ul>
      <div class="flex flex-wrap gap-2">
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
import { Alert, Button, Card, Dialog, FormControl, call } from 'frappe-ui'
import { formatAnalyticsNumber } from '@/utils/analyticsNumbers'
import AnalyticsTable from './AnalyticsTable.vue'

const props = defineProps({
  context: { type: Object, required: true },
  revision: { type: String, required: true },
  t: { type: Function, required: true },
  lang: { type: String, required: true },
  stale: Boolean,
})
const endpoint = 'crm.analytics.marketing.'
const report = ref(null)
const loading = ref(false)
const loadError = ref(false)
const costOpen = ref(false)
const draft = ref(null)
const saving = ref(false)
const saveError = ref('')
const detailOpen = ref(false)
const detail = ref(null)
const selection = ref(null)
const detailError = ref(false)
const detailLoading = ref(false)
const offset = ref(0)
let generation = 0
let detailGeneration = 0

const col = (key, en, ru, numeric = true) => ({
  key,
  label: props.t(en, ru),
  numeric,
})
const columns = computed(() => [
  col('utm_campaign', 'Campaign', 'Кампания', false),
  col('leads', 'Leads', 'Лиды'),
  col('won', 'Won', 'Победы'),
  {
    ...col('won_value', 'Won value', 'Сумма побед'),
    label: props.t('Won value', 'Сумма побед') + ', ' + props.context.currency,
  },
  ...(report.value?.costs_enabled
    ? [
        {
          ...col('cost', 'Expense', 'Расходы'),
          label: props.t('Expense', 'Расходы') + ', ' + props.context.currency,
        },
        col('revenue_to_cost', 'Wins / expense', 'Победы / расходы'),
      ]
    : []),
])
const encode = computed(() =>
  JSON.stringify(
    Object.fromEntries(
      ['from_date', 'to_date', 'owner', 'pipeline', 'source']
        .map((key) => [key, props.context[key]])
        .filter(([, value]) => value),
    ),
  ),
)
const detailTitle = computed(() =>
  selection.value?.kind === 'leads'
    ? props.t('Campaign leads', 'Лиды кампании')
    : props.t('Won deals for campaign', 'Победы кампании'),
)
const format = (value) =>
  formatAnalyticsNumber(value, props.lang === 'ru' ? 'ru-RU' : 'en-US')
function recordRoute(row) {
  return selection.value.kind === 'leads'
    ? { name: 'Lead', params: { leadId: row.name } }
    : { name: 'Deal', params: { dealId: row.name } }
}
async function api(method, params) {
  const response = await fetch(
    '/api/method/' + endpoint + method + '?' + new URLSearchParams(params),
    { cache: 'no-store' },
  )
  if (!response.ok) throw new Error(method)
  return (await response.json()).message
}
async function load(background = false) {
  const quiet = background === true
  const current = ++generation
  if (!quiet) {
    detailOpen.value = false
    report.value = null
  }
  loadError.value = false
  loading.value = !quiet && !props.stale
  if (props.stale) return
  try {
    const result = await api('get_report', { filters: encode.value })
    if (current === generation) report.value = result
  } catch {
    if (current === generation) loadError.value = true
  } finally {
    if (current === generation) loading.value = false
  }
}
watch([encode, () => props.revision, () => props.stale], load, {
  immediate: true,
})
watch(
  () => props.context.as_of,
  () => {
    if (!props.stale && !loading.value && !costOpen.value && !detailOpen.value)
      load(true)
  },
)
watch(detailOpen, (open) => {
  if (!open) detailGeneration++
})
onBeforeUnmount(() => {
  generation++
  detailGeneration++
})

function edit(row) {
  const context = report.value.context
  draft.value = {
    from_date: context.from_date,
    to_date: context.to_date,
    currency: context.currency,
    expected_viewer: context.viewer,
    expected_version: row?.cost_version,
    utm_source: row?.utm_source || '',
    utm_medium: row?.utm_medium || '',
    utm_campaign: row?.utm_campaign || '',
    confirmed_amount: row?.cost == null ? '' : String(row.cost),
    source_reference: row?.source_reference || '',
    fixed: Boolean(row),
  }
  saveError.value = ''
  costOpen.value = true
}
async function save() {
  if (saving.value || !draft.value) return
  const values = { ...draft.value }
  delete values.fixed
  saving.value = true
  saveError.value = ''
  try {
    await call(endpoint + 'save_cost', {
      ...values,
      confirmed_amount: String(values.confirmed_amount)
        .trim()
        .replace(',', '.'),
    })
    costOpen.value = false
    draft.value = null
    await load()
  } catch (failure) {
    saveError.value =
      failure?.exc_type === 'TimestampMismatchError'
        ? props.t(
            'The expense has changed. Reopen the latest record.',
            'Расход изменился. Откройте текущую запись.',
          )
        : props.t(
            'Could not save the expense. Check its period and amount.',
            'Не удалось сохранить расход. Проверьте его период и сумму.',
          )
  } finally {
    saving.value = false
  }
}
function openDetail(row, kind) {
  selection.value = { group: row.key, kind }
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
      ...selection.value,
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
    const result = await api('export_details', {
      token: report.value.token,
      ...selection.value,
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
