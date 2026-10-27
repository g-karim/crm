<template>
  <section
    class="call-work flex min-w-0 flex-col overflow-y-auto text-ink-gray-9 lg:overflow-hidden"
    data-testid="call-work-panel"
    :data-work-id="work.id"
  >
    <div
      class="shrink-0 border-b border-outline-gray-2 py-4 lg:max-h-[40dvh] lg:overflow-y-auto"
      data-testid="call-customer"
    >
      <div class="flex items-start justify-between gap-3">
        <div v-if="work.context" class="flex min-w-0 items-center gap-3">
          <span
            class="grid size-10 shrink-0 place-items-center rounded-full bg-surface-gray-2"
            aria-hidden="true"
          >
            <span class="lucide-contact-round size-5 text-ink-gray-6" />
          </span>
          <div class="min-w-0">
            <p class="mb-1 text-sm text-ink-gray-6">
              {{ __('Save to') }} ·
              {{ work.context.kind === 'lead' ? __('Lead') : __('Deal') }}
            </p>
            <RouterLink
              :to="work.context.path"
              class="break-words text-base font-medium hover:underline underline-offset-2"
              @click="emit('navigate')"
              >{{ work.context.title }}</RouterLink
            >
          </div>
          <Button
            v-if="!locked"
            :label="__('Change customer record')"
            variant="ghost"
            class="min-h-11"
            @click="picker = !picker"
          />
        </div>
        <div v-else>
          <h2 class="text-base font-semibold">{{ __('Customer record') }}</h2>
          <p
            v-if="!work.resolving"
            class="mt-1 text-sm leading-5 text-ink-gray-6"
          >
            {{ __('Choose the lead or deal for notes and tasks.') }}
          </p>
        </div>
        <Button
          v-if="!active && store.works.length > 1"
          icon="lucide-history"
          :aria-label="__('Previous conversations')"
          :tooltip="__('Previous conversations')"
          :aria-expanded="showHistory"
          class="min-h-11 min-w-11 shrink-0"
          variant="ghost"
          @click="showHistory = !showHistory"
        />
      </div>
      <FormControl
        v-if="showHistory && !active && store.works.length > 1"
        v-model="store.currentId"
        type="select"
        class="mt-3"
        :label="__('Conversation drafts')"
        :options="history"
      />
      <Button
        v-if="showHistory && !active && store.hasMoreDrafts"
        :label="__('Load older conversation drafts')"
        class="mt-2 min-h-11"
        :loading="store.restoring"
        @click="store.restore(true)"
      />
      <p
        v-if="work.resolving"
        role="status"
        class="mt-2 text-sm text-ink-gray-6"
      >
        {{ __('Loading customer context…') }}
      </p>
      <p v-if="work.contextError" role="alert" class="mt-2 text-sm">
        {{ __(work.contextError) }}
      </p>
      <div v-if="!work.context && work.candidates.length" class="mt-3">
        <div class="grid gap-2 sm:grid-cols-2">
          <button
            v-for="item in work.candidates"
            :key="item.kind + item.name"
            type="button"
            class="flex min-h-14 items-center justify-between gap-3 rounded-lg border border-outline-gray-2 px-3 py-3 text-left text-base hover:border-outline-gray-4 hover:bg-surface-gray-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ink-gray-9"
            @click="choose(item)"
          >
            <span class="min-w-0 break-words"
              >{{ item.kind === 'lead' ? __('Lead') : __('Deal') }} ·
              {{ item.title }}</span
            >
            <span
              class="lucide-chevron-right size-4 shrink-0 text-ink-gray-5"
              aria-hidden="true"
            />
          </button>
        </div>
        <Button
          :label="__('Find another lead or deal')"
          variant="ghost"
          class="mt-2 min-h-10"
          @click="picker = !picker"
        />
      </div>
      <div v-if="showSearch" class="mt-3 space-y-3">
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-[8rem_1fr]">
          <FormControl
            v-model="kind"
            type="select"
            :label="__('Record type')"
            :options="[
              { value: 'lead', label: __('Lead') },
              { value: 'deal', label: __('Deal') },
            ]"
          />
          <FormControl
            v-model="query"
            type="search"
            :label="__('Find a lead or deal')"
          />
        </div>
        <p v-if="searching" role="status" class="text-sm text-ink-gray-6">
          {{ __('Searching…') }}
        </p>
        <div
          v-else-if="results.length"
          class="max-h-40 overflow-y-auto rounded border border-outline-gray-2 bg-surface-base"
        >
          <button
            v-for="item in results"
            :key="item.kind + item.name"
            type="button"
            class="block min-h-11 w-full border-b border-outline-gray-1 px-3 py-2 text-left text-base last:border-0 hover:bg-surface-gray-2"
            @click="choose(item)"
          >
            {{ item.title }}
          </button>
        </div>
        <p v-else class="text-sm text-ink-gray-6">
          {{ __('No matching customer records.') }}
        </p>
      </div>
      <p
        v-if="work.context && !options && !error"
        role="status"
        class="mt-2 text-sm text-ink-gray-6"
      >
        {{ __('Checking saving permissions…') }}
      </p>
      <p v-if="error" role="alert" class="mt-2 text-sm">{{ __(error) }}</p>
      <Button
        v-if="error"
        :label="__('Retry')"
        class="mt-2"
        @click="loadOptions"
      />
    </div>
    <ConversationPersistence
      :work="work"
      :active="active"
      class="shrink-0 border-b border-outline-gray-2 pb-2"
      @navigate="emit('navigate')"
    />
    <p
      v-if="!active && work.started && !work.call_log"
      class="shrink-0 py-2 text-sm leading-5 text-ink-gray-6"
    >
      {{
        __(
          'To save the outcome or schedule a callback, link this conversation to its exact call in history above.',
        )
      }}
    </p>
    <div
      v-if="!active && work.call_log"
      class="max-h-[35dvh] shrink-0 overflow-y-auto border-b border-outline-gray-2 py-4"
    >
      <CallOutcomePanel
        :key="work.call_log"
        :name="work.call_log"
        :preferred-context="work.context"
        :show-materials="false"
      />
    </div>
    <div
      class="flex shrink-0 gap-2 border-b border-outline-gray-2 py-2 lg:hidden"
    >
      <Button
        :label="__('Note')"
        icon-left="lucide-file-text"
        variant="ghost"
        class="min-h-11 flex-1"
        :class="mobilePane === 'note' ? 'bg-surface-gray-2' : ''"
        :aria-pressed="mobilePane === 'note'"
        @click="mobilePane = 'note'"
      />
      <Button
        :label="`${__('Tasks')}${work.tasks.length ? ` (${work.tasks.length})` : ''}`"
        icon-left="lucide-list-checks"
        variant="ghost"
        class="min-h-11 flex-1"
        :class="mobilePane === 'tasks' ? 'bg-surface-gray-2' : ''"
        :aria-pressed="mobilePane === 'tasks'"
        @click="mobilePane = 'tasks'"
      />
    </div>
    <div
      class="shrink-0 lg:grid lg:min-h-0 lg:flex-1 lg:grid-cols-[minmax(0,1fr)_22rem] lg:overflow-hidden"
    >
      <div
        class="py-5 lg:flex lg:min-h-0 lg:flex-col lg:overflow-y-auto lg:pr-6"
        :class="mobilePane !== 'note' ? 'hidden' : ''"
      >
        <CallWorkItem
          :work="work"
          :item="work.note"
          :options="options"
          class="lg:flex-1"
        />
      </div>
      <aside
        class="border-t border-outline-gray-2 py-5 lg:flex lg:min-h-0 lg:flex-col lg:border-l lg:border-t-0 lg:pl-6"
        :class="mobilePane !== 'tasks' ? 'hidden' : ''"
        :aria-label="__('Tasks')"
      >
        <div class="mb-4 flex shrink-0 items-center justify-between gap-3">
          <h2 class="text-base font-semibold">
            {{ __('Tasks')
            }}<span
              v-if="work.tasks.length"
              class="ml-2 text-sm font-normal text-ink-gray-5"
              >{{ work.tasks.length }}</span
            >
          </h2>
          <Button
            :label="__('Add task')"
            icon-left="lucide-plus"
            class="min-h-11"
            @click="addTask"
          />
        </div>
        <div class="space-y-3 lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:pr-1">
          <div
            v-if="!work.tasks.length"
            class="rounded-lg border border-dashed border-outline-gray-2 p-4 text-sm leading-6 text-ink-gray-6"
          >
            <p class="font-medium text-ink-gray-8">
              {{ __('Agreed on a next step?') }}
            </p>
            <p class="mt-1">
              {{ __('Add a task and a deadline so nothing is forgotten.') }}
            </p>
          </div>
          <CallWorkItem
            v-for="item in work.tasks"
            :key="item.key"
            :work="work"
            :item="item"
            :options="options"
          />
        </div>
      </aside>
    </div>
  </section>
</template>
<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Button, FormControl, call } from 'frappe-ui'
import CallWorkItem from './CallWorkItem.vue'
import ConversationPersistence from './ConversationPersistence.vue'
import CallOutcomePanel from './CallOutcomePanel.vue'
import { callWorkStore } from '@/stores/callWork'
import { sessionStore } from '@/stores/session'
import { contextLocked } from '@/utils/callWork'

const props = defineProps({
  work: { type: Object, required: true },
  active: { type: Boolean, default: false },
})
const emit = defineEmits(['navigate', 'select-work'])
const store = callWorkStore(),
  session = sessionStore()
const kind = ref('lead'),
  query = ref(''),
  picker = ref(false),
  results = ref([]),
  searching = ref(false),
  options = ref(null),
  error = ref('')
let searchTimer,
  searchVersion = 0,
  optionsVersion = 0
const showHistory = ref(false)
const mobilePane = ref('note')
function addTask() {
  store.addTask(props.work)
  mobilePane.value = 'tasks'
}
const locked = computed(() => contextLocked(props.work))
watch(
  () => props.active,
  (active) => {
    if (active) showHistory.value = false
  },
)
const showSearch = computed(
  () =>
    !locked.value &&
    (picker.value ||
      (!props.work.context &&
        !props.work.candidates.length &&
        !props.work.resolving)),
)
const history = computed(() =>
  store.works.map((work) => ({
    value: work.id,
    label: `${work.context?.title || work.number || __('Unknown number')} · ${new Date(work.created).toLocaleString()}`,
  })),
)
function choose(context) {
  store.chooseContext(props.work, context)
  picker.value = false
}
async function loadOptions() {
  const context = props.work.context,
    version = ++optionsVersion
  options.value = null
  error.value = ''
  if (!context) return
  try {
    const data = await call('crm.api.call_work.options', {
      kind: context.kind,
      name: context.name,
    })
    if (version !== optionsVersion) return
    if (data.viewer !== session.user) throw new Error('Account changed')
    options.value = data
  } catch {
    if (version === optionsVersion)
      error.value =
        'Could not load saving options. Check customer access and try again.'
  }
}
function search() {
  clearTimeout(searchTimer)
  const version = ++searchVersion
  results.value = []
  if (!showSearch.value) {
    searching.value = false
    return
  }
  searching.value = true
  searchTimer = setTimeout(async () => {
    try {
      const data = await call('crm.api.call_work.search_contexts', {
        kind: kind.value,
        query: query.value,
      })
      if (version === searchVersion) results.value = data
    } catch {
      if (version === searchVersion)
        error.value =
          'Could not read the customer context. Choose an accessible lead or deal.'
    } finally {
      if (version === searchVersion) searching.value = false
    }
  }, 250)
}
watch(
  () => props.work.id,
  () => {
    mobilePane.value = 'note'
    picker.value = false
    query.value = ''
    kind.value = 'lead'
    search()
  },
)
watch(
  () => props.work.context,
  () => {
    loadOptions()
    search()
  },
  { immediate: true },
)
watch([query, kind, showSearch], search)
watch(
  () => store.currentId,
  () => emit('select-work', store.current),
)
onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  searchVersion++
  optionsVersion++
})
</script>
<style scoped>
.call-work :deep(input),
.call-work :deep(textarea:not([id^='call-note-'])),
.call-work :deep(select) {
  color: var(--ink-gray-9);
  background-color: var(--surface-gray-2);
}
</style>
