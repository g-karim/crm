<template>
  <Dialog
    v-model="open"
    :title="t('Attention rules', 'Правила внимания')"
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
      v-if="settings?.can_edit && draft"
      class="grid min-w-0 grid-cols-1 gap-4"
      @submit.prevent="save"
    >
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <FormControl
          :model-value="selectedPipeline"
          type="select"
          :label="t('Pipeline', 'Воронка')"
          :options="pipelines"
          :disabled="saving"
          class="min-w-0"
          @update:model-value="selectPipeline"
        />
        <FormControl
          v-model="selected"
          type="select"
          :label="t('Stage', 'Этап')"
          :options="stages"
          :disabled="saving"
          class="min-w-0"
        />
      </div>
      <fieldset class="grid min-w-0 gap-2" :disabled="saving">
        <legend class="mb-2 font-medium">
          {{
            t(
              'Show deals for these reasons',
              'Показывать сделки по этим причинам',
            )
          }}
        </legend>
        <FormControl
          v-for="code in settings.rules"
          :key="code"
          type="checkbox"
          :model-value="draft.enabled_rules.includes(code)"
          :label="reason(code)"
          @update:model-value="(checked) => toggle(code, checked)"
        />
      </fieldset>
      <FormControl
        v-model="draft.stale_days"
        type="number"
        min="0"
        max="3650"
        step="1"
        :label="t('Long stage threshold, days', 'Порог долгого этапа, дней')"
        :description="
          t(
            'Elapsed time in the current stage, in 24-hour intervals.',
            'Сколько суток должно пройти на текущем этапе.',
          )
        "
        :disabled="saving"
        required
      />
      <Button
        type="submit"
        variant="solid"
        :loading="saving"
        class="justify-self-start"
      >
        {{ t('Save rules', 'Сохранить правила') }}
      </Button>
    </form>
    <p v-else-if="settings && !settings.stages.length" class="text-ink-gray-7">
      {{
        t(
          'No open stages are available to edit.',
          'Нет доступных для настройки открытых этапов.',
        )
      }}
    </p>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Alert, Button, Dialog, FormControl, call } from 'frappe-ui'

const props = defineProps({
  t: { type: Function, required: true },
  reason: { type: Function, required: true },
  pipeline: { type: String, default: '' },
})
const open = defineModel('open', { type: Boolean, default: false })
const emit = defineEmits(['saved'])
const endpoint = 'crm.analytics.attention_settings.'
const settings = ref(null)
const drafts = ref({})
const selectedPipeline = ref('')
const selected = ref('')
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const notice = ref('')
const pipelines = computed(() => [
  ...new Map(
    (settings.value?.stages || []).map((stage) => [
      stage.pipeline,
      { value: stage.pipeline, label: stage.pipeline_label || stage.pipeline },
    ]),
  ).values(),
])
const stages = computed(() =>
  (settings.value?.stages || [])
    .filter((stage) => stage.pipeline === selectedPipeline.value)
    .map((stage) => ({ value: stage.key, label: stage.label })),
)
const draft = computed(() => drafts.value[selected.value])

watch(open, async (visible, _previous, onCleanup) => {
  if (!visible) return
  const request = new AbortController()
  onCleanup(() => request.abort())
  error.value = ''
  notice.value = ''
  settings.value = null
  drafts.value = {}
  loading.value = true
  try {
    const response = await fetch('/api/method/' + endpoint + 'get_settings', {
      cache: 'no-store',
      signal: request.signal,
    })
    if (!response.ok) throw new Error()
    const { message } = await response.json()
    if (request.signal.aborted) return
    settings.value = message
    drafts.value = Object.fromEntries(
      message.stages.map((stage) => [
        stage.key,
        { ...stage, enabled_rules: [...stage.enabled_rules] },
      ]),
    )
    selectPipeline(
      pipelines.value.some((item) => item.value === props.pipeline)
        ? props.pipeline
        : pipelines.value[0]?.value || '',
    )
  } catch {
    if (!request.signal.aborted)
      error.value = props.t(
        'Could not load attention rules.',
        'Не удалось загрузить правила внимания.',
      )
  } finally {
    if (!request.signal.aborted) loading.value = false
  }
})

function selectPipeline(pipeline) {
  selectedPipeline.value = pipeline
  selected.value = stages.value[0]?.value || ''
}

function toggle(code, checked) {
  const enabled = new Set(draft.value.enabled_rules)
  if (checked) enabled.add(code)
  else enabled.delete(code)
  draft.value.enabled_rules = settings.value.rules.filter((rule) =>
    enabled.has(rule),
  )
}

async function save() {
  if (!draft.value || saving.value) return
  const changes = draft.value
  const days = String(changes.stale_days ?? '')
  if (!/^\d{1,4}$/.test(days) || Number(days) > 3650) {
    error.value = props.t(
      'Enter a whole number from 0 to 3650.',
      'Укажите целое число от 0 до 3650.',
    )
    return
  }
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    const stored = await call(endpoint + 'save_setting', {
      stage: changes.key,
      enabled_rules: changes.enabled_rules,
      stale_days: days,
      version: changes.version,
      expected_viewer: settings.value.viewer,
    })
    drafts.value[changes.key] = stored
    notice.value = props.t('Rules saved.', 'Правила сохранены.')
    emit('saved')
  } catch (failure) {
    error.value =
      failure?.exc_type === 'TimestampMismatchError'
        ? props.t(
            'This stage changed in another session. Reopen its settings to compare.',
            'Этап изменился в другой сессии. Откройте настройки заново для сверки.',
          )
        : props.t(
            'Could not save the rules. Check your access and the threshold.',
            'Не удалось сохранить правила. Проверьте доступ и порог.',
          )
  } finally {
    saving.value = false
  }
}
</script>
