<template>
  <div class="relative">
    <FormControl
      v-model="input"
      type="text"
      :label="__('Number or customer name')"
      :placeholder="__('Phone number or name')"
      autocomplete="off"
      @keydown.esc="dismiss"
    />
    <p v-if="searching" class="mt-1 text-sm text-ink-gray-6" role="status">
      {{ __('Searching customers…') }}
    </p>
    <p v-if="searchError" role="alert" class="mt-1 text-sm text-ink-red-4">
      {{ searchError }}
    </p>
    <ul
      v-if="candidates.length"
      data-testid="call-recipient-results"
      :aria-label="__('Customer search results')"
      class="absolute inset-x-0 top-full z-20 mt-1 max-h-60 overflow-y-auto rounded-lg border border-outline-gray-2 bg-surface-elevation-1 shadow-lg"
    >
      <li v-for="item in candidates" :key="item.doctype + ':' + item.name">
        <button
          type="button"
          class="block min-h-14 w-full px-3 py-2 text-left hover:bg-surface-gray-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ink-gray-9"
          @click="choose(item)"
        >
          <span class="block truncate text-base-medium text-ink-gray-9">{{
            item.title
          }}</span>
          <span class="mt-1 block text-sm text-ink-gray-6"
            >{{ __(customerTypeKey(item.doctype)) }} ·
            {{ displayPhone(item.number) }}</span
          >
        </button>
      </li>
    </ul>
  </div>
</template>
<script setup>
import { FormControl, call } from 'frappe-ui'
import { onBeforeUnmount, ref, watch } from 'vue'
import { customerTypeKey, displayPhone } from '@/utils/telephony'
const input = defineModel({ type: String, default: '' })
const emit = defineEmits(['select'])
const candidates = ref([]),
  searching = ref(false),
  searchError = ref('')
let timer,
  request = 0,
  chosen = ''
function clear() {
  clearTimeout(timer)
  request++
  candidates.value = []
  searching.value = false
  searchError.value = ''
}
function dismiss(event) {
  if (candidates.value.length || searching.value) {
    event.stopPropagation()
    clear()
  }
}
watch(input, (value) => {
  clear()
  if (value === chosen) {
    chosen = ''
    return
  }
  if (value.trim().length < 2) return
  const version = request
  timer = setTimeout(async () => {
    searching.value = true
    try {
      const rows = await call('crm.api.telephony.search_customers', {
        search: value,
      })
      if (version === request) candidates.value = rows
    } catch {
      if (version === request)
        searchError.value = __(
          'Could not search customers. Enter a phone number instead.',
        )
    } finally {
      if (version === request) searching.value = false
    }
  }, 250)
})
function choose(item) {
  clear()
  chosen = item.number
  input.value = item.number
  emit('select', item)
}
onBeforeUnmount(clear)
</script>
