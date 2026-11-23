<template>
  <Alert
    v-if="stale"
    theme="yellow"
    :title="
      t('Refresh to see current reconciliation', 'Обновите отчёт для сверки')
    "
    :dismissible="false"
  />
  <Alert
    v-else-if="loadError"
    theme="red"
    :title="t('Could not load reconciliation', 'Не удалось загрузить сверку')"
    :dismissible="false"
  >
    <template #footer
      ><Button @click="load">{{ t('Retry', 'Повторить') }}</Button></template
    >
  </Alert>
  <p v-else-if="loading" role="status">
    {{ t('Loading reconciliation…', 'Загрузка сверки…') }}
  </p>
  <div v-else-if="report" class="grid min-w-0 gap-3">
    <Card
      :title="t('ERP documents and payments', 'Документы и оплаты ERP')"
      class="min-w-0"
    >
      <template #actions
        ><Button icon-left="lucide-refresh-cw" @click="load">{{
          t('Refresh', 'Обновить')
        }}</Button></template
      >
      <Alert
        v-if="!report.erp.available"
        theme="gray"
        :title="reason(report.erp.reason)"
        :dismissible="false"
      />
      <template v-else>
        <p class="mb-3 text-sm text-ink-gray-7">
          {{
            t(
              'Posted documents are linked through the quotation, sales order and invoice. Payments use allocations recorded in Payment Entry.',
              'Проведённые документы связываются по цепочке предложения, заказа и счёта. Оплаты учитываются по распределениям из документов Payment Entry.',
            )
          }}
        </p>
        <div class="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <Button
            v-for="item in erpMetrics"
            :key="item.key"
            variant="outline"
            class="!h-auto min-w-0 !justify-start !py-3"
            :disabled="!item.metric.rows"
            @click="inspect('erp', item.key, item.label)"
          >
            <span class="min-w-0 whitespace-normal text-left">
              <span class="block text-sm text-ink-gray-7">{{
                item.label
              }}</span>
              <strong class="block text-lg tabular-nums text-ink-gray-9">
                {{ format(item.metric.amount)
                }}{{
                  item.metric.amount == null
                    ? ''
                    : ' ' + report.context.currency
                }}
              </strong>
              <small class="block text-ink-gray-7"
                >{{ item.metric.documents }} ·
                {{ t('documents', 'документов') }}</small
              >
              <small
                v-if="item.metric.unknown_amounts"
                class="block text-ink-amber-9"
                >{{
                  t('Some amounts are unavailable', 'Часть сумм недоступна')
                }}</small
              >
            </span>
          </Button>
        </div>
        <p
          v-if="!erpMetrics.some((item) => item.metric.documents)"
          class="mt-3 text-sm text-ink-gray-7"
        >
          {{
            t(
              'There are no linked posted documents in this period.',
              'За период нет связанных проведённых документов.',
            )
          }}
        </p>
        <Alert
          v-if="report.erp.ambiguous_invoices"
          theme="yellow"
          :dismissible="false"
          class="mt-3"
          :title="
            t(
              'Invoices with incomplete or mixed originating links',
              'Счета с неполной или смешанной цепочкой',
            ) +
            ' · ' +
            report.erp.ambiguous_invoices
          "
        />
      </template>
    </Card>
    <Card
      :title="t('Products in won CRM deals', 'Товары в выигранных сделках CRM')"
      class="min-w-0"
    >
      <p v-if="!report.products.available" class="text-ink-gray-7">
        {{
          t(
            'CRM product lines are unavailable.',
            'Строки товаров CRM недоступны.',
          )
        }}
      </p>
      <AnalyticsTable
        v-else
        :rows="report.products.rows"
        :columns="productColumns"
        :label="t('Product lines in wins', 'Товары в победах')"
        :empty-text="
          t(
            'No product lines in wins during this period',
            'За период в выигранных сделках нет строк товаров',
          )
        "
      >
        <template #cell="{ column, row, value }">
          <Button
            v-if="column.key === 'label'"
            variant="ghost"
            @click="inspect('products', row.key, row.label)"
            >{{ value }}</Button
          >
          <span v-else-if="column.key === 'deal_count'">{{ value }}</span>
          <span v-else
            >{{ format(value)
            }}<small v-if="value != null && !row[column.key + '_complete']">
              · {{ t('known part', 'известная часть') }}</small
            ></span
          >
        </template>
      </AnalyticsTable>
    </Card>
  </div>
  <Dialog v-model="detailOpen" :title="detailTitle" size="4xl">
    <p v-if="detailLoading" role="status">
      {{ t('Loading records…', 'Загрузка строк…') }}
    </p>
    <Alert
      v-else-if="detailError"
      theme="yellow"
      :title="
        t(
          'The document slice changed. Refresh the report.',
          'Документы изменились. Обновите сверку.',
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
        :rows="detail.rows"
        :columns="detailColumns"
        row-key="name"
        :label="t('Records used for reconciliation', 'Строки сверки')"
      >
        <template #cell="{ column, row, value }">
          <a
            v-if="column.key === 'document'"
            :href="documentUrl(row)"
            target="_blank"
            rel="noopener noreferrer"
            class="underline"
            >{{ value }}</a
          >
          <RouterLink
            v-else-if="column.key === 'deal'"
            :to="{ name: 'Deal', params: { dealId: row.deal } }"
            class="underline"
            >{{ row.title || row.deal }}</RouterLink
          >
          <span v-else>{{
            column.key === 'amount' || column.key === 'quantity'
              ? format(value)
              : value
          }}</span>
        </template>
      </AnalyticsTable>
      <div class="mt-3 flex flex-wrap gap-2">
        <Button v-if="offset" @click="readDetail(offset - 50)">{{
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
import { formatAnalyticsNumber } from '@/utils/analyticsNumbers'
import AnalyticsTable from './AnalyticsTable.vue'

const props = defineProps({
  context: { type: Object, required: true },
  revision: { type: String, required: true },
  t: { type: Function, required: true },
  lang: { type: String, required: true },
  stale: Boolean,
})
const endpoint = 'crm.analytics.erp_reconciliation.'
const report = ref(null)
const loading = ref(false)
const loadError = ref(false)
const detailOpen = ref(false)
const detailTitle = ref('')
const detailsParams = ref(null)
const detail = ref(null)
const detailLoading = ref(false)
const detailError = ref(false)
const offset = ref(0)
let generation = 0
let detailGeneration = 0
const format = (value) =>
  formatAnalyticsNumber(value, props.lang === 'ru' ? 'ru-RU' : 'en-US')
const col = (key, en, ru, numeric = false) => ({
  key,
  label: props.t(en, ru),
  numeric,
})
const productColumns = computed(() => [
  col('label', 'Product', 'Товар'),
  col('deal_count', 'Won deals', 'Победы', true),
  col('quantity', 'Quantity', 'Количество', true),
  col('amount', 'Value in CRM', 'Сумма в CRM', true),
])
const detailColumns = computed(() =>
  detailsParams.value?.source === 'products'
    ? [
        col('deal', 'Deal', 'Сделка'),
        col('quantity', 'Quantity', 'Количество', true),
        col('amount', 'Value', 'Сумма', true),
      ]
    : [
        col('document', 'Document', 'Документ'),
        col('deal', 'Deal', 'Сделка'),
        col('date', 'Posting date', 'Дата проведения'),
        col('amount', 'Value', 'Сумма', true),
      ],
)
const filters = computed(() =>
  JSON.stringify(
    Object.fromEntries(
      ['from_date', 'to_date', 'owner', 'pipeline', 'source']
        .map((key) => [key, props.context[key]])
        .filter(([, value]) => value),
    ),
  ),
)
const erpMetrics = computed(() =>
  [
    col('invoices', 'Invoiced', 'Выставлено по счетам'),
    col('receipts', 'Received through Payment Entry', 'Поступило по оплатам'),
    col('credit_notes', 'Credit notes', 'Кредит-ноты'),
    col('cash_refunds', 'Cash refunds', 'Возвращено деньгами'),
  ].map((item) => ({ ...item, metric: report.value?.erp.metrics?.[item.key] })),
)
function reason(key) {
  const messages = {
    local_erp_unavailable: [
      'Local ERPNext is unavailable',
      'Локальный ERPNext недоступен',
    ],
    remote_erp_unavailable: [
      'Remote ERP has no verified data source',
      'Источник данных внешней ERP не подтверждён',
    ],
    missing_quotation_links: [
      'The ERP link from quotations to CRM is unavailable',
      'Связь предложений ERP со сделками CRM недоступна',
    ],
    source_permissions: [
      'ERP source documents are unavailable with your permissions',
      'Документы ERP недоступны с вашими правами',
    ],
    in_future: ['The selected period has not started', 'Период ещё не начался'],
  }
  return props.t(...(messages[key] || messages.local_erp_unavailable))
}
function documentUrl(row) {
  const base =
    row.doctype === 'Sales Invoice'
      ? '/app/sales-invoice/'
      : '/app/payment-entry/'
  return base + encodeURIComponent(row.document)
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
    const result = await api('get_report', { filters: filters.value })
    if (current === generation) report.value = result
  } catch {
    if (current === generation) loadError.value = true
  } finally {
    if (current === generation) loading.value = false
  }
}
watch([filters, () => props.revision, () => props.stale], load, {
  immediate: true,
})
watch(
  () => props.context.as_of,
  () => {
    if (!props.stale && !loading.value && !detailOpen.value) load(true)
  },
)
watch(detailOpen, (open) => {
  if (!open) detailGeneration++
})
onBeforeUnmount(() => {
  generation++
  detailGeneration++
})

function inspect(source, group, label) {
  detailsParams.value = { source, group }
  detailTitle.value = label
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
      ...detailsParams.value,
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
      ...detailsParams.value,
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
