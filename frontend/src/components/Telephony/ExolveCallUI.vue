<template>
  <section
    v-if="!show && enabled && active"
    data-testid="compact-call"
    :aria-label="__('Current call')"
    class="fixed bottom-4 right-4 z-50 w-[calc(100%-2rem)] max-w-sm rounded-xl border border-outline-gray-2 bg-surface-elevation-1 p-3 shadow-lg"
  >
    <button
      type="button"
      class="flex min-h-11 w-full items-center justify-between gap-3 rounded px-1 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-ink-gray-9"
      :aria-label="__('Expand call')"
      @click="show = true"
    >
      <span class="min-w-0"
        ><span class="block truncate font-medium text-ink-gray-9">{{
          currentCustomer
        }}</span
        ><span class="mt-1 block text-sm text-ink-gray-6" role="status">{{
          callLabel
        }}</span></span
      >
      <span
        v-if="callState === 'connected'"
        class="shrink-0 tabular-nums text-ink-gray-9"
        role="timer"
        aria-live="off"
        >{{ elapsedLabel }}</span
      >
      <FeatherIcon
        name="maximize-2"
        class="size-4 shrink-0 text-ink-gray-6"
        aria-hidden="true"
      />
    </button>
    <p v-if="error" role="alert" class="mt-2 text-sm text-ink-red-4">
      {{ error }}
    </p>
    <Button
      v-if="audioBlocked"
      :label="__('Enable Call Audio')"
      class="mt-2 min-h-11 w-full"
      @click="enableAudio"
    />
    <div class="mt-2 flex gap-2">
      <Button
        v-if="callState === 'incoming'"
        :label="__('Answer')"
        icon-left="lucide-phone"
        variant="solid"
        class="min-h-11 flex-1"
        :loading="preparingAudio"
        @click="answer"
      />
      <Button
        v-if="callState === 'connected'"
        :icon="muted ? 'lucide-mic-off' : 'lucide-mic'"
        :aria-label="microphoneLabel"
        :tooltip="microphoneLabel"
        :aria-pressed="muted"
        class="min-h-11 min-w-11"
        @click="toggleMute"
      />
      <Button
        :label="callState === 'incoming' ? __('Decline') : __('Hang Up')"
        icon-left="lucide-phone-off"
        theme="red"
        variant="solid"
        class="min-h-11 flex-1"
        @click="hangup"
      />
    </div>
  </section>
  <Button
    v-else-if="!show && workStore.hasDraft"
    :label="__('Conversation drafts')"
    icon-left="lucide-phone"
    variant="solid"
    class="fixed bottom-4 right-4 z-50 min-h-11 shadow-lg"
    @click="show = true"
  />
  <Dialog
    v-model="show"
    :options="{
      title: audioSettingsOpen ? __('Call audio') : __('Telephony'),
      size: audioSettingsOpen ? 'lg' : workStore.current ? '7xl' : 'md',
    }"
  >
    <template #body-content>
      <CallAudioSettings
        v-model="audioSettingsOpen"
        v-model:input="audioPreferences.input"
        v-model:output="audioPreferences.output"
        :active="active"
      />

      <div
        v-show="!audioSettingsOpen"
        data-testid="call-screen"
        class="flex min-h-0 flex-col"
        :class="workStore.current ? 'h-[calc(100dvh-9rem)]' : 'max-h-[75dvh]'"
      >
        <header
          data-testid="call-controls"
          class="shrink-0 border-b border-outline-gray-2 pb-4"
        >
          <form
            class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-6"
            @submit.prevent="dial"
          >
            <div class="min-w-0 sm:w-96 sm:max-w-[50%]">
              <CallRecipient
                v-if="!active"
                v-model="number"
                @select="chooseRecipient"
              />
              <p
                v-else
                class="break-words text-2xl font-semibold tabular-nums text-ink-gray-9"
              >
                {{ displayPhone(number) }}
              </p>
              <div
                class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-gray-6"
              >
                <span
                  v-if="active"
                  class="inline-flex items-center gap-2"
                  role="status"
                  aria-live="polite"
                >
                  <span
                    class="size-2 rounded-full bg-ink-green-3"
                    aria-hidden="true"
                  />{{ callLabel }}
                </span>
                <span
                  v-else-if="callState === 'ended' || callState === 'failed'"
                  role="status"
                  >{{ callLabel }}</span
                >
                <span
                  v-else
                  class="inline-flex items-center gap-2"
                  role="status"
                  aria-live="polite"
                >
                  <span
                    class="size-2 rounded-full"
                    :class="
                      connection === 'ready'
                        ? 'bg-ink-green-3'
                        : 'bg-surface-gray-4'
                    "
                    aria-hidden="true"
                  />
                  {{
                    connection === 'ready'
                      ? __('Ready to call')
                      : connectionLabel
                  }}
                </span>
                <span
                  v-if="active && callState === 'connected'"
                  class="font-medium tabular-nums text-ink-gray-9"
                  role="timer"
                  aria-live="off"
                  >{{ elapsedLabel }}</span
                >
                <span v-if="!active && ownNumber">{{
                  __('Calling from {0}', [displayPhone(ownNumber)])
                }}</span>
              </div>
            </div>
            <div class="flex shrink-0 flex-wrap items-center gap-2">
              <template v-if="!active">
                <Button
                  icon="lucide-audio-lines"
                  :aria-label="__('Call audio')"
                  :tooltip="__('Call audio')"
                  class="min-h-11 min-w-11"
                  @click="audioSettingsOpen = true"
                />
                <Button
                  v-if="connection === 'ready'"
                  :label="__('Call customer')"
                  icon-left="lucide-phone"
                  variant="solid"
                  class="min-h-11 min-w-36 flex-1 sm:flex-none"
                  type="submit"
                  :disabled="!dialNumber(number)"
                  :loading="preparingAudio"
                />
                <Button
                  v-else-if="connectionAvailable"
                  :label="__('Connect telephony')"
                  icon-left="lucide-headset"
                  variant="solid"
                  class="min-h-11"
                  :loading="connection === 'connecting'"
                  @click="connect(true)"
                />
                <Button
                  v-else-if="isManager()"
                  :label="__('Telephony settings')"
                  class="min-h-11"
                  @click="openSettings"
                />
              </template>
              <template v-else>
                <Button
                  v-if="callState === 'incoming'"
                  :label="__('Answer')"
                  variant="solid"
                  class="min-h-11 flex-1 sm:flex-none"
                  :loading="preparingAudio"
                  @click="answer"
                />
                <Button
                  v-if="callState === 'connected'"
                  :label="microphoneLabel"
                  :icon-left="muted ? 'lucide-mic-off' : 'lucide-mic'"
                  class="hidden min-h-11 sm:inline-flex"
                  :aria-pressed="muted"
                  @click="toggleMute"
                />
                <Button
                  v-if="callState === 'connected'"
                  :icon="muted ? 'lucide-mic-off' : 'lucide-mic'"
                  :aria-label="microphoneLabel"
                  :tooltip="microphoneLabel"
                  :aria-pressed="muted"
                  class="min-h-11 min-w-11 sm:hidden"
                  @click="toggleMute"
                />
                <Button
                  :label="
                    callState === 'incoming' ? __('Decline') : __('Hang Up')
                  "
                  icon-left="lucide-phone-off"
                  theme="red"
                  variant="solid"
                  class="min-h-11 flex-1 sm:flex-none"
                  @click="hangup"
                />
                <Popover v-if="callState === 'connected'" align="end">
                  <template #trigger>
                    <Button
                      icon="lucide-grid-3x3"
                      :aria-label="__('Dial Pad')"
                      :tooltip="__('Dial Pad')"
                      class="min-h-11 min-w-11"
                    />
                  </template>
                  <div
                    class="grid w-56 grid-cols-3 gap-2 p-2"
                    :aria-label="__('Dial Pad')"
                  >
                    <Button
                      v-for="tone in tones"
                      :key="tone"
                      :aria-label="__('Send tone {0}', [tone])"
                      class="min-h-11"
                      @click="client?.sendDtmf(tone)"
                      >{{ tone }}</Button
                    >
                  </div>
                </Popover>
                <Button
                  icon="lucide-minimize-2"
                  :aria-label="__('Minimize call')"
                  :tooltip="__('Minimize call')"
                  class="min-h-11 min-w-11"
                  @click="show = false"
                />
              </template>
            </div>
          </form>
          <p
            v-if="error"
            role="alert"
            class="mt-3 rounded bg-surface-red-1 p-3 text-sm text-ink-gray-9"
          >
            {{ error }}
          </p>
          <Button
            v-if="audioBlocked"
            :label="__('Enable Call Audio')"
            class="mt-3"
            @click="enableAudio"
          />
        </header>
        <CallWorkPanel
          v-if="workStore.current"
          :work="workStore.current"
          :active="active"
          class="min-h-0 flex-1"
          @navigate="show = false"
          @select-work="selectWork"
        />
      </div>
    </template>
  </Dialog>
  <audio ref="audioElement" autoplay playsinline />
</template>

<script setup>
import { Button, Dialog, FeatherIcon, Popover, call } from 'frappe-ui'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { callSessions } from '@/composables/telephony'
import { activeSettingsPage, showSettings } from '@/composables/settings'
import { usersStore } from '@/stores/users'
import { sessionStore } from '@/stores/session'
import { callWorkStore } from '@/stores/callWork'
import CallWorkPanel from './CallWorkPanel.vue'
import { dialNumber, displayPhone } from '@/utils/telephony'
import CallRecipient from './CallRecipient.vue'
import CallAudioSettings from './CallAudioSettings.vue'
import {
  microphoneConstraints,
  readAudioPreferences,
  saveAudioPreferences,
} from '@/utils/telephonyAudio'
import {
  acquireExolveTabLock,
  createExolveClient,
  normalizeExolveNumber,
} from '@/utils/exolveClient'

const props = defineProps({ enabled: { type: Boolean, default: false } })
const { isManager } = usersStore()
const session = sessionStore()
const workStore = callWorkStore()
const show = ref(false)
const number = ref('')
const ownNumber = ref('')
const connection = ref('offline')
const callState = ref('idle')
const error = ref('')
const muted = ref(false)
const microphoneLabel = computed(() =>
  muted.value ? __('Turn on microphone') : __('Turn off microphone'),
)
const audioBlocked = ref(false)
const audioElement = ref(null)
const audioSettingsOpen = ref(false)
const preparingAudio = ref(false)
let preferenceStorage
try {
  preferenceStorage = window.localStorage
} catch {
  /* Browser policy */
}
const audioPreferences = reactive(
  readAudioPreferences(preferenceStorage, session.user),
)
watch(audioPreferences, (value) =>
  saveAudioPreferences(preferenceStorage, session.user, value),
)
watch(show, (value) => {
  if (!value) audioSettingsOpen.value = false
})
const currentCustomer = computed(
  () => workStore.current?.context?.title || displayPhone(number.value),
)
const elapsed = ref(0)
const syncing = ref(false)
const connectionAvailable = ref(false)
const tones = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '0', '#']
let client = null
let connectedAt = null
let clock = null
let syncTimer = null
let syncAttempts = 0
let generation = 0
let releaseTabLock = null
let mounted = false
let statusGeneration = 0
let blockedByTab = false
const preferenceKey = `crm-exolve:auto-connect:${session.user}`

function autoConnectEnabled() {
  try {
    return localStorage.getItem(preferenceKey) !== 'off'
  } catch {
    return true
  }
}
function rememberAutoConnect(enabled) {
  try {
    if (enabled) localStorage.removeItem(preferenceKey)
    else localStorage.setItem(preferenceKey, 'off')
  } catch {
    // A storage restriction must not prevent the current connection.
  }
}

async function checkConnection() {
  if (!mounted || !props.enabled || active.value) return
  const version = ++statusGeneration
  try {
    const status = await call(
      'crm.integrations.exolve.api.get_connection_status',
    )
    if (!mounted || version !== statusGeneration || !props.enabled) return
    connectionAvailable.value = status.available
    if (!status.available) {
      disconnect()
      error.value = __(
        {
          unmapped:
            'Your CRM user has no Exolve SIP account. Contact your administrator.',
          missing_key: 'Enter the Exolve application ID and API key.',
          not_permitted: 'You do not have permission to use telephony.',
          disabled: 'Exolve calling is disabled.',
        }[status.reason] ||
          'Could not check telephony configuration. Try again.',
      )
      return
    }
    if (autoConnectEnabled() && !client) await connect(false)
  } catch {
    if (mounted && version === statusGeneration)
      error.value = __('Could not check telephony configuration. Try again.')
  }
}

const active = computed(() =>
  ['incoming', 'dialing', 'ringing', 'connected'].includes(callState.value),
)
watch(
  [active, connection, ownNumber, callState, error],
  () => {
    Object.assign(callSessions.exolve, {
      active: active.value,
      connection: connection.value,
      line: ownNumber.value,
      state: callState.value,
      error: error.value,
    })
  },
  { immediate: true, flush: 'sync' },
)
const elapsedLabel = computed(
  () =>
    `${Math.floor(elapsed.value / 60)
      .toString()
      .padStart(2, '0')}:${(elapsed.value % 60).toString().padStart(2, '0')}`,
)
const connectionLabel = computed(
  () =>
    ({
      ready: __('Connected'),
      connecting: __('Connecting…'),
      offline: __('Disconnected'),
    })[connection.value],
)
const callLabel = computed(
  () =>
    ({
      incoming: __('Incoming Call'),
      dialing: __('Calling…'),
      ringing: __('Ringing'),
      connected: __('Call in Progress'),
      ended: __('Call Ended'),
      failed: __(
        'The call did not connect. Check the number and Exolve account.',
      ),
    })[callState.value] || '',
)

async function connect(manual = true) {
  if (
    active.value ||
    connection.value === 'ready' ||
    connection.value === 'connecting'
  )
    return
  if (manual) rememberAutoConnect(true)
  disconnect()
  blockedByTab = false
  error.value = ''
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    error.value = __(
      'Calling requires HTTPS or localhost and microphone access.',
    )
    return
  }
  connection.value = 'connecting'
  const version = generation
  let credentials
  try {
    credentials = await call('crm.integrations.exolve.api.get_sip_credentials')
    if (version !== generation || !props.enabled) return
    const release = await acquireExolveTabLock(credentials.username)
    if (version !== generation) {
      release?.()
      return
    }
    if (!release) {
      blockedByTab = true
      connection.value = 'offline'
      error.value = __(
        'Telephony is connected in another tab. Continue there or close that tab.',
      )
      return
    }
    releaseTabLock = release
    ownNumber.value = credentials.number
    client = createExolveClient({
      sip: credentials,
      audio: audioElement.value,
      getAudioConstraints: () => microphoneConstraints(audioPreferences.input),
      onState: (state) => {
        if (version !== generation) return
        connection.value = state
      },
      onError: (message) => {
        if (version !== generation) return
        disconnect()
        error.value = __(message)
      },
      onAudioBlocked: () => {
        audioBlocked.value = true
      },
      onCall: (event) => {
        if (version !== generation) return
        workStore.observe(event)
        callState.value = event.state
        number.value = event.number
        muted.value = false
        if (event.state === 'connected') connectedAt = Date.now()
        if (['incoming', 'dialing'].includes(event.state)) {
          audioSettingsOpen.value = false
          connectedAt = null
          elapsed.value = 0
          show.value = true
        }
        if (['ended', 'failed'].includes(event.state)) {
          connectedAt = null
          syncAttempts = 0
          scheduleSync()
        }
      },
    })
    await client.connect()
  } catch {
    if (version !== generation) return
    disconnect()
    error.value = __(
      'Could not connect Exolve. Check your SIP mapping and saved API key.',
    )
  } finally {
    if (credentials) credentials.password = ''
  }
}

function openSettings() {
  show.value = false
  activeSettingsPage.value = __('Telephony')
  showSettings.value = true
}

function settingsUpdated() {
  statusGeneration++
  disconnect()
  error.value = ''
  checkConnection()
}
function recoverConnection() {
  if (autoConnectEnabled() && !active.value && (blockedByTab || !client))
    checkConnection()
}

function disconnect() {
  if (active.value) workStore.observe({ state: 'failed' })
  generation++
  clearTimeout(syncTimer)
  client?.destroy()
  client = null
  releaseTabLock?.()
  releaseTabLock = null
  connection.value = 'offline'
  callState.value = 'idle'
  connectedAt = null
  muted.value = false
  audioBlocked.value = false
}

async function prepareOutput() {
  try {
    if (audioElement.value?.setSinkId)
      await audioElement.value.setSinkId(audioPreferences.output)
  } catch {
    throw new Error(
      'Could not use the selected speaker. Check permissions or choose another device.',
    )
  }
}
async function dial() {
  if (active.value || preparingAudio.value || connection.value !== 'ready')
    return
  error.value = ''
  const version = generation
  const recipient = number.value
  const devices = { ...audioPreferences }
  preparingAudio.value = true
  try {
    const normalized = normalizeExolveNumber(recipient)
    audioSettingsOpen.value = false
    await prepareOutput()
    if (
      !mounted ||
      version !== generation ||
      active.value ||
      number.value !== recipient ||
      audioPreferences.input !== devices.input ||
      audioPreferences.output !== devices.output
    )
      return
    if (
      !workStore.current ||
      workStore.current.started ||
      workStore.current.ended
    )
      workStore.prepare(recipient, workStore.current?.context)
    client?.call(normalized)
  } catch (cause) {
    error.value =
      cause.name === 'NotFoundError' || cause.name === 'NotAllowedError'
        ? __(
            'Could not use the selected speaker. Check permissions or choose another device.',
          )
        : __(cause.message)
  } finally {
    preparingAudio.value = false
  }
}
async function answer() {
  if (callState.value !== 'incoming' || preparingAudio.value) return
  error.value = ''
  const version = generation
  const workId = workStore.current?.id
  preparingAudio.value = true
  audioSettingsOpen.value = false
  try {
    await prepareOutput()
    if (
      mounted &&
      version === generation &&
      callState.value === 'incoming' &&
      workStore.current?.id === workId
    )
      client?.answer()
  } catch {
    error.value = __(
      'Could not use the selected speaker. Check permissions or choose another device.',
    )
  } finally {
    preparingAudio.value = false
  }
}
function chooseRecipient(item) {
  if (active.value) return
  number.value = item.number
  workStore.prepare(item.number, { doctype: item.doctype, name: item.name })
}
function hangup() {
  client?.hangup()
}
function toggleMute() {
  muted.value = !muted.value
  client?.mute(muted.value)
}
async function enableAudio() {
  try {
    await audioElement.value.play()
    audioBlocked.value = false
  } catch {
    error.value = __('Could not play call audio. Check the output device.')
  }
}

function scheduleSync() {
  clearTimeout(syncTimer)
  syncTimer = setTimeout(async () => {
    await syncHistory()
    if (++syncAttempts < 3) scheduleSync()
  }, 5000)
}

async function syncHistory() {
  if (syncing.value) return
  syncing.value = true
  try {
    const result = await call('crm.integrations.exolve.api.sync_calls')
    if (result.logs.length) {
      window.dispatchEvent(new CustomEvent('crm-exolve-calls-updated'))
    }
  } catch {
    // Post-call reconciliation retries independently of the call workspace.
  } finally {
    syncing.value = false
  }
}

function makeOutgoingCall(value, context = null) {
  if (active.value) {
    show.value = true
    return
  }
  if (!value && !context && workStore.current) {
    number.value = workStore.current.number
    show.value = true
    return
  }
  number.value = value || ''
  workStore.prepare(value, context)
  show.value = true
}

function openSavedConversation(event) {
  if (active.value) {
    show.value = true
    return
  }
  workStore
    .openLinked(event.detail.callLog)
    .then((work) => {
      if (work) {
        number.value = work.number
        show.value = true
      }
    })
    .catch(() => {
      error.value = __('Could not restore conversation drafts. Try again.')
      show.value = true
    })
}
function selectWork(work) {
  if (!active.value && work) number.value = work.number
}
watch(number, (value) => {
  if (!active.value) workStore.numberChanged(value)
})

function beforeUnload(event) {
  if (active.value || workStore.hasUnsyncedDraft) {
    event.preventDefault()
    event.returnValue = ''
  }
}
onMounted(() => {
  mounted = true
  window.addEventListener('beforeunload', beforeUnload)
  window.addEventListener('crm-open-call-conversation', openSavedConversation)
  window.addEventListener('crm-exolve-settings-updated', settingsUpdated)
  window.addEventListener('online', recoverConnection)
  window.addEventListener('focus', recoverConnection)
  checkConnection()
  workStore.restore().then(() => {
    if (!active.value && workStore.current)
      number.value = workStore.current.number
  })
  clock = setInterval(() => {
    if (connectedAt)
      elapsed.value = Math.floor((Date.now() - connectedAt) / 1000)
  }, 1000)
})
onBeforeUnmount(() => {
  mounted = false
  statusGeneration++
  clearInterval(clock)
  disconnect()
  window.removeEventListener('beforeunload', beforeUnload)
  window.removeEventListener(
    'crm-open-call-conversation',
    openSavedConversation,
  )
  window.removeEventListener('crm-exolve-settings-updated', settingsUpdated)
  window.removeEventListener('online', recoverConnection)
  window.removeEventListener('focus', recoverConnection)
})
watch(
  () => props.enabled,
  (value) => {
    if (!value) {
      statusGeneration++
      disconnect()
      show.value = false
      connectionAvailable.value = false
    } else {
      checkConnection()
    }
  },
)
defineExpose({ makeOutgoingCall, setup: () => {}, disconnect })
</script>

<style scoped>
:global(.dialog-content:has([data-testid='call-screen'])) {
  margin-block: 0;
}
</style>
