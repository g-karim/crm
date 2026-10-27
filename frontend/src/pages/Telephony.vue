<template>
  <LayoutHeader>
    <template #left-header>
      <h1 class="text-lg font-semibold text-ink-gray-9">
        {{ __('Telephony') }}
      </h1>
    </template>
    <template #right-header>
      <Button
        :aria-label="analyticsOpen ? __('Журнал звонков') : __('Аналитика')"
        :tooltip="analyticsOpen ? __('Журнал звонков') : __('Аналитика')"
        icon-left="lucide-bar-chart-2"
        variant="ghost"
        class="telephony-secondary min-h-11 min-w-11"
        @click="toggleAnalytics"
        ><span class="hidden sm:inline">{{
          analyticsOpen ? __('Журнал звонков') : __('Аналитика')
        }}</span></Button
      >
      <Button
        class="telephony-secondary hidden sm:inline-flex"
        :label="__('List view')"
        icon-left="lucide-list"
        variant="ghost"
        @click="router.push({ name: 'Call Logs' })"
      />
      <Button
        :aria-label="__('Dial a number')"
        :tooltip="__('Dial a number')"
        icon-left="lucide-phone"
        variant="solid"
        class="min-h-11 min-w-11"
        @click="showDialer"
        ><span class="hidden sm:inline">{{ __('Dial a number') }}</span></Button
      >
    </template>
  </LayoutHeader>
  <div
    class="relative flex min-h-0 flex-1 flex-col overflow-hidden bg-surface-base"
    data-testid="telephony-workspace"
  >
    <div
      class="grid shrink-0 grid-cols-2 items-end gap-3 border-b border-outline-gray-2 px-4 py-4 sm:flex sm:flex-wrap sm:px-6"
    >
      <div
        class="col-span-2 flex min-w-0 items-end gap-2 sm:min-w-48 sm:flex-1"
      >
        <div class="min-w-0 flex-1">
          <FormControl
            v-model="search"
            :label="__('Search calls')"
            :placeholder="__('Клиент, номер или текст разговора')"
            type="search"
          >
            <template #prefix
              ><FeatherIcon
                name="search"
                class="size-4 text-ink-gray-5"
                aria-hidden="true"
            /></template>
          </FormControl>
        </div>
        <Button
          :aria-label="__('Refresh calls')"
          :tooltip="__('Refresh calls')"
          icon="lucide-refresh-cw"
          class="min-h-8 min-w-8"
          :loading="loading"
          @click="refresh"
        />
      </div>
      <div class="min-w-0 sm:w-36 sm:shrink-0">
        <FormControl
          v-model="period"
          :disabled="view === 'attention'"
          :label="__('Period')"
          type="select"
          :options="periodOptions"
        />
      </div>
      <div class="min-w-0 sm:w-36 sm:shrink-0">
        <FormControl
          v-model="employee"
          :label="__('Employee')"
          type="select"
          :options="employeeOptions"
        />
      </div>
      <div class="min-w-0 sm:w-40 sm:shrink-0">
        <FormControl
          v-model="line"
          :label="__('Phone line')"
          type="select"
          :options="lineOptions"
        />
      </div>
      <div class="min-w-0 sm:w-40 sm:shrink-0">
        <FormControl
          v-model="outcome"
          :label="__('Call outcome')"
          type="select"
          :options="outcomeOptions"
        />
      </div>
    </div>

    <p
      v-if="view === 'attention'"
      class="shrink-0 border-b border-outline-gray-1 px-4 py-2 text-sm leading-5 text-ink-gray-6 sm:px-6"
    >
      {{
        __(
          'Unhandled missed calls and linked tasks due today or earlier, regardless of call date.',
        )
      }}
    </p>
    <div
      class="flex shrink-0 flex-wrap gap-x-5 gap-y-1 border-b border-outline-gray-2 px-4 sm:px-6"
      :aria-label="__('Call filters')"
    >
      <button
        v-for="tab in tabs"
        :key="tab.value"
        type="button"
        :aria-pressed="view === tab.value"
        class="min-h-11 border-b-2 text-base focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ink-gray-9"
        :class="
          view === tab.value
            ? 'border-outline-gray-9 font-medium text-ink-gray-9'
            : 'border-transparent text-ink-gray-6 hover:text-ink-gray-9'
        "
        @click="view = tab.value"
      >
        {{ tab.label }}
      </button>
    </div>
    <TelephonyAnalytics
      v-if="analyticsOpen"
      :filters="analyticsFilters"
      :refresh-key="analyticsRevision"
      @employee="selectAnalyticsEmployee"
    />
    <div v-if="!analyticsOpen" class="relative flex min-h-0 flex-1">
      <section
        class="flex min-w-0 flex-1 flex-col"
        :aria-label="__('Call history')"
      >
        <div
          v-if="loading && !calls.length"
          class="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-ink-gray-6"
          role="status"
        >
          <LoadingIndicator class="size-5" />{{ __('Loading calls…') }}
        </div>
        <div
          v-else-if="listError"
          class="flex flex-1 flex-col items-center justify-center gap-4 p-6 text-center"
          role="alert"
        >
          <FeatherIcon
            name="alert-circle"
            class="size-7 text-ink-gray-5"
            aria-hidden="true"
          />
          <p class="max-w-sm text-base text-ink-gray-7">{{ listError }}</p>
          <Button :label="__('Retry')" @click="loadCalls()" />
        </div>
        <div
          v-else-if="!calls.length"
          class="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center"
        >
          <div
            class="grid size-14 place-items-center rounded-full bg-surface-gray-2"
          >
            <FeatherIcon
              name="phone"
              class="size-6 text-ink-gray-5"
              aria-hidden="true"
            />
          </div>
          <h2 class="text-lg font-medium text-ink-gray-9">
            {{ __('No calls found') }}
          </h2>
          <p class="max-w-xs text-sm leading-5 text-ink-gray-6">
            {{
              __(
                'Try a different search or period. New calls will appear here after synchronization.',
              )
            }}
          </p>
          <Button :label="__('Reset filters')" @click="resetFilters" />
        </div>
        <div v-else class="min-h-0 flex-1 overflow-y-auto" :aria-busy="loading">
          <div v-for="group in grouped" :key="group.date">
            <h2
              class="sticky top-0 z-[1] border-b border-outline-gray-1 bg-surface-gray-1 px-4 py-2 text-sm font-medium text-ink-gray-6 sm:px-6"
            >
              {{ dayLabel(group.date) }}
            </h2>
            <button
              v-for="item in group.calls"
              :key="item.name"
              type="button"
              :data-call="item.name"
              :aria-pressed="selectedName === item.name"
              :aria-label="
                __('Open call with {0}', [
                  item.client_name || displayPhone(item.number),
                ])
              "
              class="group flex min-h-24 w-full items-center gap-3 border-b border-l-2 border-outline-gray-1 py-4 pl-3 pr-4 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ink-gray-9 sm:pl-5 sm:pr-6"
              :class="
                selectedName === item.name
                  ? '!border-l-outline-gray-9 bg-surface-gray-2'
                  : 'border-l-transparent hover:bg-surface-gray-1'
              "
              @click="selectCall(item.name)"
            >
              <span
                class="grid size-10 shrink-0 place-items-center rounded-full"
                :class="
                  isMissedCall(item)
                    ? 'bg-surface-red-1 text-ink-red-4'
                    : 'bg-surface-gray-2 text-ink-gray-7'
                "
              >
                <FeatherIcon
                  :name="
                    isMissedCall(item)
                      ? 'phone-missed'
                      : item.type === 'Incoming'
                        ? 'phone-incoming'
                        : 'phone-outgoing'
                  "
                  class="size-4"
                  aria-hidden="true"
                />
              </span>
              <span class="min-w-0 flex-1">
                <span class="flex items-center justify-between gap-3"
                  ><span class="truncate text-base-medium text-ink-gray-9">{{
                    item.client_name ||
                    displayPhone(item.number) ||
                    __('Unknown number')
                  }}</span>
                  <time class="shrink-0 text-sm tabular-nums text-ink-gray-6">{{
                    formatDate(item.timestamp, 'HH:mm')
                  }}</time></span
                >
                <span class="mt-1 block truncate text-sm text-ink-gray-6">{{
                  displayPhone(item.number)
                }}</span>
                <span
                  class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm"
                  :class="
                    isMissedCall(item) ? 'text-ink-red-4' : 'text-ink-gray-6'
                  "
                >
                  <span
                    >{{ __(item.type) }} · {{ __(callStatusKey(item)) }}</span
                  >
                  <span
                    v-if="item.status === 'Completed'"
                    class="tabular-nums"
                    >{{ callDuration(item.duration) }}</span
                  >
                  <span
                    v-if="item.has_recording"
                    class="inline-flex items-center gap-1 text-ink-gray-7"
                    ><FeatherIcon
                      name="headphones"
                      class="size-3.5"
                      aria-hidden="true"
                    />{{ __('Recording') }}</span
                  >
                </span>
                <span
                  v-if="item.outcome || item.unhandled_missed || item.due_tasks"
                  class="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-sm text-ink-gray-7"
                >
                  <span v-if="item.outcome">{{ __(item.outcome) }}</span>
                  <span v-if="item.unhandled_missed">{{
                    __('Unhandled missed call')
                  }}</span>
                  <span v-if="item.overdue_tasks" class="text-ink-red-4"
                    >{{ __('Overdue tasks') }}: {{ item.overdue_tasks }}</span
                  >
                  <span v-else-if="item.due_tasks"
                    >{{ __('Tasks due today') }}: {{ item.due_tasks }}</span
                  >
                </span>
              </span>
            </button>
          </div>
          <p
            v-if="historyStatus?.enabled"
            class="px-4 pt-3 text-sm text-ink-gray-6 sm:px-6"
            role="status"
            data-testid="history-sync-status"
          >
            {{
              historyStatus.error
                ? __(historyStatus.error)
                : historyStatus.catching_up
                  ? __('Server history recovery is in progress…')
                  : historyStatus.last_success
                    ? __('Server history updated at {0}', [
                        formatDate(
                          historyStatus.last_success,
                          'DD.MM.YYYY HH:mm',
                        ),
                      ])
                    : __('Server history synchronization is starting…')
            }}
          </p>
          <div class="flex items-center justify-center gap-3 p-4">
            <Button
              v-if="hasMore"
              :label="__('Load more calls')"
              :loading="loading"
              @click="loadCalls(true)"
            />
            <span v-else class="text-sm text-ink-gray-6">{{
              __('All matching calls are shown')
            }}</span>
          </div>
        </div>
      </section>
      <aside
        v-if="selectedName || preferredIntegration !== 'exolve'"
        class="min-h-0 w-full shrink-0 flex-col overflow-y-auto border-l border-outline-gray-2 bg-surface-base lg:relative lg:w-[370px] xl:w-[410px]"
        :class="
          panelOpen
            ? 'absolute inset-0 z-10 flex lg:inset-auto'
            : 'hidden lg:flex'
        "
        :aria-label="selectedName ? __('Call details') : __('Dial a number')"
      >
        <div
          class="flex shrink-0 items-center justify-between border-b border-outline-gray-1 px-4 py-2 lg:hidden"
        >
          <Button
            :label="__('Back to calls')"
            icon-left="lucide-arrow-left"
            class="min-h-11"
            variant="ghost"
            @click="closePanel"
          />
        </div>
        <WorkspaceDialer
          v-if="!selectedName"
          :enabled="isAnyEnabled"
          @call="openCall"
        />
        <div
          v-else-if="detailLoading"
          class="flex flex-1 items-center justify-center gap-2 p-6 text-sm text-ink-gray-6"
          role="status"
        >
          <LoadingIndicator class="size-5" />{{ __('Loading call details…') }}
        </div>
        <div v-else-if="detailError" class="space-y-4 p-6" role="alert">
          <p class="text-base text-ink-gray-7">{{ detailError }}</p>
          <Button :label="__('Retry')" @click="loadDetail(selectedName)" />
        </div>
        <div v-else-if="detail" class="space-y-6 p-5 sm:p-6">
          <div>
            <p class="mb-2 text-sm text-ink-gray-6">
              {{ __(detail.type) }} · {{ __(callStatusKey(detail)) }}
            </p>
            <h2 class="break-words text-xl font-semibold text-ink-gray-9">
              {{
                detail.client_name ||
                displayPhone(detail.number) ||
                __('Unknown number')
              }}
            </h2>
            <p class="mt-2 text-base tabular-nums text-ink-gray-6">
              {{ displayPhone(detail.number) }}
            </p>
            <Button
              :label="__('Call customer')"
              icon-left="lucide-phone"
              variant="solid"
              class="mt-4 min-h-11 w-full"
              :disabled="
                !isAnyEnabled || !dialNumber(detail.number) || hasActiveCall
              "
              @click="openCall(detail.number, detail.references)"
            />
          </div>
          <WorkspaceRecording
            :key="detail.name"
            ref="recording"
            :src="detail.recording_path || ''"
            :state="detail.recording_state || 'unavailable'"
          />
          <CallInsightsPanel
            :key="'ai-' + detail.name"
            :name="detail.name"
            :references="detail.references"
            :seekable="Boolean(detail.recording_path)"
            @seek="seekTranscript"
          />
          <CallOutcomePanel :key="detail.name" :name="detail.name" />
          <CallbackProof
            :key="'callback-' + detail.name + ':' + proofRevision"
            :name="detail.name"
          />
          <Button
            v-if="detail.has_conversation"
            :label="__('Open conversation notes and tasks')"
            icon-left="lucide-file-text"
            class="min-h-11 w-full"
            @click="openConversation"
          />
          <dl
            class="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-3 text-sm"
          >
            <dt class="text-ink-gray-6">{{ __('Date and time') }}</dt>
            <dd class="text-right text-ink-gray-9">
              {{ callCalendarDate(detail.timestamp, locale) }},
              {{ formatDate(detail.timestamp, 'HH:mm') }}
            </dd>
            <dt class="text-ink-gray-6">{{ __('Duration') }}</dt>
            <dd class="text-right tabular-nums text-ink-gray-9">
              {{ callDuration(detail.duration) }}
            </dd>
            <dt class="text-ink-gray-6">{{ __('Employee') }}</dt>
            <dd class="break-words text-right text-ink-gray-9">
              {{ detail.agent || __('Unassigned') }}
            </dd>
            <dt class="text-ink-gray-6">{{ __('Phone line') }}</dt>
            <dd class="break-words text-right tabular-nums text-ink-gray-9">
              {{ displayPhone(detail.line) || '—' }}
            </dd>
          </dl>
          <section v-if="detail.references.length" class="space-y-3">
            <h3 class="text-base-medium text-ink-gray-9">
              {{ __('Customer context') }}
            </h3>
            <RouterLink
              v-for="reference in detail.references"
              :key="reference.doctype + reference.name"
              :to="reference.path.replace(/^\/crm/, '')"
              class="flex min-h-14 items-center gap-3 rounded-lg border border-outline-gray-2 px-3 py-3 hover:bg-surface-gray-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ink-gray-9"
            >
              <FeatherIcon
                :name="reference.doctype === 'CRM Deal' ? 'zap' : 'user'"
                class="size-4 shrink-0 text-ink-gray-6"
                aria-hidden="true"
              />
              <span class="min-w-0 flex-1"
                ><span class="block text-xs text-ink-gray-6">{{
                  __(customerTypeKey(reference.doctype))
                }}</span
                ><span class="mt-1 block truncate text-base text-ink-gray-9">{{
                  reference.title
                }}</span></span
              >
              <FeatherIcon
                name="arrow-up-right"
                class="size-4 text-ink-gray-6"
                aria-hidden="true"
              />
            </RouterLink>
          </section>
          <p v-else class="text-sm leading-5 text-ink-gray-6">
            {{
              __('This call is not linked to an accessible customer record.')
            }}
          </p>
          <Button
            :label="__('Notes, tasks and more')"
            icon-left="lucide-panel-top-open"
            class="min-h-11 w-full"
            @click="openFullDetails"
          />
        </div>
      </aside>
    </div>
  </div>
  <CallLogDetailModal v-model="showFullDetails" v-model:callLog="fullCall" />
</template>
<script setup>
import LayoutHeader from '@/components/LayoutHeader.vue'
import CallInsightsPanel from '@/components/Telephony/CallInsightsPanel.vue'
import TelephonyAnalytics from '@/components/Telephony/TelephonyAnalytics.vue'
import CallbackProof from '@/components/Telephony/CallbackProof.vue'
import WorkspaceDialer from '@/components/Telephony/WorkspaceDialer.vue'
import WorkspaceRecording from '@/components/Telephony/WorkspaceRecording.vue'
import CallOutcomePanel from '@/components/Telephony/CallOutcomePanel.vue'
import CallLogDetailModal from '@/components/Modals/CallLogDetailModal.vue'
import {
  Button,
  FormControl,
  FeatherIcon,
  LoadingIndicator,
  call,
  createResource,
} from 'frappe-ui'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDebounceFn, useEventListener } from '@vueuse/core'
import { hasActiveCall, useTelephony } from '@/composables/telephony'
import { globalStore } from '@/stores/global'
import { formatDate } from '@/utils'
import { callOutcomes } from '@/utils/callFollowups'
import { sessionStore } from '@/stores/session'
import {
  callDuration,
  callCalendarDate,
  customerTypeKey,
  callStatusKey,
  dialNumber,
  displayPhone,
  groupCalls,
  isMissedCall,
  mergeCalls,
} from '@/utils/telephony'

const route = useRoute(),
  router = useRouter()
const { prepareCall } = globalStore()
const { isAnyEnabled, preferredIntegration, isEnabled } = useTelephony()
const analyticsOpen = computed(() => route.query.pane === 'analytics')
const analyticsFilters = computed(() => ({
  search: analyticsSearch.value,
  period: period.value,
  employee: employee.value === '@me' ? session.user : employee.value,
  line: line.value,
  outcome: outcome.value,
  view: view.value,
}))
const proofRevision = ref(0),
  analyticsRevision = ref(0),
  analyticsSearch = ref('')
function toggleAnalytics() {
  const query = { ...route.query }
  if (analyticsOpen.value) delete query.pane
  else query.pane = 'analytics'
  router.replace({ query })
}
function selectAnalyticsEmployee(value) {
  employee.value = value
  toggleAnalytics()
}
function seekTranscript(seconds) {
  recording.value?.seekTo(seconds)
}
const historyStatus = ref(null)
async function loadHistoryStatus() {
  if (!isEnabled('exolve')) return
  try {
    const data = await call('crm.integrations.exolve.history.status')
    if (!disposed) historyStatus.value = data
  } catch {
    /* Configuration access is kept in the existing settings UI. */
  }
}
const search = ref(''),
  period = ref('30'),
  employee = ref(''),
  line = ref(''),
  outcome = ref(''),
  view = ref('all')
const directories = ref({ employees: [], lines: [] })
const session = sessionStore()
const calls = ref([]),
  hasMore = ref(false),
  loading = ref(false),
  listError = ref('')
const selectedName = computed(() =>
  typeof route.query.open === 'string' ? route.query.open : '',
)
const panelOpen = ref(Boolean(selectedName.value))
const detail = ref(null),
  detailLoading = ref(false),
  detailError = ref(''),
  recording = ref(null)
const showFullDetails = ref(false),
  fullCall = ref({})
let dialerRequested = false
let listRequest = 0,
  detailRequest = 0,
  nextOffset = 0,
  disposed = false
const grouped = computed(() => groupCalls(calls.value))
const locale =
  globalThis.frappe?.boot?.lang ||
  window.lang ||
  document.documentElement.lang ||
  navigator.language
const calendar = ref({ today: '', yesterday: '' })
const tabs = computed(() => [
  { value: 'all', label: __('All calls') },
  { value: 'attention', label: __('Needs attention') },
  { value: 'missed', label: __('Missed calls') },
  { value: 'incoming', label: __('Incoming calls') },
  { value: 'outgoing', label: __('Outgoing calls') },
])
const periodOptions = computed(() => [
  { value: 'today', label: __('Today') },
  { value: '7', label: __('Last 7 days') },
  { value: '30', label: __('Last 30 days') },
  { value: 'all', label: __('All time') },
])
const employeeOptions = computed(() => [
  { value: '', label: __('All employees') },
  { value: '@me', label: __('My calls') },
  ...directories.value.employees,
])
const lineOptions = computed(() => [
  { value: '', label: __('All lines') },
  ...directories.value.lines.map((value) => ({
    value,
    label: displayPhone(value),
  })),
])
const outcomeOptions = computed(() => [
  { value: '', label: __('All outcomes') },
  { value: 'unprocessed', label: __('No outcome yet') },
  ...callOutcomes.map((value) => ({ value, label: __(value) })),
])
async function loadDirectories() {
  try {
    const result = await call('crm.api.telephony.get_filter_options')
    if (!disposed) directories.value = result
  } catch {
    /* The journal retains the all/mine filters on directory failure. */
  }
}

async function loadCalls(append = false) {
  const version = ++listRequest
  loading.value = true
  listError.value = ''
  if (!append) {
    calls.value = []
    nextOffset = 0
  }
  try {
    const data = await call('crm.api.telephony.get_calls', {
      search: search.value,
      view: view.value,
      period: period.value,
      employee: employee.value === '@me' ? session.user : employee.value,
      line: line.value,
      outcome: outcome.value,
      offset: append ? nextOffset : 0,
    })
    if (disposed || version !== listRequest) return
    calls.value = append ? mergeCalls(calls.value, data.calls) : data.calls
    hasMore.value = data.has_more
    calendar.value = { today: data.today, yesterday: data.yesterday }
    nextOffset = data.next_offset
  } catch {
    if (disposed || version !== listRequest) return
    calls.value = []
    hasMore.value = false
    detail.value = null
    detailRequest++
    recording.value?.pause()
    showFullDetails.value = false
    fullCall.value = {}
    if (selectedName.value)
      detailError.value = __(
        'This call is unavailable or you no longer have access.',
      )
    listError.value = __(
      'Could not load calls. Check your access and connection.',
    )
  } finally {
    if (version === listRequest) loading.value = false
  }
}
async function loadDetail(name, quiet = false) {
  const version = ++detailRequest
  if (!quiet) recording.value?.pause()
  if (!quiet || detail.value?.name !== name) detail.value = null
  detailError.value = ''
  if (!name) {
    detailLoading.value = false
    return
  }
  detailLoading.value = !quiet
  try {
    const data = await call('crm.api.telephony.get_call', { name })
    if (!disposed && version === detailRequest) detail.value = data
  } catch {
    if (!disposed && version === detailRequest) {
      recording.value?.pause()
      detail.value = null
      detailError.value = __(
        'This call is unavailable or you no longer have access.',
      )
    }
  } finally {
    if (version === detailRequest) detailLoading.value = false
  }
}
function selectCall(name) {
  dialerRequested = false
  panelOpen.value = true
  router.push({ query: { ...route.query, open: name } })
}
function closePanel() {
  dialerRequested = false
  panelOpen.value = false
  const query = { ...route.query }
  delete query.open
  router.replace({ query })
}
function showDialer() {
  if (preferredIntegration.value === 'exolve') {
    openCall('')
    return
  }
  dialerRequested = true
  panelOpen.value = true
  const query = { ...route.query }
  delete query.open
  router.replace({ query })
}
function openCall(number, context = null) {
  recording.value?.pause()
  prepareCall(number, context)
}
function openConversation() {
  recording.value?.pause()
  window.dispatchEvent(
    new CustomEvent('crm-open-call-conversation', {
      detail: { callLog: selectedName.value },
    }),
  )
}
function openFullDetails() {
  recording.value?.pause()
  fullCall.value = createResource({
    url: 'crm.fcrm.doctype.crm_call_log.crm_call_log.get_call_log',
    params: { name: selectedName.value },
    auto: true,
  })
  showFullDetails.value = true
}
function resetFilters() {
  search.value = ''
  period.value = 'all'
  employee.value = ''
  line.value = ''
  outcome.value = ''
  view.value = 'all'
}
function refresh() {
  analyticsRevision.value++
  loadHistoryStatus()
  loadCalls()
  if (selectedName.value) loadDetail(selectedName.value, true)
}
function workUpdated() {
  analyticsRevision.value++
  proofRevision.value++
  loadCalls()
  if (selectedName.value) loadDetail(selectedName.value, true)
}
function dayLabel(date) {
  if (date === calendar.value.today) return __('Today')
  if (date === calendar.value.yesterday) return __('Yesterday')
  return callCalendarDate(date, locale) || __('Date unavailable')
}
const delayedSearch = useDebounceFn(() => {
  analyticsSearch.value = search.value
  loadCalls()
}, 250)
watch(search, () => {
  listRequest++
  delayedSearch()
})
watch([period, employee, line, outcome, view], () => loadCalls())
watch(
  selectedName,
  (name) => {
    panelOpen.value = Boolean(name) || dialerRequested
    loadDetail(name)
  },
  { immediate: true },
)
useEventListener(window, 'crm-exolve-calls-updated', refresh)
useEventListener(window, 'crm-exolve-history-settings-updated', refresh)
useEventListener(window, 'crm-call-work-updated', workUpdated)
useEventListener(window, 'focus', refresh)
const historyRefresh = setInterval(() => {
  if (document.visibilityState === 'visible' && isEnabled('exolve')) refresh()
}, 30000)
watch(
  () => isEnabled('exolve'),
  () => loadHistoryStatus(),
)
onBeforeUnmount(() => {
  clearInterval(historyRefresh)
  disposed = true
  listRequest++
  detailRequest++
  recording.value?.pause()
})
loadCalls()
loadHistoryStatus()
loadDirectories()
</script>
<style scoped>
/* Keep native controls on the same semantic surfaces as the workspace, including
   when the linked UI package also supplies static palette utility classes. */
[data-testid='telephony-workspace'] :deep(input),
[data-testid='telephony-workspace'] :deep([role='combobox']) {
  color: var(--ink-gray-9);
  background-color: var(--surface-gray-2);
}
.telephony-secondary {
  color: var(--ink-gray-9);
}
.telephony-secondary:hover {
  background-color: var(--surface-gray-2);
}
@media (max-width: 767px) {
  [data-testid='telephony-workspace'] :deep(input),
  [data-testid='telephony-workspace'] :deep([role='combobox']) {
    min-height: 44px;
  }
}
</style>
