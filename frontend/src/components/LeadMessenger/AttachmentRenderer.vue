<template>
  <div
    v-if="attachments.length"
    data-attachment-renderer
    class="mt-2 grid min-w-0 grid-cols-1 gap-2"
    :class="
      compactPreview
        ? singleSticker
          ? 'w-fit min-w-0 max-w-full'
          : 'w-full max-w-full'
        : singleImage
          ? 'w-fit max-w-full'
          : singleLocation
            ? 'w-full max-w-full'
            : singleAudio || singleFile
              ? 'w-full max-w-full'
              : 'max-w-[20rem]'
    "
  >
    <template v-for="segment in segments" :key="segment.key">
      <ImageGrid
        v-if="segment.type === 'images'"
        :images="segment.items"
        :compact-preview="compactPreview"
        :provider="provider"
        :outbound="outbound"
        @open-image="openImage"
      />
      <AnimatedMediaAttachment
        v-else-if="segment.type === 'animation'"
        :attachment="segment.attachment"
        :compact-preview="compactPreview"
        @open-media="openMedia"
      />
      <StickerAttachment
        v-else-if="segment.type === 'sticker'"
        :attachment="segment.attachment"
      />
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
  isSingleAudioAttachmentSet,
  isSingleFileAttachmentSet,
  isSingleImageAttachmentSet,
  isSingleLocationAttachmentSet,
  isSingleStickerAttachmentSet,
} from '@/utils/messengerAttachments'
import { computed, ref } from 'vue'
import AnimatedMediaAttachment from './AnimatedMediaAttachment.vue'
import AttachmentCard from './AttachmentCard.vue'
import ContactAttachment from './ContactAttachment.vue'
import ImageGrid from './ImageGrid.vue'
import MediaLightbox from './MediaLightbox.vue'
import MessengerAudioPlayer from './MessengerAudioPlayer.vue'
import LocationAttachment from './LocationAttachment.vue'
import StickerAttachment from './StickerAttachment.vue'
import VideoAttachment from './VideoAttachment.vue'

const props = defineProps({
  attachments: { type: Array, default: () => [] },
  playbackScope: { type: String, default: '' },
  provider: { type: String, default: '' },
  outbound: { type: Boolean, default: false },
  compactPreview: { type: Boolean, default: false },
})
const segments = computed(() =>
  buildMessengerAttachmentSegments(
    props.attachments.map((attachment) =>
      props.provider === 'wazzup'
        ? { ...attachment, provider: props.provider }
        : attachment,
    ),
  ),
)
const singleImage = computed(() =>
  isSingleImageAttachmentSet(props.attachments),
)
const singleSticker = computed(() =>
  isSingleStickerAttachmentSet(props.attachments),
)
const singleLocation = computed(() =>
  isSingleLocationAttachmentSet(props.attachments),
)
const singleAudio = computed(() =>
  isSingleAudioAttachmentSet(props.attachments),
)
const singleFile = computed(() => isSingleFileAttachmentSet(props.attachments))
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
</script>
