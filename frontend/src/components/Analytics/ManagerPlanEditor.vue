<template>
  <Dialog
    :model-value="open"
    :title="t('Monthly sales plan', 'План продаж на месяц')"
    size="lg"
    :dismissible="!saving"
    :show-close-button="!saving"
    @update:model-value="close"
  >
    <form
      id="manager-plan-form"
      class="plan-editor flex flex-col gap-4"
      @submit.prevent="save"
    >
      <div class="plan-editor-month">
        <Icon name="lucide-calendar-days" class="size-4" />
        {{ monthLabel }}
      </div>
      <div
        v-if="loading"
        class="flex items-center gap-2 py-3 text-ink-gray-7"
        role="status"
      >
        <LoadingIndicator class="size-4" />{{
          t('Loading plans…', 'Загрузка планов…')
        }}
      </div>
      <Alert
        v-else-if="loadError"
        theme="red"
        :dismissible="false"
        :title="t('Could not load the plans', 'Не удалось загрузить планы')"
      >
        <template #footer
          ><Button variant="ghost" @click="load">{{
            t('Retry', 'Повторить')
          }}</Button></template
        >
      </Alert>
      <template v-else-if="settings">
        <FormControl
          v-model="manager"
          type="select"
          size="md"
          :label="t('Manager', 'Менеджер')"
          :options="options"
          :disabled="saving"
        />
        <template v-if="draft && person">
          <Alert
            v-if="currencyChanged"
            theme="yellow"
            :dismissible="false"
            :title="
              t(
                'The saved plan uses another currency',
                'Сохранённый план в другой валюте',
              )
            "
            :description="
              t(
                'Enter a new amount in the reporting currency.',
                'Введите новую сумму в валюте отчёта.',
              ) +
              ' ' +
              settings.currency
            "
          />
          <FormControl
            v-model="draft.amount"
            variant="outline"
            size="md"
            inputmode="decimal"
            maxlength="28"
            :disabled="saving"
            :label="
              t('Won deal value', 'Сумма выигранных сделок') +
              ', ' +
              settings.currency
            "
            :placeholder="t('For example 600,000', 'Например, 600 000')"
            :error="errors.amount"
            @update:model-value="draft.currency = settings.currency"
          />
          <FormControl
            v-model="draft.wins"
            variant="outline"
            size="md"
            inputmode="numeric"
            maxlength="7"
            :disabled="saving"
            :label="t('Number of won deals', 'Количество выигранных сделок')"
            :placeholder="t('For example 5', 'Например, 5')"
            :error="errors.wins"
          />
          <p class="text-base text-ink-gray-7">
            {{
              t(
                'Set one target or both. The month uses actual results as of today.',
                'Можно задать одну цель или обе. За текущий месяц учитывается факт на сегодня.',
              )
            }}
          </p>
          <Alert
            v-if="saveError"
            theme="red"
            :dismissible="false"
            :title="saveError"
          >
            <template v-if="conflict" #footer>
              <Button variant="outline" @click="load">{{
                t('Load current version', 'Загрузить текущую версию')
              }}</Button>
            </template>
          </Alert>
        </template>
        <p v-else class="text-base text-ink-gray-7">
          {{
            t(
              'No managers in your planning scope.',
              'В вашей зоне управления нет доступных менеджеров.',
            )
          }}
        </p>
      </template>
    </form>
    <template #actions>
      <Button
        type="button"
        variant="outline"
        :disabled="saving"
        @click="close(false)"
        >{{ t('Cancel', 'Отмена') }}</Button
      >
      <Button
        variant="solid"
        icon-left="lucide-check"
        type="submit"
        form="manager-plan-form"
        :loading="saving"
        :disabled="loading || !settings || !person || conflict"
      >
        {{ t('Save plan', 'Сохранить план') }}
      </Button>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import {
  Alert,
  Button,
  Dialog,
  FormControl,
  Icon,
  LoadingIndicator,
  call,
} from 'frappe-ui'

const props = defineProps({
  open: Boolean,
  month: { type: String, required: true },
  monthLabel: { type: String, required: true },
  lang: { type: String, required: true },
  selectedManager: { type: String, default: '' },
})

const emit = defineEmits(['update:open', 'saved'])
const t = (en, ru) => (props.lang === 'ru' ? ru : en)
const prefix = 'crm.analytics.sales_plans.'
const manager = ref('')
const settings = ref(null)
const drafts = reactive({})
const loading = ref(false)
const saving = ref(false)
const loadError = ref(false)
const saveError = ref('')
const conflict = ref(false)
const errors = reactive({ amount: '', wins: '' })
let request

const person = computed(() =>
  settings.value?.assignees.find((row) => row.key === manager.value),
)
const options = computed(() =>
  (settings.value?.assignees || []).map((row) => ({
    value: row.key,
    label: row.label || row.key,
  })),
)
const draft = computed(() => drafts[manager.value])
const existing = computed(() => settings.value?.plans[manager.value])
const currencyChanged = computed(
  () =>
    existing.value?.target_amount &&
    existing.value.currency !== settings.value?.currency,
)

function resetErrors() {
  errors.amount = ''
  errors.wins = ''
  saveError.value = ''
  conflict.value = false
}

function clearDrafts() {
  for (const key of Object.keys(drafts)) delete drafts[key]
}

function close(value) {
  if (!value && !saving.value) emit('update:open', false)
}

async function load() {
  request?.abort()
  const current = new AbortController()
  request = current
  loading.value = true
  loadError.value = false
  try {
    const response = await fetch(
      '/api/method/' +
        prefix +
        'get_plan_settings?' +
        new URLSearchParams({ month: props.month }),
      {
        credentials: 'same-origin',
        cache: 'no-store',
        signal: current.signal,
      },
    )
    if (!response.ok) throw new Error('Plan settings request failed')
    const { message } = await response.json()
    if (request !== current) return
    settings.value = message
    const preferred = manager.value || props.selectedManager
    manager.value = message.assignees.some((row) => row.key === preferred)
      ? preferred
      : message.assignees[0]?.key || ''
    // Keep typed values after a version conflict. The user can review the new
    // version and then decide whether to submit the draft again.
    for (const row of message.assignees) {
      if (drafts[row.key]) continue
      const plan = message.plans[row.key]
      drafts[row.key] = {
        version: plan?.version || null,
        currency: message.currency,
        amount:
          plan?.currency === message.currency && plan.target_amount != null
            ? String(plan.target_amount).replace(/\.0+$/, '')
            : '',
        wins: plan?.target_wins == null ? '' : String(plan.target_wins),
      }
    }
    if (conflict.value) {
      resetErrors()
      const newPlan = message.plans[manager.value]
      if (draft.value) draft.value.version = newPlan?.version || null
      const currentAmount =
        newPlan?.target_amount == null
          ? '—'
          : newPlan.target_amount + ' ' + newPlan.currency
      const currentWins = newPlan?.target_wins ?? '—'
      saveError.value =
        t(
          'Latest saved targets loaded. Review your draft before saving.',
          'Текущая версия загружена. Сверьте её с вашим черновиком перед сохранением.',
        ) +
        ' ' +
        currentAmount +
        ' / ' +
        currentWins
    }
  } catch {
    if (request === current && !current.signal.aborted) loadError.value = true
  } finally {
    if (request === current) loading.value = false
  }
}

async function save() {
  if (saving.value || conflict.value || !draft.value || !person.value) return
  resetErrors()
  const input = draft.value.amount.trim()
  const wins = draft.value.wins.trim()
  const decimal = input.replace(/[ \u00a0\u202f]/g, '').replace(',', '.')
  const amountPattern = /^(?:\d+|\d{1,3}(?:[ \u00a0\u202f]\d{3})+)(?:[.,]\d+)?$/
  const digits = decimal.split('.')[1]?.replace(/0+$/, '').length || 0
  if (
    input &&
    (!amountPattern.test(input) ||
      Number(decimal) <= 0 ||
      Number(decimal) > 999999999 ||
      digits > settings.value.precision)
  )
    errors.amount = t(
      'Enter a positive amount with the currency precision.',
      'Введите положительную сумму с допустимой точностью валюты.',
    )
  if (
    wins &&
    (!/^\d+$/.test(wins) || Number(wins) < 1 || Number(wins) > 1000000)
  )
    errors.wins = t(
      'Enter a whole number from 1 to 1,000,000.',
      'Введите целое число от 1 до 1 000 000.',
    )
  if (input && draft.value.currency !== settings.value.currency) {
    errors.amount = t(
      'The reporting currency changed. Re-enter the amount in the new currency.',
      'Валюта отчёта изменилась. Введите сумму заново в новой валюте.',
    )
  }
  if (!input && !wins)
    errors.amount = t(
      'Set a target for at least one KPI.',
      'Задайте хотя бы одну цель.',
    )
  if (errors.amount || errors.wins) return
  saving.value = true
  try {
    const plan = await call(prefix + 'save_plan', {
      manager: manager.value,
      month: props.month,
      currency: settings.value.currency,
      target_amount: decimal || null,
      target_wins: wins || null,
      version: draft.value.version,
    })
    clearDrafts()
    emit('saved', plan)
    emit('update:open', false)
  } catch (error) {
    conflict.value = error.exc_type === 'TimestampMismatchError'
    saveError.value = conflict.value
      ? t(
          'The plan changed in another session. Reload the current version.',
          'План изменился в другой сессии. Загрузите текущую версию.',
        )
      : t(
          'Could not save the plan. Check the values and your access.',
          'Не удалось сохранить план. Проверьте значения и доступ.',
        )
  } finally {
    saving.value = false
  }
}

watch(manager, resetErrors)
watch(
  () => props.open,
  (open) => {
    if (open) {
      manager.value = props.selectedManager
      settings.value = null
      clearDrafts()
      resetErrors()
      load()
    } else {
      request?.abort()
    }
  },
)
onBeforeUnmount(() => request?.abort())
</script>

<style scoped>
.plan-editor-month {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  border-radius: 8px;
  background: var(--surface-blue-2);
  color: var(--ink-gray-9);
  font-weight: 600;
}
.plan-editor :deep(label) {
  color: var(--ink-gray-8);
}
:global(.dialog-content:has(.plan-editor)) {
  margin: 0;
  max-height: calc(100dvh - 32px);
  overflow-y: auto;
}
</style>
