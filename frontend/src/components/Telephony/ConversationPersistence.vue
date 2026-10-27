<template>
  <div class="mt-3 space-y-2" data-testid="conversation-persistence">
    <p v-if="store.restoring" role="status" class="text-sm text-ink-gray-6">
      {{ __('Restoring conversation drafts…') }}
    </p>
    <p v-if="store.restoreError" role="alert" class="text-sm text-ink-red-4">
      {{ __(store.restoreError) }}
      <Button :label="__('Retry')" variant="ghost" @click="store.restore()" />
    </p>
    <div
      v-if="work.draft"
      class="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-gray-6"
    >
      <span role="status" :class="work.draft.error ? 'text-ink-red-4' : ''">
        {{
          work.draft.error
            ? __(work.draft.error)
            : work.draft.state === 'saving'
              ? __('Saving conversation draft…')
              : synchronized
                ? __('Conversation draft saved on the server')
                : __('Conversation changes are not saved yet')
        }}
      </span>
      <Button
        v-if="work.draft.state === 'error'"
        :label="__('Retry draft saving')"
        variant="ghost"
        class="min-h-11"
        @click="store.retryDraft(work)"
      />
      <Button
        v-if="work.draft.state === 'conflict'"
        :label="__('Load saved conversation draft')"
        variant="ghost"
        class="min-h-11"
        @click="store.reloadDraft(work)"
      />
      <Button
        v-if="work.draft.backup"
        :label="__('Restore my conversation changes')"
        variant="ghost"
        class="min-h-11"
        @click="store.restoreLocalDraft(work)"
      />
    </div>
    <p v-if="work.restored" class="text-sm text-ink-gray-6">
      {{ __('Draft restored. A previous call is not resumed automatically.') }}
    </p>
    <div v-if="!active && (work.started || work.call_log)" class="pt-1">
      <RouterLink
        v-if="work.call_log"
        :to="{ name: 'Telephony', query: { open: work.call_log } }"
        class="inline-flex min-h-11 items-center gap-2 text-sm font-medium text-ink-gray-9 hover:underline"
        @click="emit('navigate')"
        ><span class="lucide-link size-4" aria-hidden="true" />{{
          __('Linked call in history')
        }}</RouterLink
      >
      <Button
        v-else
        :label="__('Link to a call in history')"
        icon-left="lucide-link"
        variant="ghost"
        class="min-h-11"
        :aria-expanded="open"
        @click="openPicker"
      />
      <div
        v-if="open"
        class="mt-2 space-y-3 rounded-lg border border-outline-gray-2 p-3"
      >
        <p class="text-sm leading-5 text-ink-gray-6">
          {{
            __(
              'Choose the exact conversation. Calls are never linked by phone number automatically.',
            )
          }}
        </p>
        <p v-if="loading" role="status" class="text-sm">
          {{ __('Loading calls…') }}
        </p>
        <div
          v-else-if="calls.length"
          class="max-h-48 space-y-1 overflow-y-auto"
          :aria-label="__('Calls to link')"
        >
          <button
            v-for="item in calls"
            :key="item.name"
            :data-call-candidate="item.name"
            type="button"
            :aria-pressed="selected === item.name"
            class="flex min-h-14 w-full items-center justify-between gap-3 rounded-lg border px-3 py-2 text-left text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-ink-gray-9"
            :class="
              selected === item.name
                ? 'border-outline-gray-9 bg-surface-gray-2'
                : 'border-outline-gray-2'
            "
            @click="selected = item.name"
          >
            <span
              >{{ displayPhone(item.number)
              }}<span class="mt-1 block text-ink-gray-6"
                >{{ formatDate(item.timestamp, 'DD.MM.YYYY HH:mm') }} ·
                {{ __(callStatusKey(item)) }} ·
                {{ callDuration(item.duration) }}</span
              ></span
            ><span
              v-if="selected === item.name"
              class="lucide-check size-4 shrink-0"
              aria-hidden="true"
            />
          </button>
        </div>
        <p v-else class="text-sm text-ink-gray-6">
          {{
            __(
              'No matching calls yet. Server synchronization will add completed calls here.',
            )
          }}
        </p>
        <p v-if="error" role="alert" class="text-sm text-ink-red-4">
          {{ error }}
        </p>
        <div class="flex flex-wrap gap-2">
          <Button
            :label="__('Link selected call')"
            variant="solid"
            class="min-h-11"
            :disabled="!selected || loading"
            :loading="saving"
            @click="link"
          /><Button
            :label="__('Refresh calls')"
            class="min-h-11"
            :disabled="saving"
            @click="load"
          /><Button
            :label="__('Cancel')"
            variant="ghost"
            class="min-h-11"
            :disabled="saving"
            @click="open = false"
          />
        </div>
      </div>
    </div>
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Button, call } from 'frappe-ui'
import { callWorkStore } from '@/stores/callWork'
import { sessionStore } from '@/stores/session'
import { formatDate } from '@/utils'
import { draftFingerprint } from '@/utils/callDrafts'
import { callDuration, callStatusKey, displayPhone } from '@/utils/telephony'
const props = defineProps({
  work: { type: Object, required: true },
  active: Boolean,
})
const emit = defineEmits(['navigate'])
const store = callWorkStore()
const session = sessionStore()
const synchronized = computed(
  () => props.work.draft?.acknowledged === draftFingerprint(props.work),
)
const open = ref(false),
  loading = ref(false),
  saving = ref(false),
  calls = ref([]),
  selected = ref(''),
  error = ref('')
let version = 0
async function openPicker() {
  open.value = !open.value
  if (open.value) await load()
}
async function load() {
  const current = ++version,
    work = props.work
  loading.value = true
  error.value = ''
  calls.value = []
  selected.value = ''
  try {
    await store.flushDraft(work)
    const data = await call('crm.api.call_drafts.call_candidates', {
      work_id: work.id,
    })
    if (current === version && data.viewer === session.user)
      calls.value = data.calls
  } catch {
    if (current === version)
      error.value = __('Could not load calls for linking. Try again.')
  } finally {
    if (current === version) loading.value = false
  }
}
async function link() {
  if (!selected.value || saving.value) return
  const work = props.work
  saving.value = true
  error.value = ''
  try {
    await store.linkCall(work, selected.value)
    if (work === props.work) open.value = false
  } catch {
    if (work === props.work)
      error.value = __(
        'Could not link this call. Check access or refresh the conversation draft.',
      )
  } finally {
    saving.value = false
  }
}
watch([() => props.work.id, () => props.active], () => {
  version++
  open.value = false
  loading.value = false
  calls.value = []
})
onBeforeUnmount(() => {
  version++
})
</script>
