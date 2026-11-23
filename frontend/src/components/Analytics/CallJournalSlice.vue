<template>
  <div
    class="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 py-4 sm:px-6"
  >
    <header class="flex flex-wrap items-center justify-between gap-2">
      <div>
        <h2 class="text-lg font-semibold text-ink-gray-9">
          {{ __('Звонки в выбранном срезе') }}
        </h2>
        <p v-if="journal" class="mt-1 text-sm text-ink-gray-7">
          {{ journal.period.from_date }} — {{ journal.period.to_date }} ·
          {{ journal.total }}
        </p>
      </div>
      <Button :route="{ name: 'Call Logs', query: {} }" icon-left="lucide-list">
        {{ __('Полный журнал') }}
      </Button>
    </header>
    <Alert v-if="error" theme="red" :title="error" :dismissible="false">
      <template #footer>
        <Button variant="ghost" @click="load">{{ __('Повторить') }}</Button>
      </template>
    </Alert>
    <p v-else-if="loading" role="status">{{ __('Загрузка звонков…') }}</p>
    <template v-else-if="journal">
      <AnalyticsTable
        :columns="columns"
        :rows="journal.rows"
        row-key="name"
        :label="__('Звонки в выбранном срезе')"
        :empty-text="__('По этим фильтрам звонков нет')"
      >
        <template #cell="{ row, column, value }">
          <Button
            v-if="column.key === 'at'"
            variant="ghost"
            @click="$emit('open', row.name)"
          >
            {{ time(value) }}
          </Button>
          <span v-else-if="column.key === 'direction'">{{
            value ? __(value) : '—'
          }}</span>
          <span v-else-if="column.key === 'outcome'">{{
            outcomes[value] || '—'
          }}</span>
          <span v-else-if="column.key === 'status'">{{
            value ? __(value) : '—'
          }}</span>
          <span v-else>{{ value || '—' }}</span>
        </template>
      </AnalyticsTable>
      <div
        v-if="journal.total > limit"
        class="flex flex-wrap items-center gap-2"
      >
        <Button :disabled="page === 0" @click="page--">{{
          __('Назад')
        }}</Button>
        <span class="text-sm tabular-nums"
          >{{ page * limit + 1 }}–{{ page * limit + journal.rows.length }} /
          {{ journal.total }}</span
        >
        <Button
          :disabled="(page + 1) * limit >= journal.total"
          @click="page++"
          >{{ __('Далее') }}</Button
        >
      </div>
    </template>
  </div>
</template>

<script setup>
import { Alert, Button } from 'frappe-ui'
import { onBeforeUnmount, ref, watch } from 'vue'
import { useEventListener } from '@vueuse/core'
import AnalyticsTable from './AnalyticsTable.vue'

const props = defineProps({ filters: { type: Object, required: true } })
defineEmits(['open'])
const page = ref(0)
const limit = 25
const journal = ref(null)
const error = ref('')
const loading = ref(false)
let request
const columns = [
  { key: 'at', label: __('Время звонка') },
  { key: 'direction', label: __('Направление') },
  { key: 'employee_label', label: __('Сотрудник') },
  { key: 'status', label: __('Статус') },
  { key: 'outcome', label: __('Итог') },
]
const outcomes = {
  Agreed: __('Договорились'),
  Callback: __('Перезвонить'),
  'Not interested': __('Неинтересно'),
  'Wrong number': __('Неверный номер'),
}

function time(value) {
  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone: journal.value.period.timezone,
  }).format(new Date(value))
}

async function load() {
  request?.abort()
  const current = new AbortController()
  request = current
  loading.value = true
  error.value = ''
  const query = new URLSearchParams({
    filters: JSON.stringify(props.filters),
    start: page.value * limit,
    limit,
  })
  try {
    const response = await fetch(
      '/api/method/crm.analytics.call_journal.get_journal?' + query,
      { signal: current.signal, cache: 'no-store' },
    )
    if (!response.ok) throw new Error()
    const { message } = await response.json()
    if (request === current) journal.value = message
  } catch (failure) {
    if (request === current && failure.name !== 'AbortError')
      error.value = __('Не удалось загрузить звонки по выбранным фильтрам')
  } finally {
    if (request === current) loading.value = false
  }
}

watch(
  () => props.filters,
  () => {
    if (page.value) page.value = 0
    else load()
  },
)
watch(page, load, { immediate: true })
useEventListener(window, 'crm-call-work-updated', load)
onBeforeUnmount(() => request?.abort())
</script>
