<template>
  <section
    class="min-h-0 flex-1 overflow-y-auto p-4 text-ink-gray-9 sm:p-6"
    data-testid="telephony-analytics"
    :aria-label="__('Аналитика телефонии')"
  >
    <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-xl font-semibold">{{ __('Аналитика телефонии') }}</h2>
        <p class="mt-2 max-w-3xl text-sm leading-5 text-ink-gray-6">
          {{
            __(
              'Звонки, итоги и задачи по загруженной в CRM истории. Фильтры и права те же, что в журнале.',
            )
          }}
        </p>
      </div>
      <Button
        v-if="settings?.can_manage"
        :label="__('AI и бюджет')"
        variant="ghost"
        class="min-h-11"
        @click="settingsOpen = true"
      />
    </div>
    <p
      v-if="loading"
      role="status"
      class="mb-4 flex items-center gap-2 text-sm text-ink-gray-6"
    >
      <LoadingIndicator class="size-4" />{{ __('Считаем доступную историю…') }}
    </p>
    <div v-if="error" role="alert" class="space-y-3">
      <p class="text-sm text-ink-red-4">{{ error }}</p>
      <Button :label="__('Retry')" @click="load" />
    </div>
    <template v-if="data">
      <div class="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <div
          v-for="metric in metrics"
          :key="metric.label"
          class="rounded-xl border border-outline-gray-2 p-4"
        >
          <p class="text-sm text-ink-gray-6">{{ metric.label }}</p>
          <p
            class="mt-3 text-2xl font-semibold tabular-nums"
            :data-metric="metric.key"
          >
            {{ metric.value }}
          </p>
        </div>
      </div>
      <p class="my-4 text-xs leading-5 text-ink-gray-6">
        {{
          __(
            '«Завершены» — статус звонка в журнале. Он не всегда подтверждает ответ клиента.',
          )
        }}
      </p>
      <div class="grid items-start gap-5 xl:grid-cols-2">
        <section class="rounded-xl border border-outline-gray-2 p-4">
          <h3 class="mb-4 text-base font-semibold">
            {{ __('Обработка звонков') }}
          </h3>
          <dl
            class="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-3 text-sm"
          >
            <template v-for="(label, key) in outcomeLabels" :key="key"
              ><dt class="text-ink-gray-6">{{ label }}</dt>
              <dd class="tabular-nums">
                {{ data.outcomes[key] || 0 }}
              </dd></template
            >
            <dt class="text-ink-gray-6">{{ __('Без сохранённого итога') }}</dt>
            <dd>{{ data.counts.total - data.reviewed }}</dd>
          </dl>
        </section>
        <section class="rounded-xl border border-outline-gray-2 p-4">
          <h3 class="mb-4 text-base font-semibold">
            {{ __('Задачи по звонкам') }}
          </h3>
          <dl class="grid grid-cols-[minmax(0,1fr)_auto] gap-3 text-sm">
            <dt>{{ __('Всего доступных задач') }}</dt>
            <dd>{{ data.tasks.total }}</dd>
            <dt>{{ __('Выполнены') }}</dt>
            <dd>{{ data.tasks.done }}</dd>
            <dt>{{ __('Открыты') }}</dt>
            <dd>{{ data.tasks.open }}</dd>
            <dt>{{ __('Просрочены') }}</dt>
            <dd>{{ data.tasks.overdue }}</dd>
            <dt>{{ __('Отменены') }}</dt>
            <dd>{{ data.tasks.canceled }}</dd>
          </dl>
          <p class="mt-4 text-xs leading-5 text-ink-gray-6">
            {{
              __(
                'Каждая задача учитывается один раз. Доступны только задачи, которые ты можешь открыть.',
              )
            }}
          </p>
        </section>
        <section class="rounded-xl border border-outline-gray-2 p-4">
          <h3 class="mb-3 text-base font-semibold">
            {{ __('Скорость попытки перезвона') }}
          </h3>
          <p class="text-2xl font-semibold tabular-nums">
            {{
              data.callback_median_seconds === null
                ? '—'
                : duration(data.callback_median_seconds)
            }}
          </p>
          <p class="mt-3 text-sm leading-5 text-ink-gray-6">
            {{
              __('Медиана по {0} подтверждённым попыткам перезвона.', [
                data.callback_attempts,
              ])
            }}
          </p>
          <p class="mt-2 text-xs leading-5 text-ink-gray-6">
            {{
              __(
                'От пропущенного до исходящей попытки. Подтверди связь звонков в карточке пропущенного.',
              )
            }}
          </p>
        </section>
        <section class="rounded-xl border border-outline-gray-2 p-4">
          <h3 class="mb-3 text-base font-semibold">
            {{ __('Длительность завершённых') }}
          </h3>
          <dl class="grid grid-cols-[minmax(0,1fr)_auto] gap-3 text-sm">
            <dt>{{ __('Всего') }}</dt>
            <dd>{{ duration(data.duration_seconds) }}</dd>
            <dt>{{ __('В среднем') }}</dt>
            <dd>
              {{
                data.average_seconds === null
                  ? '—'
                  : duration(data.average_seconds)
              }}
            </dd>
            <dt>{{ __('С записью') }}</dt>
            <dd>{{ data.counts.recordings }}</dd>
          </dl>
        </section>
      </div>
      <section class="mt-5 rounded-xl border border-outline-gray-2 p-4">
        <h3 class="mb-4 text-base font-semibold">{{ __('По сотрудникам') }}</h3>
        <p v-if="!data.employees.length" class="text-sm text-ink-gray-6">
          {{ __('Нет звонков по текущим фильтрам') }}
        </p>
        <div class="space-y-3">
          <button
            v-for="person in data.employees"
            :key="person.user"
            type="button"
            class="grid min-h-14 w-full gap-2 rounded-lg bg-surface-gray-1 p-3 text-left hover:bg-surface-gray-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ink-gray-9 sm:grid-cols-[minmax(0,1fr)_auto]"
            @click="person.user && emit('employee', person.user)"
          >
            <span class="min-w-0 break-words text-sm font-medium"
              >{{ person.label || person.user || __('Unassigned')
              }}<span class="mt-1 block text-xs font-normal text-ink-gray-6">{{
                __('Итоги: {0}; перезвон: {1}', [
                  Object.values(person.outcomes).reduce((n, v) => n + v, 0),
                  person.outcomes.Callback || 0,
                ])
              }}</span></span
            ><span class="text-xs leading-5 text-ink-gray-6">{{
              __('Всего {0} · Завершены {1} · Пропущены {2}', [
                person.total,
                person.completed,
                person.missed,
              ])
            }}</span>
          </button>
        </div>
      </section>
      <section class="mt-5 rounded-xl border border-outline-gray-2 p-4">
        <h3 class="mb-4 text-base font-semibold">
          {{ __('Динамика по дням') }}
        </h3>
        <p v-if="!data.days.length" class="text-sm text-ink-gray-6">
          {{ __('Нет звонков по текущим фильтрам') }}
        </p>
        <div class="max-h-80 space-y-3 overflow-y-auto">
          <div
            v-for="day in data.days"
            :key="day.day"
            class="grid grid-cols-[6rem_minmax(0,1fr)_3rem] items-center gap-2 text-xs"
          >
            <span>{{ day.day }}</span>
            <div class="h-2 rounded bg-surface-gray-1">
              <div
                class="h-2 rounded bg-ink-gray-7"
                :style="{ width: `${(day.total / maxDaily) * 100}%` }"
              />
            </div>
            <span class="text-right tabular-nums">{{ day.total }}</span>
          </div>
        </div>
        <p class="mt-3 text-xs leading-5 text-ink-gray-6">
          {{
            __(
              'Всего звонков за день. Число рядом с полосой доступно без различения цветов.',
            )
          }}
        </p>
      </section>
      <p class="mt-4 text-xs text-ink-gray-6">
        {{
          __('Последний расчёт: {0}', [
            formatDate(data.generated_at, 'DD.MM.YYYY HH:mm'),
          ])
        }}
      </p>
    </template>
    <CallAISettings
      v-if="settings"
      v-model="settingsOpen"
      :data="settings"
      @changed="loadSettings"
    />
  </section>
</template>
<script setup>
import { Button, LoadingIndicator, call } from 'frappe-ui'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { callDuration } from '@/utils/telephony'
import { formatDate } from '@/utils'
import CallAISettings from './CallAISettings.vue'
const props = defineProps({
  filters: { type: Object, required: true },
  refreshKey: { type: Number, default: 0 },
})
const emit = defineEmits(['employee'])
const data = ref(null),
  loading = ref(false),
  error = ref(''),
  settings = ref(null),
  settingsOpen = ref(false)
let version = 0,
  disposed = false
const duration = (value) => callDuration(Math.round(value))
const metrics = computed(() =>
  data.value
    ? [
        {
          key: 'total',
          label: __('Всего звонков'),
          value: data.value.counts.total,
        },
        {
          key: 'completed',
          label: __('Завершены'),
          value: data.value.counts.completed,
        },
        {
          key: 'missed',
          label: __('Пропущены входящие'),
          value: data.value.counts.missed,
        },
        {
          key: 'incoming',
          label: __('Входящие / Исходящие'),
          value: `${data.value.counts.incoming} / ${data.value.counts.outgoing}`,
        },
      ]
    : [],
)
const outcomeLabels = computed(() => ({
  Agreed: __('Agreed'),
  Callback: __('Callback'),
  'Not interested': __('Not interested'),
  'Wrong number': __('Wrong number'),
}))
const maxDaily = computed(() =>
  Math.max(1, ...(data.value?.days || []).map((d) => d.total)),
)
async function load() {
  const id = ++version
  loading.value = true
  data.value = null
  error.value = ''
  try {
    const value = await call(
      'crm.call_analysis.analytics.report',
      props.filters,
    )
    if (!disposed && id === version) data.value = value
  } catch {
    if (!disposed && id === version)
      error.value = __(
        'Не удалось рассчитать аналитику. Проверь соединение и доступ.',
      )
  } finally {
    if (id === version) loading.value = false
  }
}
async function loadSettings() {
  try {
    const value = await call('crm.call_analysis.workspace.settings')
    if (!disposed) settings.value = value
  } catch {
    settings.value = null
  }
}
watch(() => [props.filters, props.refreshKey], load, {
  deep: true,
  immediate: true,
})
onBeforeUnmount(() => {
  disposed = true
  version++
})
loadSettings()
</script>
