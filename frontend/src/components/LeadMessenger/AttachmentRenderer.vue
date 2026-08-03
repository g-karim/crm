<template>
  <div
    v-if="attachments.length"
    data-attachment-renderer
    class="mt-2 grid max-w-full gap-2"
    :class="
      singleImage ? 'w-full' : hasVideo ? 'w-[28rem]' : 'w-full max-w-[28rem]'
    "
  >
    <template v-for="segment in segments" :key="segment.key">
      <div
        v-if="
          segment.type === 'images' &&
          segment.items.length === 1 &&
          !singleImage
        "
        data-mixed-single-image-row
        class="flex w-full min-w-0 items-stretch justify-center gap-2"
      >
        <span
          data-media-side-line
          aria-hidden="true"
          class="w-px shrink-0 rounded-full bg-outline-gray-1"
        />
        <div class="min-w-0 max-w-full">
          <ImageGrid :images="segment.items" @open-image="openImage" />
        </div>
        <span
          data-media-side-line
          aria-hidden="true"
          class="w-px shrink-0 rounded-full bg-outline-gray-1"
        />
      </div>
      <ImageGrid
        v-else-if="segment.type === 'images'"
        :images="segment.items"
        @open-image="openImage"
      />
      <div v-else-if="segment.type === 'sticker'" class="max-w-52">
        <VkLottieSticker
          v-if="isLottieSticker(segment.attachment)"
          :attachment="segment.attachment"
        />
        <video
          v-else-if="
            isVideoSticker(segment.attachment) &&
            segment.attachment.url &&
            state(segment.attachment).active
          "
          :src="segment.attachment.url"
          class="max-h-52 max-w-52 object-contain"
          autoplay
          loop
          muted
          playsinline
        />
        <img
          v-else-if="
            isImageSticker(segment.attachment) &&
            segment.attachment.url &&
            state(segment.attachment).active
          "
          :src="segment.attachment.url"
          :alt="segment.attachment.file_name || __('Стикер')"
          class="max-h-52 max-w-52 object-contain"
          loading="lazy"
        />
        <AttachmentCard
          v-else
          :attachment="segment.attachment"
          icon="sticker"
        />
      </div>
      <MessengerAudioPlayer
        v-else-if="segment.type === 'audio'"
        :attachment="segment.attachment"
      />
      <VideoAttachment
        v-else-if="segment.type === 'video'"
        :attachment="segment.attachment"
        :playback-scope="playbackScope"
        :provider="provider"
      />
      <AttachmentCard v-else :attachment="segment.attachment" />
    </template>
    <ImageLightbox
      v-if="lightboxOpen"
      :images="availableImages"
      :initialIndex="lightboxIndex"
      @close="lightboxOpen = false"
    />
  </div>
</template>

<script setup>
import {
  buildMessengerAttachmentSegments,
  getAttachmentState,
  isSingleImageAttachmentSet,
} from '@/utils/messengerAttachments'
import { computed, ref } from 'vue'
import AttachmentCard from './AttachmentCard.vue'
import ImageGrid from './ImageGrid.vue'
import ImageLightbox from './ImageLightbox.vue'
import MessengerAudioPlayer from './MessengerAudioPlayer.vue'
import VideoAttachment from './VideoAttachment.vue'
import VkLottieSticker from './VkLottieSticker.vue'

const props = defineProps({
  attachments: { type: Array, default: () => [] },
  playbackScope: { type: String, default: '' },
  provider: { type: String, default: '' },
})
const segments = computed(() =>
  buildMessengerAttachmentSegments(props.attachments),
)
const singleImage = computed(() =>
  isSingleImageAttachmentSet(props.attachments),
)
const hasVideo = computed(() =>
  props.attachments.some((attachment) => attachment.type === 'video'),
)
const availableImages = computed(() =>
  props.attachments.filter(
    (attachment) =>
      attachment.type === 'image' &&
      attachment.url &&
      getAttachmentState(attachment).active,
  ),
)
const lightboxOpen = ref(false)
const lightboxIndex = ref(0)

function openImage(image) {
  let index = availableImages.value.findIndex((item) => item.id === image.id)
  if (index < 0) return
  lightboxIndex.value = index
  lightboxOpen.value = true
}

function state(attachment) {
  return getAttachmentState(attachment)
}

function isVideoSticker(attachment) {
  return attachment.mime_type?.startsWith('video/')
}

function isImageSticker(attachment) {
  return attachment.mime_type?.startsWith('image/')
}

function isLottieSticker(attachment) {
  return (
    attachment.mime_type === 'application/json' && attachment.is_animated
  )
}
</script>
