<template>
  <div>
    <input
      ref="fileInput"
      type="file"
      class="hidden"
      multiple
      :disabled="disabled"
      @change="onFileInput"
    />
    <div v-if="items.length" class="mb-2 flex gap-2 overflow-x-auto pb-1">
      <div
        v-for="item in items"
        :key="item.id"
        class="relative flex w-40 shrink-0 items-center gap-2 rounded-lg border border-outline-gray-1 bg-surface-base p-2"
      >
        <img
          v-if="item.previewUrl"
          :src="item.previewUrl"
          :alt="item.fileName"
          class="size-12 shrink-0 rounded object-cover"
        />
        <div
          v-else
          class="flex size-12 shrink-0 items-center justify-center rounded bg-surface-gray-2"
        >
          <FileIcon class="size-5 text-ink-gray-6" />
        </div>
        <div class="min-w-0 flex-1">
          <div class="truncate text-xs font-medium text-ink-gray-8">
            {{ item.fileName }}
          </div>
          <div
            class="mt-1 truncate text-xs"
            :class="
              item.status === 'failed' ? 'text-ink-red-8' : 'text-ink-gray-5'
            "
          >
            {{ itemStatus(item) }}
          </div>
          <div
            v-if="item.status === 'uploading'"
            class="mt-1 h-1 overflow-hidden rounded bg-surface-gray-3"
          >
            <div
              class="h-full bg-surface-blue-7 transition-all"
              :style="{ width: `${item.progress}%` }"
            />
          </div>
          <Button
            v-if="item.status === 'failed'"
            class="mt-1 !h-5 !px-1 text-xs"
            variant="ghost"
            :disabled="disabled || frozen"
            :label="__('Retry')"
            @click="controller.retry(item.id)"
          />
        </div>
        <Button
          class="absolute right-0 top-0 !size-6 translate-x-1/3 -translate-y-1/3 rounded-full shadow-sm"
          icon="x"
          :disabled="disabled || frozen"
          :aria-label="__('Remove Attachment')"
          @click="controller.remove(item.id)"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import {
  createComposerAttachmentController,
  retargetComposerTemporaryFiles,
  validateComposerFileMix,
} from '@/utils/messengerComposer'
import { Button, FileUploadHandler, call, toast } from 'frappe-ui'
import { onBeforeUnmount, ref, watch } from 'vue'
import FileIcon from '~icons/lucide/file'

const props = defineProps({
  supportsAttachments: { type: Boolean, default: false },
  channelType: { type: String, default: '' },
  maxFiles: { type: Number, default: 10 },
  disabled: { type: Boolean, default: false },
  conversation: { type: String, default: '' },
})
const emit = defineEmits(['change'])
const fileInput = ref(null)
const items = ref([])
const frozen = ref(false)
let preserveNextConversationChange = false

const controller = createComposerAttachmentController({
  maxFiles: () => props.maxFiles,
  scope: () => props.conversation,
  upload: uploadFile,
  discard: discardFiles,
  createObjectURL: (file) => URL.createObjectURL(file),
  revokeObjectURL: (url) => URL.revokeObjectURL(url),
  validateFiles(files, existing) {
    return validateComposerFileMix(files, existing, {
      supportsAttachments: props.supportsAttachments,
      channelType: props.channelType,
      maxAttachmentCount: props.maxFiles,
    })
  },
  onError: (message) => toast.error(__(message)),
  onChange(nextItems) {
    items.value = nextItems
    emit('change', nextItems)
  },
})

function uploadFile(file, onProgress) {
  let uploader = new FileUploadHandler()
  uploader.on('progress', ({ uploaded, total }) => {
    onProgress(total ? (uploaded / total) * 100 : 0)
  })
  return uploader.upload(file, {
    private: true,
    docname: props.conversation,
    upload_endpoint:
      '/api/method/crm_messenger.api.attachments.upload_temporary_file',
  })
}

function discardFiles(files, conversation = props.conversation) {
  if (!conversation || !files?.length) return
  return call('crm_messenger.api.attachments.discard_temporary_files', {
    conversation,
    files,
  })
}

function onFileInput(event) {
  if (props.disabled) return
  controller.addFiles(event.target.files)
  event.target.value = ''
}

function openFileSelector() {
  if (props.disabled) return
  fileInput.value?.click()
}

function handlePaste(event) {
  if (!props.disabled) controller.handlePaste(event)
}

function handleDrop(event) {
  if (!props.disabled) controller.handleDrop(event)
}

function itemStatus(item) {
  if (item.status === 'uploaded') return __('Ready')
  if (item.status === 'uploading') return __('Uploading {0}%', [item.progress])
  if (item.status === 'failed') return item.error || __('Upload failed')
  return __('Waiting')
}

async function discard() {
  frozen.value = false
  await controller.discard()
}

function release() {
  frozen.value = false
  controller.release()
}

function freeze() {
  let snapshot = controller.freeze()
  frozen.value = snapshot !== null
  return snapshot
}

function unfreeze() {
  frozen.value = false
  controller.unfreeze()
}

async function retarget(conversation) {
  let fileNames = controller.readyFileNames()
  let scopes = controller.getScopes()
  if (scopes.length > 1) {
    throw new Error(__('Could not identify the attachment conversation.'))
  }
  await retargetComposerTemporaryFiles(call, {
    sourceConversation: scopes[0] || props.conversation,
    targetConversation: conversation,
    files: fileNames,
  })
  controller.retargetScope(conversation)
  preserveNextConversationChange = true
}

function preserveScopeChange() {
  preserveNextConversationChange = true
}

onBeforeUnmount(() => controller.discard())
watch(
  () => props.conversation,
  (conversation, previousConversation) => {
    if (conversation === previousConversation) return
    if (preserveNextConversationChange) {
      preserveNextConversationChange = false
      return
    }
    controller.discard()
  },
)

defineExpose({
  openFileSelector,
  handlePaste,
  handleDrop,
  discard,
  release,
  freeze,
  unfreeze,
  retarget,
  preserveScopeChange,
  hasBlockingItems: controller.hasBlockingItems,
  readyFileNames: controller.readyFileNames,
})
</script>
