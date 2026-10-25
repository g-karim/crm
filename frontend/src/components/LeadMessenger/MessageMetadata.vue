<template>
  <div
    data-message-metadata
    class="mb-1 items-start gap-2"
    :class="[
      wrapSource
        ? 'grid grid-cols-[minmax(0,1fr)_auto]'
        : 'flex justify-between',
      constrainIntrinsicWidth ? 'w-0 min-w-full' : 'min-w-0',
    ]"
  >
    <div
      data-message-labels
      :class="
        wrapSource
          ? 'contents'
          : 'flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1'
      "
    >
      <span
        data-message-sender
        class="max-w-full break-words text-xs font-medium text-ink-gray-5 [overflow-wrap:anywhere]"
      >
        {{ sender }}
      </span>
      <Badge
        data-message-source
        class="max-w-full"
        :class="
          wrapSource
            ? 'col-span-full row-start-2 justify-self-start !h-auto !whitespace-normal !overflow-visible [overflow-wrap:anywhere]'
            : ''
        "
        variant="subtle"
        :label="source"
      />
      <Badge v-if="failed" theme="red" variant="subtle" :label="__('Failed')" />
    </div>

    <Dropdown
      v-if="menuOptions.length && !editing"
      data-message-actions
      class="shrink-0"
      :class="wrapSource ? 'col-start-2 row-start-1' : ''"
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
  deleteBlocked: { type: Boolean, default: false },
  editBlocked: { type: Boolean, default: false },
  constrainIntrinsicWidth: { type: Boolean, default: false },
  wrapSource: { type: Boolean, default: false },
})

const emit = defineEmits(['start-edit', 'delete', 'retry', 'reply'])

function capitalizeFirstLetter(label) {
  return label.replace(/^./u, (letter) => letter.toUpperCase())
}

const menuOptions = computed(() =>
  getMessengerMessageActions(props.message, {
    deleteBlocked: props.deleteBlocked,
    editBlocked: props.editBlocked,
  }).map((action) => {
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
        label: capitalizeFirstLetter(__('Edit')),
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
