<template>
  <div
    data-sticker-attachment
    class="relative flex size-40 max-w-full flex-col items-center justify-center justify-self-start gap-2"
  >
    <VkLottieSticker
      v-if="lottieSticker && state.active"
      :attachment="attachment"
    />
    <video
      v-else-if="videoSticker && playable"
      ref="mediaElement"
      data-sticker-video
      :src="source"
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
      ref="mediaElement"
      data-sticker-image
      :src="source"
      :alt="__(title)"
      class="size-full object-contain"
      @load="finishLoading"
      @error="failLocal"
    />
    <div
      v-else
      data-sticker-fallback
      :data-status="
        localFailed ? 'failed' : state.active ? 'unsupported' : state.status
      "
      class="flex size-full flex-col items-center justify-center gap-2 rounded-lg bg-surface-gray-2 p-2 text-center text-xs text-ink-gray-5"
    >
      <LoadingIndicator v-if="state.busy" class="size-5" />
      <span
        class="max-w-full break-words"
        :role="state.busy ? 'status' : undefined"
      >
        {{
          __(
            state.busy
              ? state.label
              : attachment.fallback_text || 'Sticker unavailable',
          )
        }}
      </span>
      <button
        v-if="localFailed && state.active && source"
        type="button"
        class="min-h-8 rounded px-2 text-sm text-ink-blue-6 focus-visible:ring-2"
        @click.stop="retryLocal"
      >
        {{ __('Try Again') }}
      </button>
    </div>
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
import { computed, nextTick, ref, watch } from 'vue'
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
const source = computed(() =>
  videoSticker.value
    ? props.attachment.playback_url || props.attachment.url || ''
    : props.attachment.url || '',
)
const localFailed = ref(false)
const localLoading = ref(false)
const mediaElement = ref(null)
const playable = computed(
  () => state.value.active && source.value && !localFailed.value,
)
function finishLoading() {
  localLoading.value = false
}

function failLocal() {
  finishLoading()
  localFailed.value = true
}

async function retryLocal() {
  finishLoading()
  localFailed.value = false
  if (
    !state.value.active ||
    !source.value ||
    (!videoSticker.value && !imageSticker.value)
  )
    return
  localLoading.value = true
  await nextTick()
  // A cached image can finish before Vue attaches its load listener. A DTO
  // refresh must also keep a successfully rendered sticker in its ready state.
  let media = mediaElement.value
  if (
    (imageSticker.value && media?.complete && media.naturalWidth > 0) ||
    (videoSticker.value && media?.readyState >= 2)
  ) {
    finishLoading()
  }
}

watch(
  [
    () => props.attachment.id,
    () => source.value,
    () => state.value.status,
    () => props.attachment.mime_type,
  ],
  retryLocal,
  { immediate: true },
)
</script>
