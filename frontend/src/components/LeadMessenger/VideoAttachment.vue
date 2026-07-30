<template>
  <div
    class="w-full max-w-[28rem] overflow-hidden rounded-lg bg-surface-gray-2"
  >
    <video
      v-if="mode === 'local'"
      ref="videoElement"
      :src="playbackUrl"
      :poster="attachment.preview_url || undefined"
      class="max-h-[22rem] w-full bg-black object-contain"
      controls
      preload="none"
      playsinline
      @canplay="loading = false"
      @loadedmetadata="handleLoadedMetadata"
      @play="announcePlayback"
      @error="handleLocalError"
    />
    <div
      v-else-if="mode === 'embed'"
      class="relative aspect-video w-full bg-black"
    >
      <LoadingIndicator
        v-if="loading"
        class="absolute left-1/2 top-1/2 z-10 size-6 -translate-x-1/2 -translate-y-1/2 text-white"
      />
      <iframe
        :src="attachment.embed_url"
        :title="title"
        class="size-full border-0"
        allow="autoplay; fullscreen; picture-in-picture; encrypted-media"
        sandbox="allow-scripts allow-same-origin allow-presentation"
        referrerpolicy="no-referrer"
        allowfullscreen
        @load="loading = false"
      />
    </div>
    <button
      v-else-if="playable"
      type="button"
      class="group relative block min-h-40 w-full overflow-hidden text-left"
      :aria-label="__('Воспроизвести видео')"
      @click="activate"
    >
      <img
        v-if="attachment.preview_url"
        :src="attachment.preview_url"
        :alt="title"
        class="max-h-[22rem] w-full object-contain"
        loading="lazy"
      />
      <video
        v-else-if="previewPlaybackUrl && !previewFailed"
        data-video-preview
        :src="previewPlaybackUrl"
        class="pointer-events-none aspect-video max-h-[22rem] w-full bg-black object-contain"
        muted
        preload="metadata"
        playsinline
        aria-hidden="true"
        tabindex="-1"
        @loadedmetadata="handlePreviewMetadata"
        @error="previewFailed = true"
      />
      <span v-else class="block aspect-video w-full bg-black/80" />
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
    <div v-else-if="attachment.preview_url" class="relative">
      <img
        :src="attachment.preview_url"
        :alt="title"
        class="max-h-[22rem] w-full object-contain"
        loading="lazy"
      />
      <span
        v-if="duration"
        class="absolute bottom-2 right-2 rounded bg-black/70 px-1.5 py-0.5 text-xs text-white"
      >
        {{ duration }}
      </span>
    </div>
    <AttachmentCard v-else :attachment="attachment" />

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
        {{ __('Открыть источник') }}
      </a>
    </div>
  </div>
</template>

<script setup>
import {
  formatAttachmentDuration,
  getAttachmentAction,
  getAttachmentState,
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
const state = computed(() => getAttachmentState(props.attachment))
const playbackUrl = computed(() => getVideoPlaybackUrl(props.attachment))
const previewPlaybackUrl = computed(() => {
  if (!playbackUrl.value) return ''
  return `${playbackUrl.value.split('#', 1)[0]}#t=0.001`
})
const embedAvailable = computed(
  () =>
    state.value.active &&
    props.attachment.embed_available &&
    Boolean(props.attachment.embed_url),
)
const playable = computed(() =>
  Boolean((playbackUrl.value && !localFailed.value) || embedAvailable.value),
)
const action = computed(() =>
  props.provider === 'max_direct' ? '' : getAttachmentAction(props.attachment),
)
const title = computed(
  () =>
    props.attachment.title ||
    props.attachment.file_name ||
    __('Видеосообщение'),
)
const duration = computed(() =>
  formatAttachmentDuration(
    actualDurationMs.value || props.attachment.duration_ms,
  ),
)
const statusLabel = computed(() => {
  if (state.value.busy) return state.value.label
  if (state.value.unsupported) return __('Формат видео не поддерживается')
  if (!playable.value && !action.value) return __('Видео недоступно')
  return ''
})

async function activate() {
  mode.value = playbackUrl.value && !localFailed.value ? 'local' : 'embed'
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
  if (embedAvailable.value) {
    mode.value = 'embed'
    loading.value = true
  } else {
    mode.value = ''
  }
}

function handleLoadedMetadata(event) {
  const seconds = Number(event.currentTarget?.duration)
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
    previewFailed.value = false
  },
)
onBeforeUnmount(() => {
  stopPlayback()
  window.removeEventListener('crm-messenger-video-play', handleOtherPlayback)
})
</script>
