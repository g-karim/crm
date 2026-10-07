<template>
  <div class="min-w-0 max-w-full">
    <div
      v-if="editing"
      :ref="setEditorElement"
      data-message-editor
      class="w-full min-w-0 space-y-2"
    >
      <Textarea
        :modelValue="draft"
        :rows="3"
        :disabled="loading"
        :maxlength="message.edit_max_length || undefined"
        :placeholder="__('Enter a message...')"
        @update:modelValue="$emit('update:draft', $event)"
        @keydown.esc.stop="$emit('cancel-edit')"
      />
      <div class="flex justify-end gap-2">
        <Button
          :label="__('Cancel')"
          variant="ghost"
          :disabled="loading"
          @click="$emit('cancel-edit')"
        />
        <Button
          :label="__('Save')"
          variant="solid"
          :loading="loading"
          :disabled="!canSaveMessengerMessageEdit(message, draft)"
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
        <template v-if="display.tombstone">{{
          __('Message deleted')
        }}</template>
        <template v-else>
          {{
            textPresentation.translate
              ? __(textPresentation.text)
              : textPresentation.text
          }}
          <a
            v-if="
              textPresentation.action === 'open_provider_chat' &&
              externalChatUrl
            "
            data-provider-chat-action
            :href="externalChatUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="mt-2 flex w-fit items-center gap-1.5 text-sm font-medium text-ink-blue-6 hover:underline"
          >
            <ExternalLinkIcon class="size-4 shrink-0" />
            {{ __('Open chat in Avito') }}
          </a>
        </template>
      </div>
    </template>

    <div v-if="error" class="mt-2 text-xs text-ink-red-8">
      {{ __(error) }}
    </div>
  </div>
</template>

<script setup>
import ExternalLinkIcon from '@/components/Icons/ExternalLinkIcon.vue'
import { getProviderExternalChatUrl } from '@/utils/messengerExternalLinks'
import {
  canSaveMessengerMessageEdit,
  getMessengerMessageDisplay,
} from '@/utils/messengerMessageActions'
import { getMessengerMessageTextPresentation } from '@/utils/messengerMessagePresentation'
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
const textPresentation = computed(() =>
  getMessengerMessageTextPresentation(props.message),
)
const externalChatUrl = computed(() =>
  getProviderExternalChatUrl(
    props.message.provider,
    props.message.external_chat_id,
  ),
)
</script>
