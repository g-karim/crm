// Production recorder with a synthetic channel contract and intercepted API.
// This fixture proves browser recording/upload; remote voice appearance needs
// a separate smoke test against each real Wazzup transport.
import { createApp, h, ref } from 'vue'
import ComposerVoiceRecorder from '@/components/LeadMessenger/ComposerVoiceRecorder.vue'
import { getMessengerCapabilities } from '@/utils/messengerChannels'
import '@/index.css'

globalThis.__ = (message) => message

const params = new URLSearchParams(location.search)
const channel = {
  name: `WAZZUP-${params.get('platform') || 'telegram'}`,
  provider: 'wazzup',
  platform: params.get('platform') || 'telegram',
  wazzup_api_mode: 'partner_api_v2',
  capabilities: {
    voice: {
      send: true,
      max_duration_seconds: 300,
      max_size_bytes: 10 * 1024 * 1024,
    },
  },
}
const capabilities = getMessengerCapabilities(channel)
const recorder = ref(null)
const queued = ref(null)

const app = createApp({
  render: () =>
    h('main', { class: 'mx-auto max-w-lg p-4' }, [
      h('div', { 'data-fixture-channel': '' }, channel.platform),
      capabilities.voice.send &&
        h(ComposerVoiceRecorder, {
          ref: recorder,
          conversation: 'SYNTHETIC-CONVERSATION',
          channel: channel.name,
          referenceDoctype: 'CRM Lead',
          referenceName: 'SYNTHETIC-LEAD',
          replyToMessage: 'SYNTHETIC-REPLY',
          disabled: params.has('disabled'),
          maxDurationSeconds: capabilities.voice.max_duration_seconds,
          maxSizeBytes: capabilities.voice.max_size_bytes,
          onSendRequested: () => recorder.value.send(),
          onQueued: (result) => (queued.value = result),
        }),
      queued.value &&
        h('output', { 'data-queued-status': '' }, queued.value.status),
    ]),
})
app.config.globalProperties.__ = globalThis.__
app.mount('#app')
