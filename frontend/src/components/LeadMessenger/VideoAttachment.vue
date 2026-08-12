<template>
  <div
    class="max-w-full overflow-hidden rounded-lg bg-surface-gray-2"
    :style="mediaContainerStyle"
  >
    <div
      v-if="mode === 'local'"
      data-video-frame
      class="relative w-full overflow-hidden bg-black"
      :style="mediaAspectStyle"
    >
      <div
        v-if="loading"
        data-video-loading
        class="pointer-events-none absolute inset-0 z-10 grid place-items-center bg-black/20"
        role="status"
        :aria-label="__('Загрузка видео')"
      >
        <span
          class="grid size-10 place-items-center rounded-full bg-black/65 text-white shadow-sm"
        >
          <LoadingIndicator class="size-5" />
        </span>
      </div>
      <video
        ref="videoElement"
        :src="playbackUrl"
        :poster="attachment.preview_url || undefined"
        class="absolute inset-0 size-full bg-black object-contain"
        controls
        preload="none"
        playsinline
        @loadstart="startLoading"
        @waiting="startLoading"
        @seeking="startLoading"
        @canplay="finishLoading"
        @playing="finishLoading"
        @seeked="finishLoading"
        @loadedmetadata="handleLoadedMetadata"
        @play="announcePlayback"
        @error="handleLocalError"
      />
    </div>
    <button
      v-else-if="playable"
      type="button"
      data-video-frame
      class="group relative block w-full overflow-hidden bg-black text-left"
      :style="mediaAspectStyle"
      :aria-label="__('Воспроизвести видео')"
      @click="activate"
    >
      <img
        v-if="attachment.preview_url"
        :src="attachment.preview_url"
        :alt="title"
        class="absolute inset-0 size-full object-contain"
        loading="lazy"
      />
      <video
        v-else-if="previewPlaybackUrl && !previewFailed"
        data-video-preview
        :src="previewPlaybackUrl"
        class="pointer-events-none absolute inset-0 size-full bg-black object-contain"
        muted
        preload="metadata"
        playsinline
        aria-hidden="true"
        tabindex="-1"
        @loadedmetadata="handlePreviewMetadata"
        @error="previewFailed = true"
      />
      <span v-else class="absolute inset-0 bg-black/80" />
      <span
        class="absolute inset-0 flex items-center justify-center bg-black/15 transition-colors group-hover:bg-black/25"
      >
        <span
          class="flex size-11 items-center justify-center rounded-full bg-black/65 text-white"
        >
          <PlayIcon class="size-6" />
        </span>
      </span>
      <span
        v-if="duration"
        class="absolute bottom-2 right-2 rounded bg-black/70 px-1.5 py-0.5 text-xs text-white"
      >
        {{ duration }}
      </span>
    </button>
    <div
      v-else-if="attachment.preview_url"
      data-video-frame
      class="relative w-full overflow-hidden bg-black"
      :style="mediaAspectStyle"
    >
      <img
        :src="attachment.preview_url"
        :alt="title"
        class="absolute inset-0 size-full object-contain"
        loading="lazy"
      />
      <span
        v-if="duration"
        class="absolute bottom-2 right-2 rounded bg-black/70 px-1.5 py-0.5 text-xs text-white"
      >
        {{ duration }}
      </span>
    </div>
    <AttachmentCard v-else :attachment="cardAttachment" />

    <div
      v-if="title || action || localFailed"
      class="flex items-center justify-between gap-3 px-3 py-2 text-sm"
    >
      <div class="min-w-0">
        <div v-if="title" class="truncate font-medium text-ink-gray-8">
          {{ title }}
        </div>
        <div v-if="statusLabel" class="text-xs text-ink-gray-5">
          {{ statusLabel }}
        </div>
        <button
          v-if="localFailed && playbackUrl"
          type="button"
          class="text-xs text-ink-blue-3 hover:underline"
          @click="retryLocal"
        >
          {{ __('Повторить воспроизведение') }}
        </button>
      </div>
      <a
        v-if="action"
        :href="action"
        target="_blank"
        rel="noopener noreferrer"
        class="shrink-0 text-ink-blue-3 hover:underline"
      >
        {{ actionLabel }}
      </a>
    </div>
  </div>
</template>

<script setup>
import {
  formatAttachmentDuration,
  getAttachmentAction,
  getAttachmentState,
  getCompactMediaDimensions,
  getMessengerAttachmentTitle,
  getVideoPlaybackUrl,
} from '@/utils/messengerAttachments'
import LoadingIndicator from '@/components/Icons/LoadingIndicator.vue'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import PlayIcon from '~icons/lucide/play'
import AttachmentCard from './AttachmentCard.vue'

const props = defineProps({
  attachment: { type: Object, required: true },
  playbackScope: { type: String, default: '' },
  provider: { type: String, default: '' },
})

const instanceId = `messenger-video-${Math.random().toString(36).slice(2)}`
const videoElement = ref(null)
const mode = ref('')
const loading = ref(false)
const localFailed = ref(false)
const previewFailed = ref(false)
const actualDurationMs = ref(0)
const actualWidth = ref(0)
const actualHeight = ref(0)
const state = computed(() => getAttachmentState(props.attachment))
const playbackUrl = computed(() => {
  if (
    props.provider === 'vk_direct' &&
    props.attachment.mime_type !== 'video/mp4'
  )
    return ''
  return getVideoPlaybackUrl(props.attachment)
})
const previewPlaybackUrl = computed(() => {
  if (!playbackUrl.value) return ''
  return `${playbackUrl.value.split('#', 1)[0]}#t=0.001`
})
const playable = computed(() =>
  Boolean(playbackUrl.value && !localFailed.value),
)
const action = computed(() =>
  props.provider === 'max_direct' || playable.value
    ? ''
    : getAttachmentAction(props.attachment),
)
const cardAttachment = computed(() => ({
  ...props.attachment,
  open_url: '',
  url: '',
}))
const title = computed(() => getMessengerAttachmentTitle(props.attachment))
const duration = computed(() =>
  formatAttachmentDuration(
    actualDurationMs.value || props.attachment.duration_ms,
  ),
)
const mediaDimensions = computed(() =>
  getCompactMediaDimensions({
    width: actualWidth.value || props.attachment.width,
    height: actualHeight.value || props.attachment.height,
  }),
)
const mediaContainerStyle = computed(() => ({
  width: `${mediaDimensions.value.width}px`,
  maxWidth: '100%',
}))
const mediaAspectStyle = computed(() => ({
  aspectRatio: String(mediaDimensions.value.ratio),
}))
const actionLabel = computed(() =>
  props.provider === 'vk_direct'
    ? __('Смотреть в VK Видео')
    : __('Открыть источник'),
)
const statusLabel = computed(() => {
  if (state.value.busy) return state.value.label
  if (state.value.unsupported) return __('Формат видео не поддерживается')
  if (props.provider === 'vk_direct' && !playable.value && action.value)
    return __('Видео доступно только во VK')
  if (!playable.value && !action.value) return __('Видео недоступно')
  return ''
})

async function activate() {
  if (!playbackUrl.value || localFailed.value) return
  mode.value = 'local'
  loading.value = true
  announcePlayback()
  if (mode.value === 'local') {
    await nextTick()
    videoElement.value?.play?.().catch(() => {
      loading.value = false
    })
  }
}

function announcePlayback() {
  window.dispatchEvent(
    new CustomEvent('crm-messenger-video-play', { detail: instanceId }),
  )
}

function startLoading() {
  loading.value = true
}

function finishLoading() {
  loading.value = false
}

function stopPlayback() {
  videoElement.value?.pause?.()
  mode.value = ''
  loading.value = false
}

function handleOtherPlayback(event) {
  if (event.detail !== instanceId) stopPlayback()
}

function handleLocalError() {
  localFailed.value = true
  loading.value = false
  mode.value = ''
}

function handleLoadedMetadata(event) {
  const seconds = Number(event.currentTarget?.duration)
  actualWidth.value = Number(event.currentTarget?.videoWidth || 0)
  actualHeight.value = Number(event.currentTarget?.videoHeight || 0)
  actualDurationMs.value =
    Number.isFinite(seconds) && seconds > 0 ? Math.round(seconds * 1000) : 0
}

function handlePreviewMetadata(event) {
  handleLoadedMetadata(event)
  const preview = event.currentTarget
  const seconds = Number(preview?.duration)
  if (!preview || !Number.isFinite(seconds) || seconds <= 0) return
  try {
    preview.currentTime = Math.min(0.1, seconds / 2)
  } catch {
    // The media fragment still requests the first decodable frame.
  }
}

function retryLocal() {
  localFailed.value = false
  activate()
}

window.addEventListener('crm-messenger-video-play', handleOtherPlayback)
watch(() => props.playbackScope, stopPlayback)
watch(
  () => [props.attachment.id, playbackUrl.value],
  () => {
    actualDurationMs.value = 0
    actualWidth.value = 0
    actualHeight.value = 0
    previewFailed.value = false
  },
)
onBeforeUnmount(() => {
  stopPlayback()
  window.removeEventListener('crm-messenger-video-play', handleOtherPlayback)
})
</script>
