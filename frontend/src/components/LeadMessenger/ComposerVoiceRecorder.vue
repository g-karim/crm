<template>
  <div>
    <Button
      v-if="showTrigger && state.state === 'idle'"
      variant="ghost"
      icon="mic"
      :aria-label="__('Record a Voice Message')"
      :disabled="disabled"
      @click="startRecording"
    />

    <div
      v-else-if="state.state !== 'idle'"
      class="mb-2 rounded-lg border border-outline-gray-1 bg-surface-gray-1 p-3"
    >
      <div v-if="isCapturing" class="flex min-w-0 flex-wrap items-center gap-2">
        <span
          class="size-2 rounded-full"
          :class="
            state.state === 'paused'
              ? 'bg-surface-amber-7'
              : 'animate-pulse bg-surface-red-7'
          "
        />
        <span class="text-sm tabular-nums text-ink-gray-8">
          {{ formatAudioTime(state.durationMs / 1000) }}
        </span>
        <span
          v-if="state.state === 'paused'"
          class="text-xs font-medium text-ink-amber-6"
        >
          {{ __('Pause') }}
        </span>
        <div
          class="flex h-7 min-w-24 flex-1 items-center gap-px overflow-hidden"
        >
          <span
            v-for="(bar, index) in liveBars"
            :key="index"
            class="min-w-px flex-1 rounded bg-surface-blue-7"
            :style="{ height: `${Math.max(2, bar * 24)}px` }"
          />
        </div>
        <Button
          v-if="state.canPause && state.state === 'recording'"
          variant="ghost"
          icon="pause"
          :aria-label="__('Pause')"
          @click="recorder.pause()"
        />
        <Button
          v-if="state.canPause && state.state === 'paused'"
          variant="ghost"
          icon="play"
          :aria-label="__('Resume')"
          @click="recorder.resume()"
        />
        <Button
          variant="solid"
          icon="square"
          :aria-label="__('Stop Recording')"
          :disabled="state.state === 'stopping'"
          @click="recorder.stop()"
        />
        <Button
          variant="ghost"
          icon="trash-2"
          :aria-label="__('Delete Recording')"
          @click="recorder.reset()"
        />
      </div>

      <div v-else-if="state.blob" class="flex flex-col gap-2">
        <div v-if="state.error" class="text-sm text-ink-red-8">
          {{ __(state.error) }}
        </div>
        <MessengerAudioPlayer :attachment="previewAttachment" />
        <div class="flex justify-end gap-2">
          <Button
            variant="ghost"
            icon="trash-2"
            :label="__('Delete')"
            :disabled="sending"
            @click="recorder.reset()"
          />
          <Button
            variant="solid"
            iconLeft="send"
            :label="__('Send Voice Message')"
            :loading="sending"
            :disabled="sending || !state.durationMs"
            @click="send"
          />
        </div>
      </div>

      <div v-else class="flex items-center justify-between gap-2 text-sm">
        <span :class="state.error ? 'text-ink-red-8' : 'text-ink-gray-6'">
          {{ state.error ? __(state.error) : stateLabel }}
        </span>
        <Button
          variant="ghost"
          icon="x"
          :aria-label="__('Close')"
          @click="recorder.reset()"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import MessengerAudioPlayer from '@/components/LeadMessenger/MessengerAudioPlayer.vue'
import { formatAudioTime, sanitizeWaveform } from '@/utils/messengerAudio'
import { createMessengerVoiceRecorder } from '@/utils/messengerVoiceRecorder'
import { Button, toast } from 'frappe-ui'
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  conversation: { type: String, default: '' },
  channel: { type: String, default: '' },
  referenceDoctype: { type: String, default: '' },
  referenceName: { type: String, default: '' },
  replyToMessage: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  showTrigger: { type: Boolean, default: true },
  maxDurationSeconds: { type: Number, default: 300 },
  maxSizeBytes: { type: Number, default: 10 * 1024 * 1024 },
  scopeKey: { type: String, default: '' },
})
const emit = defineEmits(['active-change', 'queued'])
const state = ref({ state: 'idle', durationMs: 0, waveform: [] })
const sending = ref(false)
let clientRequestId = ''

const recorder = createMessengerVoiceRecorder({
  maxDurationMs: props.maxDurationSeconds * 1000,
  maxSizeBytes: props.maxSizeBytes,
  onChange(next) {
    state.value = next
    emit(
      'active-change',
      Boolean(next.blob) ||
        ['requesting_permission', 'recording', 'paused', 'stopping'].includes(
          next.state,
        ),
    )
  },
})

const isCapturing = computed(() =>
  ['requesting_permission', 'recording', 'paused', 'stopping'].includes(
    state.value.state,
  ),
)
const liveBars = computed(() => {
  let samples = sanitizeWaveform(state.value.waveform).slice(-48)
  return [...Array(Math.max(0, 48 - samples.length)).fill(0), ...samples].map(
    (value) => value / 255,
  )
})
const previewAttachment = computed(() => ({
  type: 'audio',
  attachment_type: 'audio',
  is_voice: true,
  status: 'available',
  url: state.value.url,
  duration_ms: state.value.durationMs,
  waveform: state.value.waveform,
}))
const stateLabel = computed(
  () =>
    ({
      requesting_permission: __('Requesting microphone access…'),
      stopping: __('Preparing recording…'),
      uploading_to_crm: __('Uploading voice message…'),
    })[state.value.state] || __('Preparing recording…'),
)

function startRecording() {
  if (!props.disabled) recorder.start()
}

async function send() {
  if (sending.value || !state.value.blob || !props.conversation) return
  sending.value = true
  recorder.setExternalState('uploading_to_crm')
  clientRequestId ||= makeClientRequestId()
  let form = new FormData()
  form.append('file', state.value.blob, voiceFilename(state.value.mimeType))
  form.append('conversation', props.conversation)
  form.append('channel', props.channel)
  if (props.referenceDoctype)
    form.append('reference_doctype', props.referenceDoctype)
  if (props.referenceName) form.append('reference_name', props.referenceName)
  form.append('client_request_id', clientRequestId)
  form.append('duration_ms', `${state.value.durationMs}`)
  form.append('waveform', JSON.stringify(state.value.waveform || []))
  if (props.replyToMessage)
    form.append('reply_to_message', props.replyToMessage)
  try {
    let headers = {}
    if (globalThis.csrf_token)
      headers['X-Frappe-CSRF-Token'] = globalThis.csrf_token
    let response = await fetch(
      '/api/method/crm_messenger.api.messages.send_voice_message',
      {
        method: 'POST',
        headers,
        credentials: 'same-origin',
        body: form,
      },
    )
    let body = await response.json()
    let result = body.message || body
    if (!response.ok || !result?.ok)
      throw new Error(result?.error || __('Could not send the voice message.'))
    emit('queued', result)
    clientRequestId = ''
    recorder.reset()
  } catch (error) {
    recorder.setExternalState(
      'error',
      error?.message || __('Could not send the voice message.'),
    )
    toast.error(state.value.error)
  } finally {
    sending.value = false
  }
}

function makeClientRequestId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function voiceFilename(mime = '') {
  if (mime.includes('ogg')) return 'voice.ogg'
  if (mime.includes('webm')) return 'voice.webm'
  return 'voice.m4a'
}

watch(
  () => props.scopeKey,
  () => {
    clientRequestId = ''
    recorder.reset()
  },
)
onBeforeUnmount(() => recorder.dispose())
defineExpose({ start: startRecording, reset: recorder.reset })
</script>
