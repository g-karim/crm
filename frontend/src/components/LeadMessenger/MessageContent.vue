<template>
  <div class="min-w-0 max-w-full">
    <div
      v-if="editing"
      :ref="setEditorElement"
      data-message-editor
      class="min-w-[260px] space-y-2"
    >
      <Textarea
        :modelValue="draft"
        :rows="3"
        :disabled="loading"
        :placeholder="__('Введите сообщение...')"
        @update:modelValue="$emit('update:draft', $event)"
        @keydown.esc.stop="$emit('cancel-edit')"
      />
      <div class="flex justify-end gap-2">
        <Button
          :label="__('Отменить')"
          variant="ghost"
          :disabled="loading"
          @click="$emit('cancel-edit')"
        />
        <Button
          :label="__('Сохранить')"
          variant="solid"
          :loading="loading"
          :disabled="!draft.trim()"
          @click="$emit('save-edit')"
        />
      </div>
    </div>

    <template v-else>
      <div
        v-if="display.tombstone || shouldShowText"
        class="max-w-full whitespace-pre-wrap break-words [overflow-wrap:anywhere]"
        :class="display.tombstone ? 'italic text-ink-gray-5' : ''"
      >
        {{ display.tombstone ? __('Сообщение удалено') : display.text }}
      </div>
    </template>

    <div v-if="error" class="mt-2 text-xs text-ink-red-4">
      {{ __(error) }}
    </div>
  </div>
</template>

<script setup>
import { getMessengerMessageDisplay } from '@/utils/messengerMessageActions'
import { Button, Textarea } from 'frappe-ui'
import { computed } from 'vue'

const props = defineProps({
  message: { type: Object, required: true },
  editing: { type: Boolean, default: false },
  draft: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  shouldShowText: { type: Boolean, default: false },
})

const emit = defineEmits([
  'update:draft',
  'save-edit',
  'cancel-edit',
  'editor-element',
])

function setEditorElement(element) {
  emit('editor-element', element)
}

const display = computed(() => getMessengerMessageDisplay(props.message))
</script>
