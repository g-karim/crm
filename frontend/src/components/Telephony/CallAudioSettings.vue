<template>
  <div
    v-show="open"
    class="max-h-[65dvh] space-y-5 overflow-y-auto"
    data-testid="call-audio-settings"
  >
    <Button
      :label="__('Back to call')"
      icon-left="lucide-arrow-left"
      class="min-h-11"
      @click="open = false"
    />
    <p class="text-sm leading-5 text-ink-gray-6">
      {{ __('Choose your devices and check the sound before calling.') }}
    </p>
    <FormControl
      v-model="input"
      type="select"
      :label="__('Microphone')"
      :aria-label="__('Microphone')"
      :options="inputOptions"
      :disabled="active"
    />
    <FormControl
      v-if="supportsOutput"
      v-model="output"
      type="select"
      :label="__('Speaker')"
      :aria-label="__('Speaker')"
      :options="outputOptions"
      :disabled="active"
    />
    <p v-else class="text-sm leading-5 text-ink-gray-6">
      {{
        __(
          'This browser uses the system speaker. Change the output in your system settings.',
        )
      }}
    </p>
    <p v-if="active" class="text-sm leading-5 text-ink-gray-6">
      {{ __('Finish the call to change or test audio devices.') }}
    </p>
    <template v-else>
      <div class="rounded-lg border border-outline-gray-2 p-4">
        <Button
          :label="
            checking ? __('Stop microphone check') : __('Check microphone')
          "
          :icon-left="checking ? 'lucide-square' : 'lucide-mic'"
          class="min-h-11"
          @click="toggleMicrophone"
        />
        <div
          class="mt-3 h-2 overflow-hidden rounded-full bg-surface-gray-3"
          role="meter"
          :aria-label="__('Microphone level')"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-valuenow="level"
        >
          <div
            class="h-full rounded-full bg-ink-green-3 motion-safe:transition-[width]"
            :style="{ width: level + '%' }"
          />
        </div>
        <p class="mt-2 text-sm leading-5 text-ink-gray-6" role="status">
          {{
            state === 'requesting'
              ? __('Allow microphone access in your browser.')
              : state === 'checking'
                ? __('Speak a few words. The meter should move.')
                : __(
                    'Microphone check stays on this device and stops after 20 seconds.',
                  )
          }}
        </p>
      </div>
      <Button
        :label="playing ? __('Stop test sound') : __('Play test sound')"
        icon-left="lucide-volume-2"
        class="min-h-11"
        @click="toggleSpeaker"
      />
      <p class="text-sm text-ink-gray-6">
        {{ __('You should hear two short tones in the selected speaker.') }}
      </p>
    </template>
    <Button
      :label="__('Refresh devices')"
      icon-left="lucide-refresh-cw"
      class="min-h-11"
      @click="loadDevices"
    />
    <p
      v-if="error"
      role="alert"
      class="rounded bg-surface-red-1 p-3 text-sm text-ink-gray-9"
    >
      {{ error }}
    </p>
  </div>
</template>
<script setup>
import { Button, FormControl } from 'frappe-ui'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { createMicrophoneCheck, speakerTestWave } from '@/utils/telephonyAudio'
const open = defineModel({ type: Boolean, default: false })
const input = defineModel('input', { type: String, default: '' })
const output = defineModel('output', { type: String, default: '' })
const props = defineProps({ active: Boolean })
const supportsOutput =
  typeof HTMLMediaElement.prototype.setSinkId === 'function'
const devices = ref([]),
  state = ref('idle'),
  level = ref(0),
  error = ref(''),
  playing = ref(false)
const checking = computed(() => state.value !== 'idle')
let alive = true,
  deviceRequest = 0,
  playback = null,
  playbackURL = null,
  soundVersion = 0
const microphone = createMicrophoneCheck({
  onLevel: (value) => {
    level.value = value
  },
  onState: (value) => {
    state.value = value
  },
})
function deviceOptions(kind, selected) {
  const rows = devices.value
    .filter((item) => item.kind === kind && item.deviceId)
    .map((item, index) => ({
      value: item.deviceId,
      label: item.label || __('Audio device {0}', [index + 1]),
    }))
  if (selected && !rows.some((item) => item.value === selected))
    rows.push({ value: selected, label: __('Selected device is unavailable') })
  return [{ value: '', label: __('System default') }, ...rows]
}
const inputOptions = computed(() => deviceOptions('audioinput', input.value))
const outputOptions = computed(() => deviceOptions('audiooutput', output.value))
async function loadDevices() {
  const version = ++deviceRequest
  try {
    const rows = await navigator.mediaDevices.enumerateDevices()
    if (alive && open.value && version === deviceRequest) devices.value = rows
  } catch {
    if (alive && open.value && version === deviceRequest)
      error.value = __(
        'Could not list audio devices. Check browser permissions.',
      )
  }
}
async function toggleMicrophone() {
  if (props.active) return
  if (checking.value) {
    microphone.stop()
    return
  }
  stopSpeaker()
  error.value = ''
  try {
    await microphone.start(input.value)
    if (alive && open.value) await loadDevices()
  } catch {
    if (alive && open.value)
      error.value = __(
        'Could not access the selected microphone. Check permissions or choose another device.',
      )
  }
}
function stopSpeaker() {
  soundVersion++
  playback?.pause()
  if (playback) {
    playback.removeAttribute('src')
    playback.load()
  }
  playback = null
  if (playbackURL) URL.revokeObjectURL(playbackURL)
  playbackURL = null
  playing.value = false
}
async function toggleSpeaker() {
  if (props.active) return
  if (playing.value) {
    stopSpeaker()
    return
  }
  microphone.stop()
  error.value = ''
  stopSpeaker()
  const version = soundVersion
  playbackURL = URL.createObjectURL(speakerTestWave())
  const next = new Audio(playbackURL)
  playback = next
  playing.value = true
  next.onended = () => {
    if (version === soundVersion) stopSpeaker()
  }
  next.onerror = () => {
    if (version === soundVersion) {
      error.value = __('Could not play test sound. Check the selected speaker.')
      stopSpeaker()
    }
  }
  try {
    if (supportsOutput) await next.setSinkId(output.value)
    if (version !== soundVersion) return
    await next.play()
  } catch {
    if (alive && open.value && version === soundVersion) {
      error.value = __('Could not play test sound. Check the selected speaker.')
      stopSpeaker()
    }
  }
}
function stopChecks() {
  microphone.stop()
  stopSpeaker()
}
watch([input, output], stopChecks)
watch([open, () => props.active], () => {
  stopChecks()
  deviceRequest++
  error.value = ''
  if (open.value) loadDevices()
})
function devicesChanged() {
  if (open.value) {
    stopChecks()
    loadDevices()
  }
}
navigator.mediaDevices?.addEventListener('devicechange', devicesChanged)
onBeforeUnmount(() => {
  alive = false
  deviceRequest++
  stopChecks()
  navigator.mediaDevices?.removeEventListener('devicechange', devicesChanged)
})
</script>
