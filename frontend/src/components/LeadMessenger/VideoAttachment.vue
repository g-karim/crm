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
      <div
        v-if="loading"
        data-video-loading
        class="pointer-events-none absolute inset-0 z-20 grid place-items-center bg-black/20"
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
        class="absolute inset-0 z-10 size-full object-contain"
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
        @loadeddata="captureBackdropFrame"
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
        v-if="attachment.preview_url"
        :src="attachment.preview_url"
        :alt="title"
        class="absolute inset-0 z-10 size-full object-contain"
        loading="lazy"
        @load="handlePreviewImageLoad"
      />
      <video
        v-else-if="previewPlaybackUrl && !previewFailed"
        data-video-preview
        :src="previewPlaybackUrl"
        class="pointer-events-none absolute inset-0 z-10 size-full object-contain"
        muted
        preload="metadata"
        playsinline
        aria-hidden="true"
        tabindex="-1"
        @loadedmetadata="handlePreviewMetadata"
        @loadeddata="captureBackdropFrame"
        @seeked="captureBackdropFrame"
        @error="previewFailed = true"
      />
      <span v-else class="absolute inset-0 z-10 bg-black/80" />
      <span
        class="absolute inset-0 z-20 flex items-center justify-center bg-black/15 transition-colors group-hover:bg-black/25"
      >
        <span
          class="flex size-11 items-center justify-center rounded-full bg-black/65 text-white"
        >
          <PlayIcon class="size-6" />
        </span>
      </span>
      <span
        v-if="duration"
        class="absolute bottom-2 right-2 z-20 rounded bg-black/70 px-1.5 py-0.5 text-xs text-white"
      >
        {{ duration }}
      </span>
    </button>
    <div
      v-else-if="attachment.preview_url"
      data-video-frame
      class="relative block w-full overflow-hidden bg-black"
      :style="mediaAspectStyle"
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
        :src="attachment.preview_url"
        :alt="title"
        class="absolute inset-0 z-10 size-full object-contain"
        loading="lazy"
        @load="handlePreviewImageLoad"
      />
      <span
        v-if="duration"
        class="absolute bottom-2 right-2 z-20 rounded bg-black/70 px-1.5 py-0.5 text-xs text-white"
      >
        {{ duration }}
      </span>
    </div>
    <AttachmentCard v-else :attachment="cardAttachment" />

    <div
      v-if="showFooter"
      data-video-footer
      class="grid gap-2 px-3 py-2 text-sm"
    >
      <div v-if="statusLabel || localFailed" class="min-w-0">
        <div v-if="statusLabel" class="text-xs text-ink-gray-5">
          {{ statusLabel }}
        </div>
        <button
          v-if="localFailed && playbackUrl"
          type="button"
          class="text-xs text-ink-blue-6 hover:underline"
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
        data-video-external-action
        class="flex w-full items-center justify-center gap-2 rounded-md border border-outline-gray-2 bg-surface-base px-3 py-2 text-center text-sm font-medium text-ink-blue-6 transition-colors hover:bg-surface-gray-2"
      >
        <ExternalLinkIcon class="size-4 shrink-0" />
        {{ actionLabel }}
      </a>
    </div>
  </div>
</template>

<script setup>
import {
  formatAttachmentDuration,
  getAttachmentState,
  getCompactMediaDimensions,
  getCompactPreviewDimensions,
  getMessengerAttachmentTitle,
  getVideoExternalAction,
  getVideoPlaybackUrl,
} from '@/utils/messengerAttachments'
import LoadingIndicator from '@/components/Icons/LoadingIndicator.vue'
import ExternalLinkIcon from '@/components/Icons/ExternalLinkIcon.vue'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import PlayIcon from '~icons/lucide/play'
import AttachmentCard from './AttachmentCard.vue'

const props = defineProps({
  attachment: { type: Object, required: true },
  playbackScope: { type: String, default: '' },
  provider: { type: String, default: '' },
  compactPreview: { type: Boolean, default: false },
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
const generatedBackdropUrl = ref('')
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
    : getVideoExternalAction(props.attachment),
)
const immediateExternalFallback = computed(() =>
  Boolean(
    props.provider === 'vk_direct' &&
    action.value &&
    ['external', 'provider_embed'].includes(props.attachment.video_source),
  ),
)
const cardAttachment = computed(() => ({
  ...props.attachment,
  status: immediateExternalFallback.value
    ? 'external'
    : props.attachment.status,
  open_url: '',
  url: '',
}))
const title = computed(() => getMessengerAttachmentTitle(props.attachment))
const duration = computed(() =>
  formatAttachmentDuration(
    actualDurationMs.value || props.attachment.duration_ms,
  ),
)
const mediaDimensions = computed(() => {
  let media = {
    width: actualWidth.value || props.attachment.width,
    height: actualHeight.value || props.attachment.height,
  }
  return props.compactPreview
    ? getCompactPreviewDimensions(media)
    : getCompactMediaDimensions(media)
})
const mediaContainerStyle = computed(() => ({
  width: `${mediaDimensions.value.width}px`,
  maxWidth: '100%',
}))
const mediaAspectStyle = computed(() => ({
  aspectRatio: String(mediaDimensions.value.ratio),
}))
const backdropSource = computed(
  () => props.attachment.preview_url || generatedBackdropUrl.value,
)
const showBackdrop = computed(
  () => mediaDimensions.value.letterboxed && Boolean(backdropSource.value),
)
const actionLabel = computed(() =>
  props.provider === 'vk_direct'
    ? __('Смотреть в VK Видео')
    : __('Открыть источник'),
)
const statusLabel = computed(() => {
  if (immediateExternalFallback.value) return __('Доступно только во VK')
  if (state.value.busy) return state.value.label
  if (state.value.unsupported) return __('Формат видео не поддерживается')
  if (props.provider === 'vk_direct' && !playable.value && action.value)
    return __('Доступно только во VK')
  if (!playable.value && !action.value) return __('Видео недоступно')
  return ''
})
const showFooter = computed(
  () =>
    Boolean(statusLabel.value) || Boolean(action.value) || localFailed.value,
)

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

function handlePreviewImageLoad(event) {
  actualWidth.value = Number(event.currentTarget?.naturalWidth || 0)
  actualHeight.value = Number(event.currentTarget?.naturalHeight || 0)
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

function captureBackdropFrame(event) {
  if (props.attachment.preview_url || generatedBackdropUrl.value) return
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
    generatedBackdropUrl.value = ''
    previewFailed.value = false
  },
)
onBeforeUnmount(() => {
  stopPlayback()
  window.removeEventListener('crm-messenger-video-play', handleOtherPlayback)
})
</script>
