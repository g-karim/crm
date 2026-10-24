<template>
  <div
    data-sticker-attachment
    class="relative flex size-52 max-w-full flex-col items-center justify-center justify-self-start gap-2"
  >
    <VkLottieSticker
      v-if="lottieSticker && state.active"
      :attachment="attachment"
    />
    <video
      v-else-if="videoSticker && playable"
      data-sticker-video
      :src="attachment.url"
      :aria-label="__(title)"
      class="size-full object-contain"
      autoplay
      loop
      muted
      playsinline
      @loadeddata="finishLoading"
      @playing="finishLoading"
      @error="failLocal"
    />
    <img
      v-else-if="imageSticker && playable"
      data-sticker-image
      :src="attachment.url"
      :alt="__(title)"
      class="size-full object-contain"
      @load="finishLoading"
      @error="failLocal"
    />
    <template v-else>
      <AttachmentCard :attachment="fallbackAttachment" icon="sticker" />
      <button
        v-if="localFailed && state.active && attachment.url"
        type="button"
        class="min-h-8 rounded px-2 text-sm text-ink-blue-6 focus-visible:ring-2"
        @click.stop="retryLocal"
      >
        {{ __('Try Again') }}
      </button>
    </template>
    <div
      v-if="localLoading"
      data-sticker-loading
      class="pointer-events-none absolute inset-0 grid place-items-center"
      role="status"
      :aria-label="__('Loading...')"
    >
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>
  </div>
</template>

<script setup>
import LoadingIndicator from '@/components/Icons/LoadingIndicator.vue'
import {
  getAttachmentState,
  getMessengerAttachmentTitle,
} from '@/utils/messengerAttachments'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import AttachmentCard from './AttachmentCard.vue'
import VkLottieSticker from './VkLottieSticker.vue'

const props = defineProps({
  attachment: { type: Object, required: true },
})
const state = computed(() => getAttachmentState(props.attachment))
const title = computed(() => getMessengerAttachmentTitle(props.attachment))
const lottieSticker = computed(
  () =>
    props.attachment.mime_type === 'application/json' &&
    props.attachment.is_animated,
)
const videoSticker = computed(() =>
  String(props.attachment.mime_type || '').startsWith('video/'),
)
const imageSticker = computed(() =>
  String(props.attachment.mime_type || '').startsWith('image/'),
)
const localFailed = ref(false)
const localLoading = ref(false)
let loadingTimer = null
const playable = computed(
  () => state.value.active && props.attachment.url && !localFailed.value,
)
const fallbackAttachment = computed(() =>
  localFailed.value ||
  (state.value.active &&
    (!props.attachment.url ||
      (!videoSticker.value && !imageSticker.value && !lottieSticker.value)))
    ? {
        ...props.attachment,
        status: localFailed.value ? 'failed' : 'unsupported',
        display_title: 'Sticker unavailable',
      }
    : props.attachment,
)

function finishLoading() {
  clearTimeout(loadingTimer)
  loadingTimer = null
  localLoading.value = false
}

function failLocal() {
  finishLoading()
  localFailed.value = true
}

function retryLocal() {
  finishLoading()
  localFailed.value = false
  if (
    !state.value.active ||
    !props.attachment.url ||
    (!videoSticker.value && !imageSticker.value)
  )
    return
  localLoading.value = true
  loadingTimer = setTimeout(failLocal, 20000)
}

watch(
  () => [
    props.attachment.id,
    props.attachment.url,
    state.value.status,
    props.attachment.mime_type,
  ],
  retryLocal,
  { immediate: true },
)
onBeforeUnmount(finishLoading)
</script>
