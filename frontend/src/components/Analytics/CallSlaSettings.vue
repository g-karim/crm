<template>
  <Dialog
    :model-value="open"
    :title="t('Call SLA settings', 'Правила перезвона')"
    size="lg"
    :dismissible="!saving"
    @update:model-value="onOpen"
  >
    <form id="crm-call-sla-form" class="grid gap-4" @submit.prevent="save">
      <p v-if="loading" role="status">
        {{ t('Loading settings…', 'Загрузка настроек…') }}
      </p>
      <Alert v-if="error" theme="red" :title="error" :dismissible="false">
        <template v-if="!settings" #footer>
          <Button variant="ghost" @click="load">{{
            t('Retry', 'Повторить')
          }}</Button>
        </template>
      </Alert>
      <template v-if="settings">
        <FormControl
          v-model="settings.enabled"
          type="checkbox"
          :label="
            t('Calculate callback SLA', 'Считать соблюдение срока перезвона')
          "
          :disabled="saving"
        />
        <FormControl
          v-model="settings.timezone"
          :label="t('Timezone', 'Часовой пояс')"
          required
          :disabled="saving"
        />
        <fieldset class="grid gap-2" :disabled="saving">
          <legend class="text-base text-ink-gray-8">
            {{ t('Working days', 'Рабочие дни') }}
          </legend>
          <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <FormControl
              v-for="(day, index) in weekdays"
              :key="day"
              v-model="chosen[index]"
              type="checkbox"
              :label="day"
            />
          </div>
        </fieldset>
        <div class="grid grid-cols-2 gap-3">
          <FormControl
            v-model="settings.work_start"
            type="time"
            :label="t('Working day starts', 'Начало дня')"
            required
            :disabled="saving"
          />
          <FormControl
            v-model="settings.work_end"
            type="time"
            :label="t('Working day ends', 'Конец дня')"
            required
            :disabled="saving"
          />
        </div>
        <FormControl
          v-model="settings.response_minutes"
          type="number"
          min="1"
          max="10080"
          :label="
            t(
              'Callback target, working minutes',
              'Срок перезвона, рабочих минут',
            )
          "
          required
          :disabled="saving"
        />
        <FormControl
          v-model="settings.require_original_employee"
          type="checkbox"
          :label="
            t(
              'Require the original employee to call back',
              'Учитывать в SLA только перезвон ответственного за входящий',
            )
          "
          :description="
            t(
              'With this option off, a confirmed conversation by another employee also meets the callback requirement.',
              'Без этой настройки подтверждённый разговор другого сотрудника тоже закрывает обязательство перезвонить.',
            )
          "
          :disabled="saving"
        />
      </template>
    </form>
    <template #actions>
      <Button :disabled="saving" @click="onOpen(false)">{{
        t('Cancel', 'Отмена')
      }}</Button>
      <Button
        type="submit"
        form="crm-call-sla-form"
        variant="solid"
        :loading="saving"
        :disabled="loading || !settings?.available"
      >
        {{ t('Save', 'Сохранить') }}
      </Button>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Alert, Button, Dialog, FormControl, call } from 'frappe-ui'

const props = defineProps({
  open: Boolean,
  lang: { type: String, required: true },
})
const emit = defineEmits(['update:open', 'saved'])
const t = (en, ru) => (props.lang === 'ru' ? ru : en)
const endpoint = 'crm.analytics.call_sla_settings.'
const settings = ref(null)
const chosen = ref([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
let request
const weekdays = computed(() =>
  Array.from({ length: 7 }, (_, day) =>
    new Intl.DateTimeFormat(props.lang, {
      weekday: 'short',
      timeZone: 'UTC',
    }).format(new Date(Date.UTC(2024, 0, 1 + day))),
  ),
)

function onOpen(open) {
  if (!open && !saving.value) emit('update:open', false)
}

async function load() {
  request?.abort()
  const current = new AbortController()
  request = current
  loading.value = true
  error.value = ''
  settings.value = null
  try {
    const response = await fetch('/api/method/' + endpoint + 'get_settings', {
      signal: current.signal,
      cache: 'no-store',
    })
    if (!response.ok) throw new Error()
    const { message } = await response.json()
    if (request !== current) return
    settings.value = {
      ...message,
      enabled: Boolean(message.enabled),
      require_original_employee: Boolean(message.require_original_employee),
    }
    chosen.value = weekdays.value.map((_, day) =>
      message.weekdays.split(',').includes(String(day)),
    )
  } catch (failure) {
    if (request === current && failure.name !== 'AbortError')
      error.value = t(
        'Could not load call SLA settings',
        'Не удалось загрузить правила перезвона',
      )
  } finally {
    if (request === current) loading.value = false
  }
}

async function save() {
  if (!settings.value?.available || saving.value) return
  const {
    enabled,
    timezone,
    work_start,
    work_end,
    response_minutes,
    version,
    require_original_employee,
  } = settings.value
  const days = chosen.value.flatMap((selected, day) => (selected ? [day] : []))
  if (
    !days.length ||
    work_start >= work_end ||
    !Number.isInteger(Number(response_minutes)) ||
    Number(response_minutes) < 1 ||
    Number(response_minutes) > 10080
  ) {
    error.value = t(
      'Check working days, hours and the response time.',
      'Проверьте рабочие дни, часы и срок перезвона.',
    )
    return
  }
  saving.value = true
  error.value = ''
  try {
    await call(endpoint + 'save_settings', {
      enabled,
      timezone: timezone.trim(),
      work_start,
      work_end,
      response_minutes: Number(response_minutes),
      weekdays: days.join(','),
      version,
      require_original_employee,
    })
    emit('saved')
    emit('update:open', false)
  } catch (failure) {
    error.value =
      failure.exc_type === 'TimestampMismatchError'
        ? t(
            'Settings changed in another session. Reopen the form before saving.',
            'Настройки изменились в другой сессии. Откройте форму заново перед сохранением.',
          )
        : t(
            'Could not save the schedule. Check the timezone and values.',
            'Не удалось сохранить график. Проверьте часовой пояс и значения.',
          )
  } finally {
    saving.value = false
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) load()
    else request?.abort()
  },
)
onBeforeUnmount(() => request?.abort())
</script>
