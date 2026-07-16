<template>
  <div>
    <input
      ref="fileInput"
      type="file"
      class="hidden"
      multiple
      @change="onFileInput"
    />
    <div
      v-if="items.length"
      class="mb-2 flex gap-2 overflow-x-auto pb-1"
    >
      <div
        v-for="item in items"
        :key="item.id"
        class="relative flex w-40 shrink-0 items-center gap-2 rounded-lg border border-outline-gray-1 bg-surface-white p-2"
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
            :class="item.status === 'failed' ? 'text-ink-red-4' : 'text-ink-gray-5'"
          >
            {{ itemStatus(item) }}
          </div>
          <div
            v-if="item.status === 'uploading'"
            class="mt-1 h-1 overflow-hidden rounded bg-surface-gray-3"
          >
            <div
              class="h-full bg-surface-blue-3 transition-all"
              :style="{ width: `${item.progress}%` }"
            />
          </div>
          <Button
            v-if="item.status === 'failed'"
            class="mt-1 !h-5 !px-1 text-xs"
            variant="ghost"
            :label="__('Повторить')"
            @click="controller.retry(item.id)"
          />
        </div>
        <Button
          class="absolute right-0 top-0 !size-6 translate-x-1/3 -translate-y-1/3 rounded-full shadow-sm"
          icon="x"
          :aria-label="__('Удалить вложение')"
          @click="controller.remove(item.id)"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import {
  createComposerAttachmentController,
  validateComposerFileMix,
} from '@/utils/messengerComposer'
import { Button, FileUploadHandler, toast } from 'frappe-ui'
import { onBeforeUnmount, ref } from 'vue'
import FileIcon from '~icons/lucide/file'

const props = defineProps({
  supportsAttachments: { type: Boolean, default: false },
  channelType: { type: String, default: '' },
})
const emit = defineEmits(['change'])
const fileInput = ref(null)
const items = ref([])

const controller = createComposerAttachmentController({
  upload: uploadFile,
  createObjectURL: (file) => URL.createObjectURL(file),
  revokeObjectURL: (url) => URL.revokeObjectURL(url),
  validateFiles(files, existing) {
    return validateComposerFileMix(files, existing, {
      supportsAttachments: props.supportsAttachments,
      channelType: props.channelType,
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
  return uploader.upload(file, { private: true })
}

function onFileInput(event) {
  controller.addFiles(event.target.files)
  event.target.value = ''
}

function openFileSelector() {
  fileInput.value?.click()
}

function itemStatus(item) {
  if (item.status === 'uploaded') return __('Готово')
  if (item.status === 'uploading') return __('Загрузка {0}%', [item.progress])
  if (item.status === 'failed') return item.error || __('Ошибка загрузки')
  return __('Ожидание')
}

onBeforeUnmount(() => controller.clear())

defineExpose({
  openFileSelector,
  handlePaste: controller.handlePaste,
  handleDrop: controller.handleDrop,
  clear: controller.clear,
  hasBlockingItems: controller.hasBlockingItems,
  readyFileNames: controller.readyFileNames,
})
</script>
