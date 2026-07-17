<template>
  <div v-if="attachments.length" class="mt-2 grid w-full max-w-[28rem] gap-2">
    <ImageGrid v-if="groups.images.length" :images="groups.images" />

    <div
      v-for="sticker in groups.stickers"
      :key="sticker.id"
      class="max-w-52"
    >
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
        v-else-if="isImageSticker(sticker) && sticker.url && state(sticker).active"
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
