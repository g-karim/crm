<template>
  <Dialog
    v-model="open"
    :options="{ title: __('AI-анализ и бюджет'), size: 'xl' }"
  >
    <template #body-content>
      <div class="space-y-4 text-ink-gray-9" data-testid="call-ai-settings">
        <p class="text-sm leading-5 text-ink-gray-6">
          {{
            __(
              'Записи отправляются в OpenRouter только по команде «Анализировать». Заметки менеджера остаются без изменений. Бюджет указан в USD и не связан с балансом Exolve.',
            )
          }}
        </p>
        <p
          v-if="!data.configured"
          role="status"
          class="rounded-lg bg-surface-gray-1 p-3 text-sm"
        >
          {{
            __(
              'AI-ключ не настроен на сервере. Ключ Exolve подходит только для телефонии.',
            )
          }}
        </p>
        <FormControl
          v-model="enabled"
          type="checkbox"
          :label="__('Включить AI-анализ звонков')"
          :disabled="!data.configured || busy"
        />
        <FormControl
          v-model="daily"
          type="number"
          :label="__('Дневной бюджет, USD')"
          min="0.25"
          max="100"
          step="0.25"
          :disabled="busy"
        />
        <FormControl
          v-model="reserve"
          type="number"
          :label="__('Резерв на один анализ, USD')"
          min="0.25"
          step="0.25"
          :disabled="busy"
        />
        <p class="text-sm leading-5 text-ink-gray-6">
          {{
            __(
              data.shared_key
                ? 'Сегодня учтено вместе с резервами: ${0}. Используется общий ключ CRM. Локальный бюджет ограничивает запросы этого стенда; лимиты ключа на проде не меняются.'
                : 'Сегодня учтено вместе с резервами: ${0}. Резерв — оценка; жёсткий дневной лимит задаётся на отдельном ключе OpenRouter. Для работы нужен daily limit не выше бюджета CRM, с учётом BYOK.',
              [Number(data.used).toFixed(4)],
            )
          }}
        </p>
        <p class="text-sm leading-5 text-ink-gray-6">
          {{
            __(
              'До 10 минут и 25 МБ на запись. Сбой сети не запускает повторное платное распознавание. Неизвестные расходы требуют сверки с журналом провайдера.',
            )
          }}
        </p>
        <p class="break-words text-xs text-ink-gray-6">
          {{ data.transcription_model }} · {{ data.summary_model }}
        </p>
        <Button
          :label="__('Сохранить настройки AI')"
          variant="solid"
          :loading="busy"
          @click="save"
        />
        <section
          v-for="run in data.uncertain || []"
          :key="run.name"
          class="space-y-3 rounded-lg border border-outline-gray-2 p-3"
        >
          <h3 class="text-sm font-semibold">
            {{ __('Сверка неизвестного расхода') }}
          </h3>
          <p class="break-all text-xs text-ink-gray-6">
            {{ run.name }} ·
            {{ run.provider_ids || __('ID ответа не получен') }}
          </p>
          <FormControl
            v-model="costs[run.name]"
            type="number"
            min="0"
            step="0.000001"
            :label="__('Полная стоимость этого анализа, USD')"
          />
          <FormControl
            v-model="notes[run.name]"
            :label="__('Ссылка или номер операции из журнала провайдера')"
          />
          <Button
            :label="__('Подтвердить сверку и выключить AI')"
            :loading="busy"
            @click="reconcile(run.name)"
          />
        </section>
        <p v-if="error" role="alert" class="text-sm text-ink-red-4">
          {{ error }}
        </p>
        <p v-if="saved" role="status" class="text-sm text-ink-gray-7">
          {{ __('Настройки сохранены') }}
        </p>
      </div>
    </template>
  </Dialog>
</template>
<script setup>
import { Button, Dialog, FormControl, call } from 'frappe-ui'
import { reactive, ref, watch } from 'vue'
const open = defineModel({ type: Boolean })
const props = defineProps({ data: { type: Object, required: true } })
const emit = defineEmits(['changed'])
const enabled = ref(false),
  daily = ref('1'),
  reserve = ref('0.25'),
  busy = ref(false),
  error = ref(''),
  saved = ref(false)
const costs = reactive({}),
  notes = reactive({})
watch(open, (value) => {
  if (value) {
    enabled.value = props.data.enabled
    daily.value = String(props.data.daily_limit)
    reserve.value = String(props.data.run_reserve)
    error.value = ''
    saved.value = false
  }
})
async function save() {
  busy.value = true
  error.value = ''
  saved.value = false
  try {
    await call('crm.call_analysis.workspace.save_settings', {
      enabled: enabled.value ? 1 : 0,
      daily_limit: daily.value,
      run_reserve: reserve.value,
      expected_revision: props.data.revision,
    })
    saved.value = true
    emit('changed')
  } catch {
    error.value = __(
      'Не удалось сохранить. Проверь бюджет и AI-ключ. При изменении в другом окне открой настройки заново.',
    )
  } finally {
    busy.value = false
  }
}
async function reconcile(name) {
  busy.value = true
  error.value = ''
  try {
    await call('crm.call_analysis.workspace.reconcile', {
      run_name: name,
      actual_cost: costs[name],
      note: notes[name],
    })
    emit('changed')
  } catch {
    error.value = __(
      'Не удалось подтвердить расход. Укажи проверенную стоимость и ссылку на операцию.',
    )
  } finally {
    busy.value = false
  }
}
</script>
