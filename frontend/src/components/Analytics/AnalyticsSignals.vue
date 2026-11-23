<template>
  <Dialog
    v-model="open"
    :title="t('Analytics signals', 'Сигналы аналитики')"
    size="xl"
    :dismissible="!saving"
    :show-close-button="!saving"
  >
    <div class="flex flex-col gap-3">
      <p class="text-sm text-ink-gray-7">
        {{
          t(
            'Background checks appear in the CRM inbox. Rules are also checked when you open this window.',
            'Новые сигналы из фоновых проверок появляются здесь. Правила также проверяются при открытии окна.',
          )
        }}
      </p>
      <Alert v-if="error" theme="red" :title="error" :dismissible="false" />
      <p v-if="notice" role="status" class="text-sm text-ink-green-8">
        {{ notice }}
      </p>
      <p v-if="loading && !data" role="status">
        {{ t('Loading…', 'Загрузка…') }}
      </p>
      <template v-if="data">
        <Card
          v-if="data.inbox?.length"
          :title="t('New signals', 'Новые сигналы')"
        >
          <ul class="divide-y divide-outline-gray-2">
            <li
              v-for="entry in data.inbox"
              :key="entry.name"
              class="flex flex-wrap items-center justify-between gap-2 py-2"
            >
              <div>
                <p class="font-medium text-ink-gray-9">
                  {{ label(entry.metric) }}
                </p>
                <time
                  :datetime="entry.arrived_at"
                  class="text-sm text-ink-gray-7"
                  >{{ signalTime(entry.arrived_at) }}</time
                >
              </div>
              <Button
                variant="ghost"
                :loading="acknowledging === entry.name"
                :disabled="!!acknowledging"
                @click="ack(entry.name)"
              >
                {{ t('Mark as read', 'Отметить прочитанным') }}
              </Button>
            </li>
          </ul>
        </Card>
        <Card
          v-for="row in data.rows"
          :key="row.metric"
          :title="label(row.metric)"
          class="min-w-0"
        >
          <template #actions>
            <Button
              icon="lucide-pencil"
              variant="ghost"
              :label="t('Configure', 'Настроить') + ' · ' + label(row.metric)"
              :disabled="saving || !!draft"
              @click="edit(row)"
            />
          </template>
          <p class="text-sm text-ink-gray-7">{{ basis(row.metric) }}</p>
          <div class="mt-3 flex flex-wrap items-center gap-2">
            <Badge
              :theme="
                row.active ? 'orange' : row.active === false ? 'green' : 'gray'
              "
            >
              {{ status(row) }}
            </Badge>
            <span v-if="row.enabled" class="text-sm text-ink-gray-8">
              {{ t('Threshold', 'Порог') }} {{ row.threshold }}{{ suffix(row) }}
            </span>
            <span
              v-if="row.actual !== null"
              class="text-sm font-medium text-ink-gray-9"
            >
              {{ t('Actual', 'Факт') }} {{ format(row.actual)
              }}{{ suffix(row) }}
            </span>
            <Button
              v-if="row.active"
              variant="ghost"
              :route="{
                name: 'Dashboard',
                query:
                  row.destination === 'calls'
                    ? { section: 'calls', call_view: 'sla' }
                    : { section: 'managers' },
              }"
              @click="open = false"
              >{{ t('View details', 'Открыть раздел') }}</Button
            >
          </div>
          <form
            v-if="draft?.metric === row.metric"
            class="mt-4 space-y-3"
            @submit.prevent="save"
          >
            <FormControl
              v-model="draft.threshold"
              type="number"
              :min="1"
              :max="row.upper"
              step="1"
              :label="t('Signal threshold', 'Порог сигнала')"
              :disabled="saving"
              required
            />
            <Checkbox
              v-model="draft.enabled"
              :label="t('Monitor this metric', 'Следить за показателем')"
              :disabled="saving"
            />
            <div class="flex flex-wrap gap-2">
              <Button type="submit" variant="solid" :loading="saving">{{
                t('Save rule', 'Сохранить правило')
              }}</Button>
              <Button
                variant="ghost"
                :disabled="saving"
                @click="draft = null"
                >{{ t('Cancel', 'Отмена') }}</Button
              >
            </div>
          </form>
        </Card>
      </template>
      <Button
        class="self-start"
        icon-left="lucide-refresh-cw"
        :loading="loading"
        :disabled="!!draft || saving"
        @click="load"
      >
        {{ t('Refresh', 'Обновить') }}
      </Button>
    </div>
  </Dialog>
</template>

<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Dialog,
  FormControl,
  call,
} from 'frappe-ui'
import { formatAnalyticsNumber } from '@/utils/analyticsNumbers'

const props = defineProps({
  t: { type: Function, required: true },
  lang: { type: String, required: true },
})
const open = defineModel('open', { type: Boolean, default: false })
const data = ref(null)
const draft = ref(null)
const error = ref('')
const notice = ref('')
const loading = ref(false)
const saving = ref(false)
const acknowledging = ref('')
const endpoint = 'crm.analytics.signals.'
const signalTime = (value) =>
  new Intl.DateTimeFormat(props.lang === 'ru' ? 'ru-RU' : 'en-US', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(new Date(value))
let refreshTimer
let request = 0

const names = {
  calls_overdue: ['Overdue callbacks', 'Просроченные перезвоны'],
  tasks_overdue: ['Overdue deal tasks', 'Просроченные задачи по сделкам'],
  monthly_progress: [
    'Lowest monthly goal progress',
    'Самое низкое выполнение месячной цели',
  ],
}
const bases = {
  calls_overdue: [
    'Past 30 days, after the callback deadline',
    'За 30 дней, после истечения срока перезвона',
  ],
  tasks_overdue: [
    'Current overdue tasks on readable deals',
    'Текущие просроченные задачи по доступным сделкам',
  ],
  monthly_progress: [
    'Current month, goals with enough data to calculate progress',
    'Текущий месяц, цели с достаточными данными для расчёта',
  ],
}
const label = (metric) => props.t(...names[metric])
const basis = (metric) => props.t(...bases[metric])
const suffix = (row) => (row.metric === 'monthly_progress' ? '%' : '')
const format = (value) =>
  formatAnalyticsNumber(value, props.lang === 'ru' ? 'ru-RU' : 'en-US')
function status(row) {
  if (!row.enabled) return props.t('Off', 'Выключено')
  if (row.active === null)
    return props.t('Insufficient data', 'Недостаточно данных')
  return row.active
    ? props.t('Needs attention', 'Требует внимания')
    : props.t('Within threshold', 'В пределах порога')
}
function edit(row) {
  notice.value = ''
  error.value = ''
  draft.value = { ...row }
}
async function load() {
  if (!open.value || loading.value) return
  const current = ++request
  loading.value = true
  error.value = ''
  try {
    const response = await fetch('/api/method/' + endpoint + 'get_signals', {
      cache: 'no-store',
    })
    if (!response.ok) throw new Error('get_signals')
    const report = (await response.json()).message
    if (current === request) data.value = report
  } catch {
    if (current === request) {
      data.value = null
      error.value = props.t(
        'Could not load signals.',
        'Не удалось загрузить сигналы.',
      )
    }
  } finally {
    if (current === request) loading.value = false
  }
}
async function save() {
  if (!draft.value || saving.value) return
  const rule = draft.value
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    await call(endpoint + 'save_monitor', {
      metric: rule.metric,
      threshold: Number(rule.threshold),
      enabled: rule.enabled,
      version: rule.version,
      expected_viewer: data.value.viewer,
    })
    draft.value = null
    await load()
    if (data.value) notice.value = props.t('Rule saved.', 'Правило сохранено.')
  } catch (failure) {
    error.value =
      failure?.exc_type === 'TimestampMismatchError'
        ? props.t(
            'The rule changed. Reopen its current settings.',
            'Правило изменилось. Откройте текущие настройки.',
          )
        : props.t('Could not save the rule.', 'Не удалось сохранить правило.')
  } finally {
    saving.value = false
  }
}
async function ack(name) {
  if (acknowledging.value || !data.value) return
  const viewer = data.value.viewer
  acknowledging.value = name
  try {
    await call('crm.analytics.signal_delivery.acknowledge', {
      name,
      expected_viewer: viewer,
    })
    if (data.value?.viewer === viewer)
      data.value.inbox = data.value.inbox.filter((item) => item.name !== name)
  } catch {
    error.value = props.t(
      'Could not mark the signal as read.',
      'Не удалось отметить сигнал прочитанным.',
    )
  } finally {
    acknowledging.value = ''
  }
}
watch(open, (value) => {
  if (value) load()
  else {
    request++
    data.value = null
    loading.value = false
    draft.value = null
    error.value = ''
    notice.value = ''
  }
})
onMounted(() => {
  refreshTimer = setInterval(() => {
    if (!document.hidden && !draft.value && !saving.value) load()
  }, 60_000)
})
onUnmounted(() => {
  clearInterval(refreshTimer)
  request++
})
</script>
