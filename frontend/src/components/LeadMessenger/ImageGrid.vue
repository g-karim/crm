<template>
  <div
    class="grid w-[min(28rem,calc(100vw-3rem))] max-w-full gap-1 overflow-hidden rounded-lg"
    :class="images.length === 1 ? 'grid-cols-1' : 'grid-cols-2'"
  >
    <button
      v-for="(image, index) in visibleImages"
      :key="image.id"
      type="button"
      class="relative min-h-28 overflow-hidden bg-surface-gray-2 text-left"
      :class="getImageGridCellClass(images.length, index)"
      :style="cellStyle(image)"
      :disabled="!image.url || !getAttachmentState(image).active"
      @click="open(image)"
    >
      <img
        v-if="image.url && getAttachmentState(image).active"
        :src="image.url"
        :alt="image.file_name || __('Изображение')"
        class="size-full"
        :class="images.length === 1 ? 'object-contain' : 'object-cover'"
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
  <ImageLightbox
    v-if="lightboxOpen"
    :images="availableImages"
    :initialIndex="lightboxIndex"
    @close="lightboxOpen = false"
  />
</template>

<script setup>
import LoadingIndicator from '@/components/Icons/LoadingIndicator.vue'
import {
  getAttachmentState,
  getImageAspectRatio,
  getImageGridCellClass,
  visibleImageAttachments,
} from '@/utils/messengerAttachments'
import { computed, ref } from 'vue'
import ImageOffIcon from '~icons/lucide/image-off'
import ImageLightbox from './ImageLightbox.vue'

const props = defineProps({
  images: { type: Array, default: () => [] },
})
const lightboxOpen = ref(false)
const lightboxIndex = ref(0)
const visibleImages = computed(() => visibleImageAttachments(props.images))
const availableImages = computed(() =>
  props.images.filter(
    (image) => image.url && getAttachmentState(image).active,
  ),
)

function open(image) {
  let index = availableImages.value.findIndex((item) => item.id === image.id)
  if (index < 0) return
  lightboxIndex.value = index
  lightboxOpen.value = true
}

function cellStyle(image) {
  if (props.images.length !== 1) return undefined
  return { aspectRatio: getImageAspectRatio(image) }
}
</script>
