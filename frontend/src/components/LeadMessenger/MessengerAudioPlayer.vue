<template>
  <div data-messenger-audio class="w-full min-w-0 max-w-full">
    <div
      v-if="playable"
      class="mb-2 flex min-w-0 items-center gap-2 text-sm font-medium text-ink-gray-8"
    >
      <AudioLinesIcon class="size-4 shrink-0" />
      <span class="truncate">{{ __(title) }}</span>
    </div>

    <audio
      v-if="playable"
      :key="`${attachment.id || ''}:${attachment.url}`"
      ref="audio"
      class="hidden"
      :src="attachment.url"
      :volume="volume"
      :muted="muted"
      preload="metadata"
      @loadstart="startLoading"
      @loadedmetadata="onMetadata"
      @durationchange="onMetadata"
      @timeupdate="onTimeUpdate"
      @waiting="startLoading"
      @canplay="finishLoading"
      @playing="onPlaying"
      @pause="onPause"
      @ended="onEnded"
      @error="onError"
      @volumechange="onVolumeChange"
    />

    <template v-if="playable">
      <div class="flex min-w-0 items-center gap-2">
        <Button
          class="!size-10 shrink-0 !p-0"
          variant="ghost"
          :icon="playing ? 'pause' : 'play'"
          :aria-label="playing ? __('Pause') : __('Play')"
          :disabled="Boolean(error)"
          @click="togglePlayback"
        />
        <div class="min-w-0 flex-1">
          <div
            v-if="bars.length"
            class="flex h-8 touch-none cursor-pointer items-center gap-[2px] rounded px-1 outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
            role="slider"
            tabindex="0"
            :aria-disabled="!duration || Boolean(error)"
            :aria-label="__('Playback Position')"
            :aria-valuemin="0"
            :aria-valuemax="Math.round(duration)"
            :aria-valuenow="Math.round(currentTime)"
            :aria-valuetext="`${formatAudioTime(currentTime)} / ${formatAudioTime(duration)}`"
            @pointerdown="seekDrag.pointerDown"
            @pointermove="seekDrag.pointerMove"
            @pointerup="seekDrag.pointerUp"
            @pointercancel="seekDrag.pointerCancel"
            @keydown="seekFromKeyboard"
          >
            <span
              v-for="(bar, index) in bars"
              :key="index"
              class="flex-1 rounded-full"
              :class="
                barProgress(index) <= progress
                  ? 'bg-surface-blue-7'
                  : 'bg-surface-gray-5'
              "
              :style="{ height: `${2 + bar * 22}px` }"
            />
          </div>
          <input
            v-else
            class="audio-seek-range h-8 w-full rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
            type="range"
            min="0"
            max="1"
            step="0.001"
            :value="progress"
            :style="{ '--seek-progress': `${progress * 100}%` }"
            :aria-label="__('Playback Position')"
            :disabled="!duration || Boolean(error)"
            @input="seekToFraction($event.target.value)"
          />
        </div>
      </div>

      <div class="flex min-w-0 flex-wrap items-center gap-2">
        <LoadingIndicator v-if="loading && !error" class="size-4 shrink-0" />
        <span class="shrink-0 text-xs tabular-nums text-ink-gray-5">
          {{ formatAudioTime(currentTime) }} / {{ formatAudioTime(duration) }}
        </span>
        <div class="ml-auto flex min-w-0 items-center gap-1">
          <Button
            class="!size-9 shrink-0 !p-0"
            variant="ghost"
            :icon="muted || !volume ? 'volume-x' : 'volume-2'"
            :aria-label="muted ? __('Unmute') : __('Mute')"
            @click="toggleMute"
          />
          <input
            class="h-8 w-20 max-w-[24vw] accent-blue-500"
            type="range"
            min="0"
            max="1"
            step="0.05"
            :value="muted ? 0 : volume"
            :aria-label="__('Volume')"
            @input="setVolume($event.target.value)"
          />
        </div>
      </div>
      <div
        v-if="error"
        class="mt-2 flex flex-wrap items-center gap-2 text-xs text-ink-red-8"
        role="status"
      >
        <CircleAlertIcon class="size-4 shrink-0" />
        <span>{{ error }}</span>
        <Button
          :label="__('Try Again')"
          variant="outline"
          @click="retryPlayback"
        />
        <a
          v-if="downloadAction"
          :href="downloadAction"
          target="_blank"
          rel="noopener noreferrer"
          class="rounded underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
          >{{ __('Download') }}</a
        >
      </div>
    </template>

    <AttachmentCard v-else :attachment="fallbackAttachment" />
  </div>
</template>

<script setup>
import LoadingIndicator from '@/components/Icons/LoadingIndicator.vue'
import {
  clampAudioFraction,
  createAudioSeekDrag,
  formatAudioTime,
  getAudioDuration,
  normalizeAudioVolume,
  prepareWaveform,
} from '@/utils/messengerAudio'
import {
  getAttachmentState,
  getAttachmentAction,
  getMessengerAttachmentTitle,
} from '@/utils/messengerAttachments'
import { Button } from 'frappe-ui'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import AudioLinesIcon from '~icons/lucide/audio-lines'
import CircleAlertIcon from '~icons/lucide/circle-alert'
import AttachmentCard from './AttachmentCard.vue'

const props = defineProps({
  attachment: { type: Object, required: true },
  compactPreview: { type: Boolean, default: false },
})
const audio = ref(null)
const playing = ref(false)
const loading = ref(false)
const error = ref('')
const currentTime = ref(0)
const metadataDuration = ref(0)
const volume = ref(1)
const muted = ref(false)
let previousVolume = 1
let loadingTimer = null

const state = computed(() => getAttachmentState(props.attachment))
const playable = computed(() =>
  Boolean(props.attachment.url && state.value.active),
)
const fallbackAttachment = computed(() =>
  state.value.active
    ? {
        ...props.attachment,
        status: 'failed',
        url: null,
        download_url: null,
        open_url: null,
      }
    : props.attachment,
)
const downloadAction = computed(() =>
  state.value.active
    ? props.attachment.download_url || getAttachmentAction(props.attachment)
    : '',
)
const bars = computed(() => prepareWaveform(props.attachment.waveform, 64))
const duration = computed(() =>
  getAudioDuration(metadataDuration.value, props.attachment.duration_ms),
)
const progress = computed(() =>
  duration.value ? clampAudioFraction(currentTime.value / duration.value) : 0,
)
const title = computed(() => getMessengerAttachmentTitle(props.attachment))

async function togglePlayback() {
  if (!audio.value || error.value) return
  if (!audio.value.paused) {
    audio.value.pause()
    return
  }
  startLoading()
  try {
    await audio.value.play()
  } catch {
    onError()
  }
}

function onMetadata() {
  let value = Number(audio.value?.duration || 0)
  metadataDuration.value = Number.isFinite(value) ? value : 0
  finishLoading()
}

function onTimeUpdate() {
  currentTime.value = Number(audio.value?.currentTime || 0)
}

function onPlaying() {
  playing.value = true
  finishLoading()
  error.value = ''
}

function onEnded() {
  finishLoading()
  playing.value = false
  currentTime.value = duration.value
}

function onPause() {
  playing.value = false
  finishLoading()
}

function onError() {
  audio.value?.pause()
  playing.value = false
  finishLoading()
  error.value = __('Could not play the audio')
}

function startLoading() {
  if (error.value || loadingTimer !== null) return
  loading.value = true
  loadingTimer = setTimeout(onError, 20000)
}

function finishLoading() {
  clearTimeout(loadingTimer)
  loadingTimer = null
  loading.value = false
}

function retryPlayback() {
  if (!audio.value || !playable.value) return
  error.value = ''
  currentTime.value = 0
  startLoading()
  audio.value.load()
}

function seekToFraction(value) {
  if (!audio.value || !duration.value || error.value) return
  let next = clampAudioFraction(value) * duration.value
  audio.value.currentTime = next
  currentTime.value = next
}

const seekDrag = createAudioSeekDrag(seekToFraction)

function seekFromKeyboard(event) {
  if (!duration.value) return
  let next = progress.value
  if (event.key === 'ArrowLeft') next -= 5 / duration.value
  else if (event.key === 'ArrowRight') next += 5 / duration.value
  else if (event.key === 'Home') next = 0
  else if (event.key === 'End') next = 1
  else return
  event.preventDefault()
  seekToFraction(next)
}

function setVolume(value) {
  let next = normalizeAudioVolume(value)
  volume.value = next
  muted.value = next === 0
  if (next > 0) previousVolume = next
  if (audio.value) {
    audio.value.volume = next
    audio.value.muted = muted.value
  }
}

function toggleMute() {
  if (muted.value || volume.value === 0) {
    setVolume(previousVolume || 1)
  } else {
    previousVolume = volume.value
    muted.value = true
    if (audio.value) audio.value.muted = true
  }
}

function onVolumeChange() {
  if (!audio.value) return
  volume.value = normalizeAudioVolume(audio.value.volume)
  muted.value = Boolean(audio.value.muted)
}

function barProgress(index) {
  return (index + 1) / bars.value.length
}

watch(
  () => [props.attachment.id, props.attachment.url, playable.value],
  () => {
    audio.value?.pause()
    finishLoading()
    playing.value = false
    error.value = ''
    currentTime.value = 0
    metadataDuration.value = 0
  },
)

onBeforeUnmount(() => {
  finishLoading()
  seekDrag.cancel()
  audio.value?.pause()
})
</script>

<style scoped>
.audio-seek-range {
  appearance: none;
  background: transparent;
  cursor: pointer;
}

.audio-seek-range::-webkit-slider-runnable-track {
  height: 0.5rem;
  border-radius: 9999px;
  background: linear-gradient(
    to right,
    var(--surface-blue-7) 0 var(--seek-progress),
    var(--surface-gray-5) var(--seek-progress) 100%
  );
}

.audio-seek-range::-moz-range-track {
  height: 0.5rem;
  border-radius: 9999px;
  background: var(--surface-gray-5);
}

.audio-seek-range::-moz-range-progress {
  height: 0.5rem;
  border-radius: 9999px;
  background: var(--surface-blue-7);
}

.audio-seek-range::-webkit-slider-thumb {
  appearance: none;
  width: 1rem;
  height: 1rem;
  margin-top: -0.25rem;
  border-radius: 50%;
  background: var(--surface-blue-7);
}

.audio-seek-range::-moz-range-thumb {
  width: 1rem;
  height: 1rem;
  border: 0;
  border-radius: 50%;
  background: var(--surface-blue-7);
}
</style>
