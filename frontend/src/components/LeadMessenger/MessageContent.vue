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
        v-if="message.template_context && !display.tombstone"
        data-message-template
        class="mb-2 space-y-1 break-words [overflow-wrap:anywhere]"
      >
        <div class="text-sm font-medium">{{ __('Template message') }}</div>
        <div v-if="!message.text?.trim()" class="text-xs text-ink-gray-5">
          {{ __('The provider did not include the template text.') }}
        </div>
        <div v-if="message.template_context.values?.length" class="space-y-1">
          <div class="text-xs text-ink-gray-5">{{ __('Template values') }}</div>
          <MessageText
            v-for="(value, index) in message.template_context.values"
            :key="`value:${index}`"
            :text="value"
          />
        </div>
        <div
          v-if="message.template_context.buttons?.length"
          class="flex flex-wrap gap-1"
        >
          <span
            v-for="(button, index) in message.template_context.buttons"
            :key="`button:${index}`"
            class="rounded border border-outline-gray-2 px-2 py-1 text-sm"
            >{{ button.text }}</span
          >
        </div>
      </div>
      <div
        v-if="display.tombstone || shouldShowText"
        class="max-w-full whitespace-pre-wrap break-words [overflow-wrap:anywhere]"
        :class="display.tombstone ? 'italic text-ink-gray-5' : ''"
      >
        <template v-if="display.tombstone">{{
          __('Message deleted')
        }}</template>
        <template v-else>
          <MessageText
            :text="
              textPresentation.translate
                ? __(textPresentation.text)
                : textPresentation.text
            "
          />
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
import MessageText from './MessageText.vue'

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
