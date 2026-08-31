<template>
  <div class="w-fit max-w-full">
    <button
      v-if="playable"
      type="button"
      data-animated-media
      class="relative block max-w-full overflow-hidden rounded-lg bg-black text-left"
      :style="frameStyle"
      :aria-label="__('Open Animation')"
      @click="emit('open-media', attachment)"
    >
      <img
        v-if="showBackdrop"
        data-media-backdrop
        :src="backdropSource"
        alt=""
        aria-hidden="true"
        class="pointer-events-none absolute inset-0 size-full scale-110 object-cover blur-xl"
      />
      <span
        v-if="showBackdrop"
        aria-hidden="true"
        class="pointer-events-none absolute inset-0 bg-black/35"
      />
      <img
        v-if="imageAnimation"
        data-animated-image
        :src="source"
        :alt="attachment.file_name || __('Animation')"
        class="relative z-10 size-full object-contain"
        loading="lazy"
        @load="handleImageLoad"
        @error="failed = true"
      />
      <video
        v-else
        data-animated-video
        :src="source"
        class="relative z-10 size-full object-contain"
        autoplay
        loop
        muted
        playsinline
        preload="metadata"
        @loadedmetadata="handleMetadata"
        @loadeddata="captureBackdropFrame"
        @error="failed = true"
      />
    </button>
    <AttachmentCard v-else :attachment="fallbackAttachment" />
  </div>
</template>

<script setup>
import {
  getAttachmentState,
  getCompactMediaDimensions,
  getCompactPreviewDimensions,
} from '@/utils/messengerAttachments'
import { computed, ref, watch } from 'vue'
import AttachmentCard from './AttachmentCard.vue'

const props = defineProps({
  attachment: { type: Object, required: true },
  compactPreview: { type: Boolean, default: false },
})
const emit = defineEmits(['open-media'])

const failed = ref(false)
const actualWidth = ref(0)
const actualHeight = ref(0)
const generatedBackdropUrl = ref('')
const imageAnimation = computed(() =>
  String(props.attachment.mime_type || '').startsWith('image/'),
)
const source = computed(() =>
  imageAnimation.value
    ? props.attachment.url || props.attachment.preview_url || ''
    : props.attachment.playback_url ||
      props.attachment.url ||
      props.attachment.preview_url ||
      '',
)
const playable = computed(
  () =>
    getAttachmentState(props.attachment).active &&
    Boolean(source.value) &&
    !failed.value,
)
const fallbackAttachment = computed(() => ({
  ...props.attachment,
  open_url:
    props.attachment.open_url ||
    props.attachment.download_url ||
    props.attachment.url ||
    '',
}))
const dimensions = computed(() => {
  let media = {
    width: actualWidth.value || props.attachment.width,
    height: actualHeight.value || props.attachment.height,
  }
  return props.compactPreview
    ? getCompactPreviewDimensions(media)
    : getCompactMediaDimensions(media)
})
const frameStyle = computed(() => ({
  width: `${dimensions.value.width}px`,
  maxWidth: '100%',
  aspectRatio: String(dimensions.value.ratio),
}))
const backdropSource = computed(() =>
  imageAnimation.value ? source.value : generatedBackdropUrl.value,
)
const showBackdrop = computed(
  () => dimensions.value.letterboxed && Boolean(backdropSource.value),
)

function handleImageLoad(event) {
  actualWidth.value = Number(event.currentTarget?.naturalWidth || 0)
  actualHeight.value = Number(event.currentTarget?.naturalHeight || 0)
}

function handleMetadata(event) {
  actualWidth.value = Number(event.currentTarget?.videoWidth || 0)
  actualHeight.value = Number(event.currentTarget?.videoHeight || 0)
}

function captureBackdropFrame(event) {
  if (generatedBackdropUrl.value) return
  const video = event.currentTarget
  const width = Number(video?.videoWidth || 0)
  const height = Number(video?.videoHeight || 0)
  if (!video || !width || !height) return
  try {
    const canvas = document.createElement('canvas')
    const scale = Math.min(96 / width, 96 / height, 1)
    canvas.width = Math.max(1, Math.round(width * scale))
    canvas.height = Math.max(1, Math.round(height * scale))
    const context = canvas.getContext('2d')
    if (!context) return
    context.drawImage(video, 0, 0, canvas.width, canvas.height)
    generatedBackdropUrl.value = canvas.toDataURL('image/jpeg', 0.6)
  } catch {
    generatedBackdropUrl.value = ''
  }
}

watch(
  () => props.attachment.id,
  () => {
    failed.value = false
    actualWidth.value = 0
    actualHeight.value = 0
    generatedBackdropUrl.value = ''
  },
)
</script>
