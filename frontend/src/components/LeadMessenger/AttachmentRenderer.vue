<template>
  <div
    v-if="attachments.length"
    data-attachment-renderer
    class="mt-2 grid max-w-full gap-2"
    :class="
      compactPreview
        ? 'w-full min-w-0'
        : singleImage
          ? 'w-fit'
          : 'w-fit max-w-[20rem]'
    "
  >
    <template v-for="segment in segments" :key="segment.key">
      <ImageGrid
        v-if="segment.type === 'images'"
        :images="segment.items"
        :compact-preview="compactPreview"
        @open-image="openImage"
      />
      <AnimatedMediaAttachment
        v-else-if="segment.type === 'animation'"
        :attachment="segment.attachment"
        :compact-preview="compactPreview"
        @open-media="openMedia"
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
          :alt="__(getMessengerAttachmentTitle(segment.attachment))"
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
        :compact-preview="compactPreview"
      />
      <VideoAttachment
        v-else-if="segment.type === 'video'"
        :attachment="segment.attachment"
        :playback-scope="playbackScope"
        :provider="provider"
        :compact-preview="compactPreview"
      />
      <LocationAttachment
        v-else-if="segment.type === 'location'"
        :attachment="segment.attachment"
      />
      <ContactAttachment
        v-else-if="segment.type === 'contact'"
        :contact="segment.attachment.contact"
      />
      <AttachmentCard v-else :attachment="segment.attachment" />
    </template>
    <MediaLightbox
      v-if="lightboxOpen"
      :items="availableMedia"
      :initialIndex="lightboxIndex"
      @close="lightboxOpen = false"
    />
  </div>
</template>

<script setup>
import {
  buildMessengerAttachmentSegments,
  getAttachmentState,
  getMessengerAttachmentTitle,
  isSingleImageAttachmentSet,
} from '@/utils/messengerAttachments'
import { computed, ref } from 'vue'
import AnimatedMediaAttachment from './AnimatedMediaAttachment.vue'
import AttachmentCard from './AttachmentCard.vue'
import ContactAttachment from './ContactAttachment.vue'
import ImageGrid from './ImageGrid.vue'
import MediaLightbox from './MediaLightbox.vue'
import MessengerAudioPlayer from './MessengerAudioPlayer.vue'
import LocationAttachment from './LocationAttachment.vue'
import VideoAttachment from './VideoAttachment.vue'
import VkLottieSticker from './VkLottieSticker.vue'

const props = defineProps({
  attachments: { type: Array, default: () => [] },
  playbackScope: { type: String, default: '' },
  provider: { type: String, default: '' },
  compactPreview: { type: Boolean, default: false },
})
const segments = computed(() =>
  buildMessengerAttachmentSegments(props.attachments),
)
const singleImage = computed(() =>
  isSingleImageAttachmentSet(props.attachments),
)
const availableMedia = computed(() =>
  props.attachments.flatMap((attachment) => {
    if (!getAttachmentState(attachment).active) return []
    if (attachment.type === 'image' && attachment.url) {
      return [
        {
          id: attachment.id,
          kind: 'image',
          url: attachment.url,
          download_url: attachment.download_url,
          file_name: attachment.file_name,
        },
      ]
    }
    if (attachment.type === 'video' && attachment.is_animated) {
      let url = attachment.playback_url
      if (!url) return []
      return [
        {
          id: attachment.id,
          kind: 'animation',
          url,
          download_url: attachment.download_url,
          file_name: attachment.file_name,
        },
      ]
    }
    return []
  }),
)
const lightboxOpen = ref(false)
const lightboxIndex = ref(0)

function openImage(image) {
  openMedia(image)
}

function openMedia(attachment) {
  let index = availableMedia.value.findIndex(
    (item) => item.id === attachment?.id,
  )
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
  return attachment.mime_type === 'application/json' && attachment.is_animated
}
</script>
