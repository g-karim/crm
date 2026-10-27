<template>
  <section
    v-if="visible"
    class="space-y-3 rounded-xl border border-outline-gray-2 p-4 text-ink-gray-9"
    data-testid="callback-proof"
  >
    <h3 class="text-sm font-semibold">
      {{ __('Фактическая попытка перезвона') }}
    </h3>
    <p class="text-xs leading-5 text-ink-gray-6">
      {{
        __(
          'Выбери исходящий звонок, который относится к этому пропущенному. Эта связь используется для расчёта скорости перезвона.',
        )
      }}
    </p>
    <p v-if="proof.linked" class="break-words text-sm">
      {{ __('Подтверждено: {0}', [proof.linked]) }}
    </p>
    <template v-else-if="proof.can_manage"
      ><FormControl
        v-model="outgoing"
        type="select"
        :label="__('Исходящая попытка')"
        :options="options"
        :disabled="saving"
      /><Button
        :label="__('Подтвердить связь звонков')"
        class="min-h-11 w-full"
        :disabled="!outgoing"
        :loading="saving"
        @click="save"
      />
      <p v-if="!candidates.length" class="text-xs text-ink-gray-6">
        {{
          __(
            'Пока нет доступной исходящей попытки на этот номер после пропущенного.',
          )
        }}
      </p></template
    >
    <p v-if="error" role="alert" class="text-sm text-ink-red-4">{{ error }}</p>
  </section>
</template>
<script setup>
import { Button, FormControl, call } from 'frappe-ui'
import { computed, onBeforeUnmount, ref } from 'vue'
import { formatDate } from '@/utils'
const props = defineProps({ name: { type: String, required: true } })
const proof = ref({}),
  candidates = ref([]),
  outgoing = ref(''),
  visible = ref(false),
  saving = ref(false),
  error = ref('')
let disposed = false
const options = computed(() => [
  { value: '', label: __('Выбери звонок') },
  ...candidates.value.map((c) => ({
    value: c.name,
    label: `${formatDate(c.timestamp, 'DD.MM.YYYY HH:mm')} · ${__(c.status)} · ${c.agent || '—'}`,
  })),
])
async function load() {
  try {
    const data = await call('crm.call_analysis.analytics.callback_status', {
      name: props.name,
    })
    if (disposed) return
    proof.value = data
    visible.value = data.applicable
    candidates.value = data.candidates || []
  } catch {
    visible.value = false
  }
}
async function save() {
  saving.value = true
  error.value = ''
  try {
    await call('crm.call_analysis.analytics.link_callback', {
      name: props.name,
      outgoing: outgoing.value,
      expected_revision: proof.value.revision,
      expected_viewer: proof.value.viewer,
    })
    await load()
    window.dispatchEvent(new Event('crm-call-work-updated'))
  } catch {
    error.value = __(
      'Не удалось связать звонки. Обнови карточку и проверь доступ к выбранной попытке.',
    )
  } finally {
    saving.value = false
  }
}
onBeforeUnmount(() => {
  disposed = true
})
load()
</script>
