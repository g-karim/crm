<template>
  <section
    class="rounded-xl border border-outline-gray-2 bg-surface-gray-1 p-4"
    :aria-label="__('Call recording')"
  >
    <div class="mb-3 flex items-center gap-2 text-base-medium text-ink-gray-9">
      <FeatherIcon name="headphones" class="size-4" aria-hidden="true" />{{
        __('Call recording')
      }}
    </div>
    <p
      class="mb-3 text-sm text-ink-gray-6"
      role="status"
      data-testid="recording-state"
    >
      {{
        failed
          ? __('Recording loading error')
          : src
            ? __('Recording is available')
            : state === 'pending' || pending
              ? __('Recording is being prepared')
              : __('Recording is unavailable')
      }}
    </p>
    <template v-if="src">
      <p
        v-if="hasActiveCall"
        role="status"
        class="text-sm leading-5 text-ink-gray-6"
      >
        {{ __('Recording paused during a live call.') }}
      </p>
      <audio
        v-show="!hasActiveCall && !failed"
        ref="audio"
        :key="src"
        :src="src"
        controls
        preload="none"
        class="h-10 w-full"
        :aria-label="__('Call recording')"
        @error="onError"
        @waiting="waiting = true"
        @canplay="waiting = false"
        @loadedmetadata="metadataReady"
        @play="guardPlayback"
      />
      <div
        v-if="!failed && !hasActiveCall"
        class="mt-3 flex flex-wrap items-end justify-between gap-2"
      >
        <div class="flex gap-2">
          <Button
            :label="__('−10 s')"
            icon-left="lucide-rotate-ccw"
            :tooltip="__('Back 10 seconds')"
            class="min-h-11 min-w-11"
            @click="seek(-10)"
          />
          <Button
            :label="__('+10 s')"
            icon-left="lucide-rotate-cw"
            :tooltip="__('Forward 10 seconds')"
            class="min-h-11 min-w-11"
            @click="seek(10)"
          />
        </div>
        <div class="w-28 shrink-0">
          <FormControl
            v-model="speed"
            type="select"
            :label="__('Playback speed')"
            :options="
              ['0.75', '1', '1.25', '1.5', '2'].map((value) => ({
                value,
                label: value + '×',
              }))
            "
          />
        </div>
      </div>
      <p
        v-if="waiting && !failed"
        class="mt-2 text-sm text-ink-gray-6"
        role="status"
      >
        {{ __('Loading recording…') }}
      </p>
      <div v-if="failed" role="alert" class="space-y-3">
        <p class="text-sm leading-5 text-ink-gray-6">
          {{
            __('Could not load the recording. Check access or try again later.')
          }}
        </p>
        <Button :label="__('Retry')" @click="retry" />
      </div>
    </template>
    <p v-else class="text-sm leading-5 text-ink-gray-6">
      {{
        state === 'pending' || pending
          ? __(
              'The recording may arrive after the call ends and history is updated.',
            )
          : __('No recording is available for this call.')
      }}
    </p>
  </section>
</template>
<script setup>
import { Button, FeatherIcon, FormControl } from 'frappe-ui'
import { onBeforeUnmount, ref, watch } from 'vue'
import { hasActiveCall } from '@/composables/telephony'
import { absoluteRecordingSeek } from '@/utils/callInsights'
import { seekRecording } from '@/utils/callFollowups'
const props = defineProps({
  src: { type: String, default: '' },
  pending: { type: Boolean, default: false },
  state: { type: String, default: 'unavailable' },
})
const audio = ref(null)
const failed = ref(false)
const waiting = ref(false)
const speed = ref('1')
let pendingSeek = null
function seekTo(seconds) {
  if (
    !audio.value ||
    hasActiveCall.value ||
    !Number.isFinite(seconds) ||
    seconds < 0
  )
    return
  if (audio.value.readyState < 1) {
    pendingSeek = seconds
    audio.value.preload = 'auto'
    audio.value.load()
    return
  }
  const target = absoluteRecordingSeek(seconds, audio.value.duration)
  if (target !== null) audio.value.currentTime = target
}
function metadataReady() {
  applySpeed()
  if (pendingSeek !== null) {
    const value = pendingSeek
    pendingSeek = null
    seekTo(value)
  }
}
function applySpeed() {
  if (audio.value) audio.value.playbackRate = Number(speed.value)
}
function seek(delta) {
  if (!audio.value || hasActiveCall.value) return
  const value = seekRecording(
    audio.value.currentTime,
    audio.value.duration,
    delta,
  )
  if (value !== null) audio.value.currentTime = value
}
watch(speed, applySpeed)
function onError() {
  failed.value = true
  waiting.value = false
}
function pause() {
  audio.value?.pause()
}
function guardPlayback() {
  if (hasActiveCall.value) pause()
}
function retry() {
  failed.value = false
  audio.value?.load()
}
watch(
  () => props.src,
  () => {
    pendingSeek = null
    failed.value = false
    waiting.value = false
  },
)
watch(
  hasActiveCall,
  (active) => {
    if (active) pause()
  },
  { flush: 'sync' },
)
onBeforeUnmount(pause)
defineExpose({ pause, seekTo })
</script>
<style scoped>
:global([data-theme='dark']) audio {
  color-scheme: dark;
}
</style>
