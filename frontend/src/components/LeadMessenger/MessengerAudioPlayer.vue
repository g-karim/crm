<template>
  <div
    class="w-[min(22rem,calc(100vw-3rem))] max-w-full rounded-lg border border-outline-gray-1 bg-surface-white p-3"
  >
    <div class="mb-2 flex min-w-0 items-center gap-2 text-sm font-medium text-ink-gray-8">
      <AudioLinesIcon class="size-4 shrink-0" />
      <span class="truncate">{{ title }}</span>
    </div>

    <audio
      v-if="attachment.url && state.active"
      ref="audio"
      class="hidden"
      :src="attachment.url"
      preload="metadata"
      @loadstart="loading = true"
      @loadedmetadata="onMetadata"
      @durationchange="onMetadata"
      @timeupdate="onTimeUpdate"
      @waiting="loading = true"
      @canplay="loading = false"
      @playing="onPlaying"
      @pause="playing = false"
      @ended="onEnded"
      @error="onError"
      @volumechange="onVolumeChange"
    />

    <template v-if="attachment.url && state.active">
      <div
        v-if="bars.length"
        class="flex h-8 touch-none cursor-pointer items-center gap-[2px] rounded px-1 outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
        role="slider"
        tabindex="0"
        :aria-label="__('Позиция воспроизведения')"
        :aria-valuemin="0"
        :aria-valuemax="Math.round(duration)"
        :aria-valuenow="Math.round(currentTime)"
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
          :class="barProgress(index) <= progress ? 'bg-surface-blue-3' : 'bg-surface-gray-4'"
          :style="{ height: `${2 + bar * 22}px` }"
        />
      </div>
      <input
        v-else
        class="h-8 w-full accent-blue-500"
        type="range"
        min="0"
        max="1"
        step="0.001"
        :value="progress"
        :aria-label="__('Позиция воспроизведения')"
        @input="seekToFraction($event.target.value)"
      />

      <div class="mt-2 flex min-w-0 flex-wrap items-center gap-2">
        <Button
          class="!size-9 shrink-0 !p-0"
          variant="ghost"
          :icon="playing ? 'pause' : 'play'"
          :aria-label="playing ? __('Пауза') : __('Воспроизвести')"
          :disabled="Boolean(error)"
          @click="togglePlayback"
        />
        <LoadingIndicator v-if="loading && !error" class="size-4 shrink-0" />
        <span class="shrink-0 text-xs tabular-nums text-ink-gray-5">
          {{ formatAudioTime(currentTime) }} / {{ formatAudioTime(duration) }}
        </span>
        <div class="ml-auto flex min-w-0 items-center gap-1">
          <Button
            class="!size-9 shrink-0 !p-0"
            variant="ghost"
            :icon="muted || !volume ? 'volume-x' : 'volume-2'"
            :aria-label="muted ? __('Включить звук') : __('Выключить звук')"
            @click="toggleMute"
          />
          <input
            class="h-8 w-20 max-w-[24vw] accent-blue-500"
            type="range"
            min="0"
            max="1"
            step="0.05"
            :value="muted ? 0 : volume"
            :aria-label="__('Громкость')"
            @input="setVolume($event.target.value)"
          />
        </div>
      </div>
      <div v-if="error" class="mt-2 flex items-center gap-2 text-xs text-ink-red-4">
        <CircleAlertIcon class="size-4 shrink-0" />
        <span>{{ error }}</span>
      </div>
    </template>

    <div v-else class="flex items-center gap-2 text-sm text-ink-gray-5">
      <LoadingIndicator v-if="state.busy" class="size-4" />
      <CircleAlertIcon v-else class="size-4" />
      <span>{{ __(state.label) }}</span>
    </div>
  </div>
</template>

<script setup>
import LoadingIndicator from '@/components/Icons/LoadingIndicator.vue'
import {
  clampAudioFraction,
  createAudioSeekDrag,
  formatAudioTime,
  normalizeAudioVolume,
  prepareWaveform,
} from '@/utils/messengerAudio'
import { getAttachmentState } from '@/utils/messengerAttachments'
import { Button } from 'frappe-ui'
import { computed, onBeforeUnmount, ref } from 'vue'
import AudioLinesIcon from '~icons/lucide/audio-lines'
import CircleAlertIcon from '~icons/lucide/circle-alert'

const props = defineProps({ attachment: { type: Object, required: true } })
const audio = ref(null)
const playing = ref(false)
const loading = ref(true)
const error = ref('')
const currentTime = ref(0)
const metadataDuration = ref(0)
const volume = ref(1)
const muted = ref(false)
let previousVolume = 1

const state = computed(() => getAttachmentState(props.attachment))
const bars = computed(() => prepareWaveform(props.attachment.waveform, 64))
const duration = computed(
  () => metadataDuration.value || Number(props.attachment.duration_ms || 0) / 1000,
)
const progress = computed(() =>
  duration.value ? clampAudioFraction(currentTime.value / duration.value) : 0,
)
const title = computed(() =>
  props.attachment.is_voice
    ? __('Голосовое сообщение')
    : props.attachment.title || props.attachment.file_name || __('Аудио'),
)

async function togglePlayback() {
  if (!audio.value || error.value) return
  if (!audio.value.paused) {
    audio.value.pause()
    return
  }
  loading.value = true
  try {
    await audio.value.play()
  } catch {
    onError()
  }
}

function onMetadata() {
  let value = Number(audio.value?.duration || 0)
  metadataDuration.value = Number.isFinite(value) ? value : 0
  loading.value = false
}

function onTimeUpdate() {
  currentTime.value = Number(audio.value?.currentTime || 0)
}

function onPlaying() {
  playing.value = true
  loading.value = false
  error.value = ''
}

function onEnded() {
  playing.value = false
  currentTime.value = duration.value
}

function onError() {
  playing.value = false
  loading.value = false
  error.value = __('Не удалось воспроизвести аудио')
}

function seekToFraction(value) {
  if (!audio.value || !duration.value) return
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

onBeforeUnmount(() => {
  seekDrag.cancel()
  audio.value?.pause()
})
</script>
