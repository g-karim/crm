<template>
  <div
    v-if="attachments.length"
    data-attachment-renderer
    class="mt-2 grid max-w-full gap-2"
    :class="singleImage ? 'w-full' : 'w-full max-w-[28rem]'"
  >
    <div
      v-if="groups.images.length === 1 && !singleImage"
      data-mixed-single-image-row
      class="flex w-full min-w-0 items-stretch justify-center gap-2"
    >
      <span
        data-media-side-line
        aria-hidden="true"
        class="w-px shrink-0 rounded-full bg-outline-gray-1"
      />
      <div class="min-w-0 max-w-full">
        <ImageGrid :images="groups.images" />
      </div>
      <span
        data-media-side-line
        aria-hidden="true"
        class="w-px shrink-0 rounded-full bg-outline-gray-1"
      />
    </div>
    <ImageGrid v-else-if="groups.images.length" :images="groups.images" />

    <div v-for="sticker in groups.stickers" :key="sticker.id" class="max-w-52">
      <video
        v-if="isVideoSticker(sticker) && sticker.url && state(sticker).active"
        :src="sticker.url"
        class="max-h-52 max-w-52 object-contain"
        autoplay
        loop
        muted
        playsinline
      />
      <img
        v-else-if="
          isImageSticker(sticker) && sticker.url && state(sticker).active
        "
        :src="sticker.url"
        :alt="sticker.file_name || __('Стикер')"
        class="max-h-52 max-w-52 object-contain"
        loading="lazy"
      />
      <AttachmentCard v-else :attachment="sticker" icon="sticker" />
    </div>

    <template v-for="attachment in groups.other" :key="attachment.id">
      <MessengerAudioPlayer
        v-if="attachment.type === 'audio'"
        :attachment="attachment"
      />
      <VideoAttachment
        v-else-if="attachment.type === 'video'"
        :attachment="attachment"
      />
      <AttachmentCard v-else :attachment="attachment" />
    </template>
  </div>
</template>

<script setup>
import {
  getAttachmentState,
  groupMessengerAttachments,
  isSingleImageAttachmentSet,
} from '@/utils/messengerAttachments'
import { computed } from 'vue'
import AttachmentCard from './AttachmentCard.vue'
import ImageGrid from './ImageGrid.vue'
import MessengerAudioPlayer from './MessengerAudioPlayer.vue'
import VideoAttachment from './VideoAttachment.vue'

const props = defineProps({
  attachments: { type: Array, default: () => [] },
})
const groups = computed(() => groupMessengerAttachments(props.attachments))
const singleImage = computed(() =>
  isSingleImageAttachmentSet(props.attachments),
)

function state(attachment) {
  return getAttachmentState(attachment)
}

function isVideoSticker(attachment) {
  return attachment.mime_type?.startsWith('video/')
}

function isImageSticker(attachment) {
  return attachment.mime_type?.startsWith('image/')
}
</script>
