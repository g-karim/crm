<template>
  <div v-if="items.length" class="mt-2 flex flex-wrap items-center gap-1">
    <button
      v-for="reaction in items"
      :key="reaction.reaction_id"
      type="button"
      class="rounded-full border px-2 py-0.5 text-xs tabular-nums transition-colors"
      :class="
        reaction.reaction_id === ownReactionId
          ? 'border-outline-blue-3 bg-surface-blue-2'
          : 'border-outline-gray-2 bg-surface-base'
      "
      :disabled="pending || !canSend || reaction.supported === false"
      :aria-pressed="reaction.reaction_id === ownReactionId"
      :title="
        reaction.reaction_type === 'custom_emoji'
          ? __('Custom Telegram Reaction')
          : undefined
      "
      @click="toggleReaction(reaction.reaction_id)"
    >
      {{ reactionDisplay(reaction) }} {{ reaction.count }}
    </button>
  </div>

  <Teleport to="body">
    <div
      v-if="pickerOpen"
      ref="pickerElement"
      class="fixed z-[1000] grid max-h-[calc(100dvh-1rem)] w-[calc(100vw-1rem)] max-w-[19rem] grid-cols-[repeat(auto-fit,minmax(2.25rem,1fr))] justify-items-center gap-1 overflow-y-auto overscroll-contain rounded-lg border border-outline-gray-2 bg-surface-base p-2 shadow-xl"
      :style="pickerStyle"
      role="menu"
      :aria-label="__('Choose Reaction')"
      @click.stop
      @contextmenu.prevent
    >
      <button
        v-for="reaction in catalog"
        :key="reaction.reaction_id"
        type="button"
        class="flex size-9 items-center justify-center rounded-md text-xl transition-colors hover:bg-surface-gray-2"
        :class="
          reaction.reaction_id === ownReactionId
            ? 'bg-surface-blue-2 ring-1 ring-outline-blue-3'
            : ''
        "
        :disabled="pending"
        :aria-label="`${__('Reaction')} ${reaction.emoji}`"
        :aria-pressed="reaction.reaction_id === ownReactionId"
        role="menuitemradio"
        @click="toggleReaction(reaction.reaction_id)"
      >
        {{ reaction.emoji }}
      </button>
    </div>
  </Teleport>
</template>

<script setup>
import { call, toast } from 'frappe-ui'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  message: { type: Object, required: true },
  canSend: { type: Boolean, default: false },
})
const emit = defineEmits(['changed'])
const pending = ref(false)
const pickerOpen = ref(false)
const pickerElement = ref(null)
const pickerPosition = ref({ left: 0, top: 0 })
const items = computed(() => props.message.reactions?.items || [])
const catalog = computed(() => props.message.reactions?.catalog || [])
const catalogVersion = computed(
  () => props.message.reactions?.catalog_version || '',
)
const catalogSignature = computed(
  () => props.message.reactions?.catalog_signature || '',
)
const ownReactionId = computed(() => props.message.reactions?.own_reaction_id)
const pickerStyle = computed(() => ({
  left: `${pickerPosition.value.left}px`,
  top: `${pickerPosition.value.top}px`,
}))

function reactionDisplay(reaction) {
  if (reaction.emoji) return reaction.emoji
  if (reaction.reaction_type === 'custom_emoji') return '✦'
  return `#${reaction.reaction_id}`
}

function openPicker(event) {
  if (!props.canSend || pending.value || !catalog.value.length) return false
  window.dispatchEvent(
    new CustomEvent('crm:reaction-picker-open', {
      detail: props.message.name,
    }),
  )
  pickerPosition.value = {
    left: Math.max(8, Math.min(event.clientX, window.innerWidth - 320)),
    top: Math.max(8, Math.min(event.clientY, window.innerHeight - 260)),
  }
  pickerOpen.value = true
  nextTick(() => {
    let rect = pickerElement.value?.getBoundingClientRect()
    if (!rect) return
    pickerPosition.value = {
      left: Math.max(
        8,
        Math.min(event.clientX, window.innerWidth - rect.width - 8),
      ),
      top: Math.max(
        8,
        Math.min(event.clientY, window.innerHeight - rect.height - 8),
      ),
    }
  })
  return true
}

function closePicker(event) {
  if (
    event?.type === 'crm:reaction-picker-open' &&
    event.detail === props.message.name
  )
    return
  pickerOpen.value = false
}

function handleKeydown(event) {
  if (event.key === 'Escape') closePicker()
}

async function toggleReaction(reactionId) {
  if (!props.canSend || pending.value) return
  pending.value = true
  try {
    let result = await call('crm_messenger.api.messages.set_reaction', {
      message: props.message.name,
      reaction_id: ownReactionId.value === reactionId ? null : reactionId,
      catalog_version: catalogVersion.value,
      catalog_signature: catalogSignature.value,
    })
    if (!result?.ok)
      throw new Error(result?.message || __('Could not update the reaction.'))
    pickerOpen.value = false
    emit('changed', result.reaction_state)
  } catch (error) {
    toast.error(__(error?.message || 'Could not update the reaction.'))
  } finally {
    pending.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', closePicker)
  document.addEventListener('keydown', handleKeydown)
  window.addEventListener('crm:reaction-picker-open', closePicker)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', closePicker)
  document.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('crm:reaction-picker-open', closePicker)
})

defineExpose({ openPicker })
</script>
