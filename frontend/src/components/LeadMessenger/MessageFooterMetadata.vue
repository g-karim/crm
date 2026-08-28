<template>
  <div
    v-if="visible"
    data-message-footer
    class="mt-1 flex items-center justify-end gap-1.5 whitespace-nowrap text-xs text-ink-gray-5"
  >
    <span v-if="display.edited" data-message-edited class="shrink-0">
      {{ __('ред.') }}
    </span>
    <Tooltip
      v-if="message.message_datetime"
      :text="formatDate(message.message_datetime)"
    >
      <span data-message-time class="shrink-0">
        {{ formatDate(message.message_datetime, 'HH:mm') }}
      </span>
    </Tooltip>
    <Tooltip v-if="deliveryState" :text="deliveryTooltip">
      <span
        data-message-delivery
        class="inline-flex shrink-0 items-center"
        :class="deliveryIconClass"
      >
        <ClockIcon
          v-if="['queued', 'sending', 'retrying'].includes(deliveryState)"
          class="size-4"
        />
        <CheckIcon v-else-if="deliveryState === 'sent'" class="size-4" />
        <DoubleCheckIcon
          v-else-if="['delivered', 'read'].includes(deliveryState)"
          class="size-4"
        />
        <CircleAlertIcon
          v-else-if="['failed', 'unknown'].includes(deliveryState)"
          class="size-4"
        />
      </span>
    </Tooltip>
  </div>
</template>

<script setup>
import CheckIcon from '@/components/Icons/CheckIcon.vue'
import DoubleCheckIcon from '@/components/Icons/DoubleCheckIcon.vue'
import { formatDate } from '@/utils'
import {
  getMessengerDeliveryLabel,
  getMessengerDeliveryState,
} from '@/utils/messengerChannels'
import { getMessengerMessageDisplay } from '@/utils/messengerMessageActions'
import { Tooltip } from 'frappe-ui'
import { computed } from 'vue'
import CircleAlertIcon from '~icons/lucide/circle-alert'
import ClockIcon from '~icons/lucide/clock-3'

const props = defineProps({
  message: { type: Object, required: true },
})

const display = computed(() => getMessengerMessageDisplay(props.message))
const deliveryState = computed(() => getMessengerDeliveryState(props.message))
const deliveryTooltip = computed(() => {
  let label = getMessengerDeliveryLabel(props.message)
  let reason = props.message.failure_reason || props.message.error || ''
  return reason ? `${__(label)}: ${reason}` : __(label)
})
const deliveryIconClass = computed(() => {
  if (deliveryState.value === 'read') return 'text-ink-blue-2'
  if (['failed', 'unknown'].includes(deliveryState.value)) {
    return 'text-ink-red-4'
  }
  return 'text-ink-gray-5'
})
const visible = computed(
  () =>
    display.value.edited ||
    Boolean(props.message.message_datetime) ||
    Boolean(deliveryState.value),
)
</script>
