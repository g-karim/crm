<template>
  <div class="p-5 sm:p-6">
    <div class="mb-6">
      <h2 class="text-xl font-semibold text-ink-gray-9">
        {{ __('Dial a number') }}
      </h2>
      <p class="mt-2 text-sm leading-5 text-ink-gray-6">
        {{ __('Find a customer or enter a phone number.') }}
      </p>
    </div>
    <form class="space-y-4" @submit.prevent="openCall">
      <FormControl
        v-model="input"
        type="text"
        :label="__('Number or customer name')"
        :placeholder="__('Phone number or name')"
        autocomplete="off"
      />
      <p v-if="searching" class="text-sm text-ink-gray-6" role="status">
        {{ __('Searching customers…') }}
      </p>
      <p v-if="searchError" role="alert" class="text-sm text-ink-red-4">
        {{ searchError }}
      </p>
      <div
        v-if="candidates.length"
        class="max-h-60 overflow-y-auto rounded-lg border border-outline-gray-2"
      >
        <button
          v-for="item in candidates"
          :key="item.doctype + ':' + item.name"
          type="button"
          class="flex min-h-14 w-full items-center gap-3 border-b border-outline-gray-1 px-3 py-2 text-left last:border-0 hover:bg-surface-gray-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ink-gray-9"
          @click="choose(item)"
        >
          <FeatherIcon
            name="user"
            class="size-4 shrink-0 text-ink-gray-5"
            aria-hidden="true"
          />
          <span class="min-w-0 flex-1"
            ><span class="block truncate text-base-medium text-ink-gray-9">{{
              item.title
            }}</span>
            <span class="mt-1 block text-sm text-ink-gray-6"
              >{{ __(customerTypeKey(item.doctype)) }} ·
              {{ displayPhone(item.number) }}</span
            ></span
          >
        </button>
      </div>
      <p v-if="selected" class="text-sm text-ink-gray-6">
        {{ selected.title }}
      </p>
      <div class="grid grid-cols-3 gap-2" :aria-label="__('Dial Pad')">
        <button
          v-for="digit in [
            '1',
            '2',
            '3',
            '4',
            '5',
            '6',
            '7',
            '8',
            '9',
            '+',
            '0',
            'backspace',
          ]"
          :key="digit"
          type="button"
          :aria-label="digit === 'backspace' ? __('Delete digit') : digit"
          class="dialer-key flex min-h-12 items-center justify-center rounded-lg text-xl font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-gray-9"
          @click="press(digit)"
        >
          <FeatherIcon
            v-if="digit === 'backspace'"
            name="delete"
            class="size-5"
            aria-hidden="true"
          />
          <span v-else>{{ digit }}</span>
        </button>
      </div>
      <Button
        :label="__('Open telephony')"
        icon-left="lucide-phone"
        variant="solid"
        class="min-h-11 w-full"
        type="submit"
        :disabled="!enabled || !dialNumber(input) || hasActiveCall"
      />
      <p class="text-sm leading-5 text-ink-gray-6">
        {{
          !enabled
            ? __('Set up telephony to make calls.')
            : hasActiveCall
              ? __('Finish the current call before starting another.')
              : __('Review the number and confirm the call in telephony.')
        }}
      </p>
    </form>
  </div>
</template>
<script setup>
import { Button, FormControl, FeatherIcon, call } from 'frappe-ui'
import { onBeforeUnmount, ref, watch } from 'vue'
import { hasActiveCall } from '@/composables/telephony'
import { customerTypeKey, dialNumber, displayPhone } from '@/utils/telephony'

defineProps({ enabled: { type: Boolean, default: false } })
const emit = defineEmits(['call'])
const input = ref('')
const selected = ref(null)
const candidates = ref([])
const searching = ref(false)
const searchError = ref('')
let timer,
  request = 0
watch(input, (value) => {
  clearTimeout(timer)
  const version = ++request
  candidates.value = []
  searchError.value = ''
  searching.value = false
  if (selected.value?.number !== value) selected.value = null
  if (value.trim().length < 2 || selected.value) return
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
  input.value = item.number
  selected.value = item
  candidates.value = []
}
function press(digit) {
  if (digit === 'backspace') {
    input.value = input.value.slice(0, -1)
    return
  }
  if (!/^[+\d\s().-]*$/.test(input.value)) input.value = ''
  if (digit !== '+' || !input.value) input.value += digit
}
function openCall() {
  if (dialNumber(input.value))
    emit(
      'call',
      dialNumber(input.value),
      selected.value
        ? { doctype: selected.value.doctype, name: selected.value.name }
        : null,
    )
}
onBeforeUnmount(() => {
  request++
  clearTimeout(timer)
})
</script>
<style scoped>
.dialer-key {
  background-color: var(--surface-gray-2);
  color: var(--ink-gray-9);
}
.dialer-key:hover {
  background-color: var(--surface-gray-3);
}
.dialer-key:active {
  background-color: var(--surface-gray-4);
}
</style>
