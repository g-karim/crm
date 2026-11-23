<template>
  <fieldset :disabled="disabled" class="rule-choices space-y-2">
    <legend class="text-base font-medium text-ink-gray-9">{{ label }}</legend>
    <p v-if="help" class="text-sm text-ink-gray-6">{{ help }}</p>
    <input v-if="search" v-model="query" type="search" :aria-label="label" class="min-h-11 w-full rounded border border-outline-gray-3 bg-surface-base px-3 text-base text-ink-gray-9" :placeholder="__('Search')" />
    <p v-if="loading" role="status" class="text-sm text-ink-gray-6">{{ __('Loading…') }}</p>
    <p v-if="error" role="alert" class="text-sm text-ink-red-7">{{ __('Could not load choices. Try another search.') }}</p>
    <div class="grid max-h-52 grid-cols-1 gap-x-5 overflow-auto sm:grid-cols-2">
      <label v-for="item in merged" :key="item.value" class="flex min-h-11 cursor-pointer items-center gap-2 text-base text-ink-gray-9">
        <input type="checkbox" :value="item.value" :checked="modelValue.includes(item.value)" class="size-4 shrink-0 accent-gray-900" @change="toggle(item.value, $event.target.checked)" />
        <span class="min-w-0 break-words">{{ item.label }}</span>
      </label>
    </div>
    <p v-if="!merged.length && !loading && !error" class="text-sm text-ink-gray-6">{{ __('No available choices') }}</p>
  </fieldset>
</template>
<script setup>
import { computed, ref, watch, onBeforeUnmount } from 'vue'
const props = defineProps({ modelValue: { type: Array, default: () => [] }, label: String, help: String,
  options: { type: Array, default: () => [] }, search: Function, disabled: Boolean })
const emit = defineEmits(['update:modelValue'])
const query = ref(''), rows = ref([]), labels = new Map(), loading = ref(false), error = ref(false)
let timer, ticket = 0
const merged = computed(() => {
  const values = [...props.options, ...rows.value].map(item => typeof item === 'string' ? { value: item, label: item } : item)
  values.forEach(item => labels.set(item.value, item.label))
  return [...new Map([...props.modelValue.map(value => ({ value, label: labels.get(value) || value })), ...values].map(item => [item.value, item])).values()]
})
function toggle(value, checked) { emit('update:modelValue', checked ? [...new Set([...props.modelValue, value])] : props.modelValue.filter(item => item !== value)) }
watch([query, () => props.search], () => {
  clearTimeout(timer)
  const current = ++ticket
  if (!props.search) { rows.value = []; return }
  timer = setTimeout(async () => {
    loading.value = true; error.value = false
    try {
      const result = await props.search(query.value)
      if (current === ticket) rows.value = result.map(item => ({ value: item.value || item.id, label: item.label }))
    } catch { if (current === ticket) error.value = true }
    finally { if (current === ticket) loading.value = false }
  }, 180)
}, { immediate: true })
onBeforeUnmount(() => { ticket++; clearTimeout(timer) })
</script>
