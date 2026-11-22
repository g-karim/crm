<template>
  <span
    class="flex items-center justify-center w-8 h-8 bg-surface-gray-2 rounded-xl"
    :class="{ 'ring-2 ring-outline-gray-4': selected }"
  >
    <img :src="logo" alt="" class="w-4 h-4" />
  </span>
  <span v-if="label" class="mt-2 block text-center text-xs text-ink-gray-6">
    {{ label }}
  </span>
</template>

<script setup>
defineProps({
  logo: { type: String, required: true },
  label: { type: String, default: '' },
  selected: { type: Boolean, default: false },
})
</script>
