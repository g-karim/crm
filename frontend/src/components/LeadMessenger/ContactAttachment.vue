<template>
  <div
    class="rounded-md border border-outline-gray-2 bg-surface-base px-3 py-2"
  >
    <div class="flex items-center gap-2">
      <FeatherIcon name="user" class="h-5 w-5 shrink-0 text-ink-gray-6" />
      <div class="min-w-0 flex-1">
        <div class="text-xs text-ink-gray-5">
          {{ __('Contact') }}
        </div>
        <div class="truncate font-medium">
          {{ safeContact.display_name || __('Name not provided') }}
        </div>
      </div>
    </div>
    <div v-if="safeContact.phones?.length" class="mt-2 grid gap-1">
      <a
        v-for="phone in safeContact.phones"
        :key="phone"
        :href="`tel:${phone}`"
        class="w-fit text-sm text-ink-blue-6 hover:underline"
      >
        {{ phone }}
      </a>
    </div>
  </div>
</template>

<script setup>
import { FeatherIcon } from 'frappe-ui'
import { computed } from 'vue'

const props = defineProps({
  contact: { type: Object, default: () => ({}) },
})
const safeContact = computed(() => props.contact || {})
</script>
