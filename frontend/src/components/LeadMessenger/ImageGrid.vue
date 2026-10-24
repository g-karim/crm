<template>
  <div v-if="singleImage" class="w-fit min-w-0 max-w-full">
    <button
      data-single-image
      type="button"
      class="relative inline-flex max-w-full justify-self-start overflow-hidden rounded-md bg-surface-gray-2 text-left"
      :class="getSingleImageMediaWidthClass(singleImage)"
      :style="singleImageStyle"
      :disabled="
        !canDisplayLocalImage(singleImage) ||
        !getAttachmentState(singleImage).active
      "
      :aria-label="__('Open Image')"
      @click="open(singleImage)"
    >
      <img
        v-if="canDisplayLocalImage(singleImage) && showSingleImageBackdrop"
        data-media-backdrop
        :src="singleImage.url"
        alt=""
        aria-hidden="true"
        class="pointer-events-none absolute inset-0 size-full scale-110 object-cover blur-xl"
      />
      <span
        v-if="showSingleImageBackdrop"
        aria-hidden="true"
        class="pointer-events-none absolute inset-0 bg-black/30"
      />
      <img
        v-if="canDisplayLocalImage(singleImage)"
        :src="singleImage.url"
        :alt="__(getMessengerAttachmentTitle(singleImage))"
        :width="imageDimension(singleImage.width)"
        :height="imageDimension(singleImage.height)"
        class="relative z-10 block size-full max-w-full object-contain"
        loading="lazy"
        @load="handleSingleImageLoad"
        @error="markImageFailed(singleImage)"
      />
      <div
        v-else
        class="flex min-h-28 w-full max-w-full flex-col items-center justify-center gap-2 p-3 text-center text-xs text-ink-gray-5"
        role="status"
      >
        <LoadingIndicator
          v-if="getAttachmentState(singleImage).busy && !waitingForUpdate"
          class="size-5"
          data-image-loading
        />
        <ImageOffIcon v-else class="size-5" />
        <span>{{ __(imageStatusLabel(singleImage)) }}</span>
      </div>
      <div
        v-if="isVkProviderUploadFailure(singleImage)"
        data-vk-image-send-failed
        class="absolute inset-x-0 bottom-0 z-20 bg-red-700/90 px-3 py-2 text-center text-xs font-medium text-white"
      >
        {{ __('Failed to send image to VK') }}
      </div>
    </button>
    <div
      v-if="canRetryImage(singleImage) || canRefreshImage(singleImage)"
      class="flex flex-wrap gap-2"
    >
      <button
        v-if="canRetryImage(singleImage)"
        type="button"
        data-image-retry
        class="min-h-10 rounded px-2 text-sm text-ink-blue-6 focus-visible:ring-2"
        @click="retryImage(singleImage)"
      >
        {{ __('Try Again') }}
      </button>
      <button
        v-if="canRefreshImage(singleImage)"
        type="button"
        data-image-refresh
        :disabled="refreshing"
        class="min-h-10 rounded px-2 text-sm text-ink-blue-6 focus-visible:ring-2"
        @click="refresh"
      >
        {{ __('Refresh') }}
      </button>
    </div>
    <p v-if="refreshError" class="mt-1 text-xs text-ink-red-8" role="status">
      {{ refreshError }}
    </p>
  </div>

  <div
    v-else-if="images.length"
    data-image-grid
    class="grid w-[min(20rem,calc(100vw-3rem))] max-w-full grid-cols-2 gap-1 overflow-hidden rounded-lg"
    :class="compactPreview ? compactGridRowsClass : ''"
    :style="compactGridStyle"
  >
    <div
      v-for="(image, index) in visibleImages"
      :key="image.id"
      class="relative min-h-28 overflow-hidden bg-surface-gray-2 text-left"
      :class="imageGridCellClass(images.length, index)"
    >
      <button
        type="button"
        class="relative block size-full min-h-28 text-left"
        :disabled="
          !canDisplayLocalImage(image) || !getAttachmentState(image).active
        "
        :aria-label="__('Open Image')"
        @click="open(image)"
      >
        <img
          v-if="canDisplayLocalImage(image)"
          :src="image.url"
          :alt="__(getMessengerAttachmentTitle(image))"
          class="size-full object-cover"
          loading="lazy"
          @error="markImageFailed(image)"
        />
        <div
          v-else
          class="flex size-full min-h-28 flex-col items-center justify-center gap-2 p-3 text-center text-xs text-ink-gray-5"
          role="status"
        >
          <LoadingIndicator
            v-if="getAttachmentState(image).busy && !waitingForUpdate"
            class="size-5"
            data-image-loading
          />
          <ImageOffIcon v-else class="size-5" />
          <span>{{ __(imageStatusLabel(image)) }}</span>
        </div>
        <div
          v-if="isVkProviderUploadFailure(image)"
          data-vk-image-send-failed
          class="absolute inset-x-0 bottom-0 z-10 bg-red-700/90 px-2 py-1.5 text-center text-xs font-medium text-white"
        >
          {{ __('Failed to send image to VK') }}
        </div>
        <div
          v-if="index === 3 && images.length > 4"
          class="absolute inset-0 flex items-center justify-center bg-black/55 text-2xl font-semibold text-white"
        >
          +{{ images.length - 4 }}
        </div>
      </button>
      <div
        v-if="canRetryImage(image) || canRefreshImage(image)"
        class="absolute inset-x-0 bottom-0 z-30 flex flex-wrap justify-center gap-2 bg-surface-base/95"
      >
        <button
          v-if="canRetryImage(image)"
          type="button"
          data-image-retry
          class="min-h-10 rounded px-2 text-sm text-ink-blue-6 focus-visible:ring-2"
          @click="retryImage(image)"
        >
          {{ __('Try Again') }}
        </button>
        <button
          v-if="canRefreshImage(image)"
          type="button"
          data-image-refresh
          :disabled="refreshing"
          class="min-h-10 rounded px-2 text-sm text-ink-blue-6 focus-visible:ring-2"
          @click="refresh"
        >
          {{ __('Refresh') }}
        </button>
      </div>
    </div>
    <p
      v-if="refreshError"
      class="col-span-2 p-2 text-xs text-ink-red-8"
      role="status"
    >
      {{ refreshError }}
    </p>
  </div>
</template>

<script setup>
import LoadingIndicator from '@/components/Icons/LoadingIndicator.vue'
import {
  getAttachmentState,
  getMessengerAttachmentTitle,
  getCompactMediaDimensions,
  getCompactPreviewDimensions,
  getImageGridCellClass,
  getSingleImageMediaWidthClass,
  visibleImageAttachments,
} from '@/utils/messengerAttachments'
import { computed, inject, onBeforeUnmount, ref, watch } from 'vue'
import ImageOffIcon from '~icons/lucide/image-off'

const props = defineProps({
  images: { type: Array, default: () => [] },
  compactPreview: { type: Boolean, default: false },
  provider: { type: String, default: '' },
  outbound: { type: Boolean, default: false },
})
const emit = defineEmits(['open-image'])
const refreshAttachments = inject('refreshMessengerAttachments', null)
const failedImages = ref(new Set())
const waitingForUpdate = ref(false)
const refreshing = ref(false)
const refreshError = ref('')
let waitingTimer = null
const actualWidth = ref(0)
const actualHeight = ref(0)
const singleImage = computed(() =>
  props.images.length === 1 ? props.images[0] : null,
)
const singleImageStyle = computed(() => {
  if (!singleImage.value) return undefined
  let style = {
    width: `${singleImageDimensions.value.width}px`,
    maxWidth: '100%',
  }
  if (
    props.compactPreview ||
    actualWidth.value > 0 ||
    hasDimensions(singleImage.value)
  ) {
    style.aspectRatio = String(singleImageDimensions.value.ratio)
  }
  return style
})
const singleImageMedia = computed(() =>
  hasDimensions(singleImage.value)
    ? singleImage.value
    : { width: actualWidth.value, height: actualHeight.value },
)
const singleImageDimensions = computed(() =>
  props.compactPreview
    ? getCompactPreviewDimensions(singleImageMedia.value)
    : getCompactMediaDimensions(singleImageMedia.value),
)
const showSingleImageBackdrop = computed(
  () =>
    canDisplayLocalImage(singleImage.value) &&
    singleImageDimensions.value.letterboxed,
)
const visibleImages = computed(() => visibleImageAttachments(props.images))
const compactGridRowsClass = computed(() =>
  props.images.length === 2 ? 'grid-rows-1' : 'grid-rows-2',
)
const compactGridStyle = computed(() =>
  props.compactPreview
    ? {
        aspectRatio: props.images.length === 2 ? '2' : String(320 / 280),
        maxHeight: '280px',
      }
    : undefined,
)

function open(image) {
  if (!canDisplayLocalImage(image) || !getAttachmentState(image).active) return
  emit('open-image', image)
}

function isVkProviderUploadFailure(image) {
  return (
    props.outbound &&
    props.provider === 'vk_direct' &&
    image?.status === 'failed' &&
    Boolean(image.url)
  )
}

function canDisplayLocalImage(image) {
  return (
    Boolean(image?.url) &&
    !failedImages.value.has(imageSourceKey(image)) &&
    (getAttachmentState(image).active || isVkProviderUploadFailure(image))
  )
}

function imageSourceKey(image = {}) {
  return JSON.stringify([image.id, image.url])
}

function markImageFailed(image) {
  failedImages.value.add(imageSourceKey(image))
}

function canRetryImage(image) {
  return (
    failedImages.value.has(imageSourceKey(image)) &&
    Boolean(image.url) &&
    (getAttachmentState(image).active || isVkProviderUploadFailure(image))
  )
}

function retryImage(image) {
  failedImages.value.delete(imageSourceKey(image))
}

function canRefreshImage(image) {
  let state = getAttachmentState(image)
  return Boolean(refreshAttachments && (state.busy || state.failed))
}

function imageStatusLabel(image) {
  if (failedImages.value.has(imageSourceKey(image))) return 'Image unavailable'
  let state = getAttachmentState(image)
  return state.active ? 'Attachment unavailable' : state.label
}

async function refresh() {
  if (!refreshAttachments || refreshing.value) return
  refreshing.value = true
  refreshError.value = ''
  try {
    await refreshAttachments()
  } catch {
    refreshError.value = __('Could not refresh messages.')
  } finally {
    refreshing.value = false
  }
}

function imageDimension(value) {
  let dimension = Number(value || 0)
  return dimension > 0 ? dimension : undefined
}

function handleSingleImageLoad(event) {
  actualWidth.value = Number(event.currentTarget?.naturalWidth || 0)
  actualHeight.value = Number(event.currentTarget?.naturalHeight || 0)
}

function hasDimensions(image) {
  return [image?.width, image?.height].every(
    (value) => Number.isFinite(Number(value)) && Number(value) > 0,
  )
}

function imageGridCellClass(count, index) {
  if (!props.compactPreview) return getImageGridCellClass(count, index)
  return count === 3 && index === 0 ? 'row-span-2' : ''
}

watch(
  () => [singleImage.value?.id, singleImage.value?.url],
  () => {
    actualWidth.value = 0
    actualHeight.value = 0
  },
)

watch(
  () =>
    JSON.stringify(
      props.images.map((image) => [image.id, image.url, image.status]),
    ),
  () => {
    let currentKeys = new Set(
      props.images
        .filter(
          (image) =>
            getAttachmentState(image).active ||
            isVkProviderUploadFailure(image),
        )
        .map(imageSourceKey),
    )
    failedImages.value = new Set(
      [...failedImages.value].filter((key) => currentKeys.has(key)),
    )
    refreshError.value = ''
    if (props.images.some((image) => getAttachmentState(image).busy)) {
      if (waitingTimer === null && !waitingForUpdate.value) {
        waitingTimer = setTimeout(() => {
          waitingTimer = null
          waitingForUpdate.value = true
        }, 30000)
      }
    } else {
      clearTimeout(waitingTimer)
      waitingTimer = null
      waitingForUpdate.value = false
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => clearTimeout(waitingTimer))
</script>
