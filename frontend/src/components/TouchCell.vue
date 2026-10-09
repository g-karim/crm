<template>
  <Popover placement="bottom-end">
    <template #target="{ togglePopover }">
      <button
        type="button"
        class="truncate text-left text-base hover:underline"
        :title="item?.label"
        :aria-label="__('Last Touch')"
        @click.stop.prevent="open(togglePopover)"
      >
        {{ item?.timeAgo || '—' }}
      </button>
    </template>
    <template #body>
      <div
        class="m-2 w-72 space-y-3 rounded-lg border border-outline-gray-1 bg-surface-elevation-2 p-4 shadow-xl"
        @click.stop
      >
        <h3 class="text-base-medium">{{ __('Last Touch') }}</h3>
        <LoadingIndicator v-if="loading" class="size-5" />
        <template v-else-if="reason">
          <p class="text-p-sm text-ink-gray-5">{{ formatDate(reason.date) }}</p>
          <ul class="space-y-2 text-p-base">
            <li v-for="label in reason.reasons" :key="label">{{ label }}</li>
          </ul>
          <a
            v-if="reason.source"
            :href="reason.source.url"
            class="block text-p-sm text-ink-blue-3 underline"
            >{{ reason.source.label }}</a
          >
        </template>
        <template v-else-if="error"
          ><ErrorMessage :message="error" /><Button
            :label="__('Retry')"
            @click="load"
        /></template>
      </div>
    </template>
  </Popover>
</template>
<script setup>
import { ref, watch } from 'vue'
import { call, ErrorMessage, LoadingIndicator, Popover } from 'frappe-ui'
import { formatDate } from '@/utils'
import { withTouchTimeout } from '@/utils/touchTracking'
const props = defineProps({
  doctype: { type: String, required: true },
  name: { type: [String, Number], required: true },
  item: { type: Object, default: () => ({}) },
})
const reason = ref(null)
const error = ref('')
const loading = ref(false)
let generation = 0
watch(
  () => [props.doctype, props.name, props.item?.value],
  () => {
    generation++
    reason.value = null
    loading.value = false
    error.value = ''
  },
)
function open(togglePopover) {
  togglePopover()
  load()
}
async function load() {
  if (reason.value || loading.value) return
  const current = ++generation
  loading.value = true
  error.value = ''
  try {
    const result = await withTouchTimeout(() =>
      call('crm.touch_tracking_ui.get_reason', {
        doctype: props.doctype,
        name: String(props.name),
      }),
    )
    if (current === generation) reason.value = result
  } catch (err) {
    if (current === generation)
      error.value = __(
        err.messages?.[0] ||
          err.message ||
          'Could not load interaction details',
      )
  } finally {
    if (current === generation) loading.value = false
  }
}
</script>
