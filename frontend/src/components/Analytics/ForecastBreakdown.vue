<template>
  <Card :title="t('Forecast categories', 'Категории прогноза')" class="min-w-0">
    <template #actions>
      <Button
        v-if="report.can_manage_forecast_categories"
        icon-left="lucide-settings-2"
        :disabled="stale"
        @click="open = true"
      >
        {{ t('Set categories', 'Настроить категории') }}
      </Button>
    </template>
    <p class="mb-3 text-sm text-ink-gray-7">
      {{
        t(
          'Each open deal in the forecast horizon uses the category of its current stage.',
          'Открытая сделка в горизонте прогноза получает категорию своего текущего этапа.',
        )
      }}
    </p>
    <AnalyticsTable
      :columns="columns"
      :rows="report.forecast_categories || []"
      :label="t('Forecast by category', 'Прогноз по категориям')"
      :empty-text="
        t(
          'No available deals in the forecast horizon',
          'В горизонте прогноза нет доступных сделок',
        )
      "
    >
      <template #cell="{ column, row, value }">
        <Button
          v-if="column.key === 'key'"
          variant="ghost"
          :disabled="stale"
          @click="emit('details', row.key)"
          >{{ label(row.key) }}</Button
        >
        <span v-else-if="column.key === 'value'">
          {{ format(value) }} {{ report.context.currency }}
          <small v-if="!row.complete" class="text-ink-amber-9">
            {{ t('known part', 'известная часть') }}
          </small>
        </span>
        <span v-else>{{ value }}</span>
      </template>
    </AnalyticsTable>
  </Card>

  <Dialog
    v-model="open"
    :title="t('Forecast categories by stage', 'Категории прогноза по этапам')"
    size="lg"
    :dismissible="!saving"
    :show-close-button="!saving"
  >
    <p v-if="loading" role="status">
      {{ t('Loading stages…', 'Загрузка этапов…') }}
    </p>
    <Alert v-if="error" theme="red" :title="error" :dismissible="false" />
    <p v-if="notice" role="status" class="mb-3 text-sm text-ink-green-8">
      {{ notice }}
    </p>
    <form
      v-if="settings?.can_edit && stage"
      class="flex flex-col gap-3"
      @submit.prevent="save"
    >
      <FormControl
        v-model="selected"
        type="select"
        :label="t('Open stage', 'Открытый этап')"
        :options="stages"
        :disabled="saving"
      />
      <FormControl
        v-model="category"
        type="select"
        :label="t('Forecast category', 'Категория прогноза')"
        :options="categories"
        :disabled="saving"
      />
      <Button
        type="submit"
        variant="solid"
        :loading="saving"
        class="self-start"
        >{{ t('Save category', 'Сохранить категорию') }}</Button
      >
    </form>
    <p
      v-else-if="settings && !settings.stages.length && !error"
      class="text-sm text-ink-gray-7"
    >
      {{
        t(
          'There are no available open stages.',
          'Нет доступных открытых этапов.',
        )
      }}
    </p>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Alert, Button, Card, Dialog, FormControl, call } from 'frappe-ui'
import { formatAnalyticsNumber } from '@/utils/analyticsNumbers'
import {
  forecastCategories,
  forecastCategoryLabel,
} from '@/utils/forecastCategories'
import AnalyticsTable from './AnalyticsTable.vue'

const props = defineProps({
  report: { type: Object, required: true },
  t: { type: Function, required: true },
  lang: { type: String, required: true },
  stale: Boolean,
})
const emit = defineEmits(['details', 'saved'])
const endpoint = 'crm.analytics.forecast_categories.'
const open = ref(false)
const loading = ref(false)
const saving = ref(false)
const settings = ref(null)
const error = ref('')
const notice = ref('')
const category = ref('Uncategorized')
const selected = ref(null)
let generation = 0

const label = (value) => forecastCategoryLabel(value, props.t)
const format = (value) =>
  formatAnalyticsNumber(value, props.lang === 'ru' ? 'ru-RU' : 'en-US')
const categories = computed(() =>
  forecastCategories.map((value) => ({ value, label: label(value) })),
)
const stages = computed(() =>
  (settings.value?.stages || []).map((row) => ({
    value: row.key,
    label: row.label + ' · ' + row.pipeline,
  })),
)
const stage = computed(() =>
  settings.value?.stages.find((item) => item.key === selected.value),
)
const columns = computed(() => [
  { key: 'key', label: props.t('Category', 'Категория') },
  { key: 'count', label: props.t('Deals', 'Сделки'), numeric: true },
  {
    key: 'value',
    label: props.t('Weighted value', 'Взвешенная сумма'),
    numeric: true,
  },
])
watch(stage, (value) => {
  category.value = value?.category || 'Uncategorized'
})

watch(open, async (visible) => {
  const current = ++generation
  error.value = ''
  notice.value = ''
  loading.value = visible
  if (!visible) {
    settings.value = null
    return
  }
  try {
    const response = await fetch('/api/method/' + endpoint + 'get_settings', {
      cache: 'no-store',
    })
    if (!response.ok) throw new Error('forecast settings')
    const data = (await response.json()).message
    if (current === generation) {
      settings.value = data
      selected.value = data.stages[0]?.key
    }
  } catch {
    if (current === generation)
      error.value = props.t(
        'Could not load stages.',
        'Не удалось загрузить этапы.',
      )
  } finally {
    if (current === generation) loading.value = false
  }
})

async function save() {
  if (saving.value || !stage.value) return
  saving.value = true
  notice.value = ''
  error.value = ''
  try {
    const updated = await call(endpoint + 'save_setting', {
      stage: stage.value.key,
      category: category.value === 'Uncategorized' ? '' : category.value,
      version: stage.value.version,
      expected_viewer: settings.value.viewer,
    })
    settings.value.stages = settings.value.stages.map((row) =>
      row.key === updated.key ? updated : row,
    )
    notice.value = props.t('Category saved.', 'Категория сохранена.')
    emit('saved')
  } catch (failure) {
    error.value =
      failure?.exc_type === 'TimestampMismatchError'
        ? props.t(
            'The stage changed. Reopen the settings.',
            'Этап изменился. Откройте настройки заново.',
          )
        : props.t(
            'Could not save the category.',
            'Не удалось сохранить категорию.',
          )
  } finally {
    saving.value = false
  }
}
</script>
