<template>
  <button
    v-if="singleImage"
    data-single-image
    type="button"
    class="relative inline-flex max-w-full justify-self-start overflow-hidden rounded-md bg-surface-gray-2 text-left"
    :class="getSingleImageMediaWidthClass(singleImage)"
    :style="singleImageStyle"
    :disabled="!singleImage.url || !getAttachmentState(singleImage).active"
    @click="open(singleImage)"
  >
    <img
      v-if="
        singleImage.url &&
        getAttachmentState(singleImage).active &&
        showSingleImageBackdrop
      "
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
      v-if="singleImage.url && getAttachmentState(singleImage).active"
      :src="singleImage.url"
      :alt="singleImage.file_name || __('Image')"
      :width="imageDimension(singleImage.width)"
      :height="imageDimension(singleImage.height)"
      class="relative z-10 block size-full max-w-full object-contain"
      loading="lazy"
      @load="handleSingleImageLoad"
    />
    <div
      v-else
      class="flex min-h-28 w-full max-w-full flex-col items-center justify-center gap-2 p-3 text-center text-xs text-ink-gray-5"
    >
      <LoadingIndicator
        v-if="getAttachmentState(singleImage).busy"
        class="size-5"
      />
      <ImageOffIcon v-else class="size-5" />
      <span>{{ __(getAttachmentState(singleImage).label) }}</span>
    </div>
  </button>

  <div
    v-else-if="images.length"
    data-image-grid
    class="grid w-[min(20rem,calc(100vw-3rem))] max-w-full grid-cols-2 gap-1 overflow-hidden rounded-lg"
    :class="compactPreview ? compactGridRowsClass : ''"
    :style="compactGridStyle"
  >
    <button
      v-for="(image, index) in visibleImages"
      :key="image.id"
      type="button"
      class="relative min-h-28 overflow-hidden bg-surface-gray-2 text-left"
      :class="imageGridCellClass(images.length, index)"
      :disabled="!image.url || !getAttachmentState(image).active"
      @click="open(image)"
    >
      <img
        v-if="image.url && getAttachmentState(image).active"
        :src="image.url"
        :alt="image.file_name || __('Image')"
        class="size-full object-cover"
        loading="lazy"
      />
      <div
        v-else
        class="flex size-full min-h-28 flex-col items-center justify-center gap-2 p-3 text-center text-xs text-ink-gray-5"
      >
        <LoadingIndicator
          v-if="getAttachmentState(image).busy"
          class="size-5"
        />
        <ImageOffIcon v-else class="size-5" />
        <span>{{ __(getAttachmentState(image).label) }}</span>
      </div>
      <div
        v-if="index === 3 && images.length > 4"
        class="absolute inset-0 flex items-center justify-center bg-black/55 text-2xl font-semibold text-white"
      >
        +{{ images.length - 4 }}
      </div>
    </button>
  </div>
</template>

<script setup>
import LoadingIndicator from '@/components/Icons/LoadingIndicator.vue'
import {
  getAttachmentState,
  getCompactMediaDimensions,
  getCompactPreviewDimensions,
  getImageGridCellClass,
  getSingleImageMediaWidthClass,
  visibleImageAttachments,
} from '@/utils/messengerAttachments'
import { computed, ref, watch } from 'vue'
import ImageOffIcon from '~icons/lucide/image-off'

const props = defineProps({
  images: { type: Array, default: () => [] },
  compactPreview: { type: Boolean, default: false },
})
const emit = defineEmits(['open-image'])
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
const singleImageMedia = computed(() => ({
  width: actualWidth.value || singleImage.value?.width,
  height: actualHeight.value || singleImage.value?.height,
}))
const singleImageDimensions = computed(() =>
  props.compactPreview
    ? getCompactPreviewDimensions(singleImageMedia.value)
    : getCompactMediaDimensions(singleImageMedia.value),
)
const showSingleImageBackdrop = computed(
  () =>
    Boolean(singleImage.value?.url) &&
    getAttachmentState(singleImage.value).active &&
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
  if (!image.url || !getAttachmentState(image).active) return
  emit('open-image', image)
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
  return Number(image?.width) > 0 && Number(image?.height) > 0
}

function imageGridCellClass(count, index) {
  if (!props.compactPreview) return getImageGridCellClass(count, index)
  return count === 3 && index === 0 ? 'row-span-2' : ''
}

watch(
  () => singleImage.value?.id,
  () => {
    actualWidth.value = 0
    actualHeight.value = 0
  },
)
</script>
