<template>
  <div
    data-message-metadata
    class="mb-1 flex min-w-0 items-start justify-between gap-2"
  >
    <div
      data-message-labels
      class="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1"
    >
      <span class="text-xs font-medium text-ink-gray-5">
        {{ sender }}
      </span>
      <Badge class="max-w-full" variant="subtle" :label="source" />
      <Badge v-if="failed" theme="red" variant="subtle" :label="__('Failed')" />
    </div>

    <Dropdown
      v-if="menuOptions.length && !editing"
      data-message-actions
      class="shrink-0"
      :options="menuOptions"
    >
      <Button
        class="opacity-70 transition-opacity hover:opacity-100 focus-visible:opacity-100"
        variant="ghost"
        icon="more-horizontal"
        size="sm"
        :loading="loading"
        :disabled="loading"
        :aria-label="__('Message Actions')"
      />
    </Dropdown>
  </div>
</template>

<script setup>
import { getMessengerMessageActions } from '@/utils/messengerMessageActions'
import { Badge, Button, Dropdown } from 'frappe-ui'
import { computed } from 'vue'

const props = defineProps({
  message: { type: Object, required: true },
  sender: { type: String, default: '' },
  source: { type: String, default: '' },
  failed: { type: Boolean, default: false },
  editing: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['start-edit', 'delete', 'retry', 'reply'])

const menuOptions = computed(() =>
  getMessengerMessageActions(props.message).map((action) => {
    if (action === 'reply') {
      return {
        label: __('Reply'),
        icon: 'corner-up-left',
        onClick: () => emit('reply'),
      }
    }
    if (action === 'retry') {
      return {
        label: __('Retry Sending'),
        icon: 'refresh-cw',
        onClick: () => emit('retry'),
      }
    }
    if (action === 'edit') {
      return {
        label: __('Edit'),
        icon: 'edit-3',
        onClick: () => emit('start-edit'),
      }
    }
    return {
      label: __('Delete for Everyone'),
      icon: 'trash-2',
      onClick: () => emit('delete'),
    }
  }),
)
</script>
