<template>
  <div class="flex flex-col gap-4" data-wazzup-partner-connection>
    <div
      v-if="preparing"
      class="flex items-center gap-2 text-p-sm text-ink-gray-6"
      role="status"
    >
      <LoadingIndicator class="size-4" />
      {{ __('Preparing connection') }}
    </div>
    <div v-if="!currentChannel.name" class="flex flex-col gap-4">
      <p v-if="!available" class="text-p-sm text-ink-orange-7" role="status">
        {{
          __(
            'Connection is not configured. Ask your system administrator to enable it.',
          )
        }}
      </p>
    </div>

    <template v-else>
      <section
        v-if="onboarding.status === 'waiting_qr'"
        class="flex flex-col items-center gap-3 rounded-lg border border-outline-gray-1 p-4"
      >
        <template v-if="qrExpired">
          <p class="text-p-sm text-ink-orange-7">
            {{ __('QR code has expired. Request a new code.') }}
          </p>
          <Button
            :label="__('Refresh QR code')"
            variant="solid"
            :disabled="busy || !onboarding.can_reconnect"
            :loading="action === 'reconnect'"
            @click="reconnect"
          />
        </template>
        <template v-else-if="qrImage">
          <img
            :src="qrImage"
            :alt="__('Channel QR code')"
            class="size-64 max-w-full bg-white object-contain"
            data-wazzup-qr
          />
          <p class="text-center text-p-sm text-ink-gray-6">
            {{
              __(
                simulator
                  ? 'Use the simulator button below to test the QR scan.'
                  : 'Scan this QR code in the messenger app.',
              )
            }}
          </p>
        </template>
        <p v-else class="text-p-sm text-ink-gray-6">
          {{ __('Waiting for QR code.') }}
        </p>
      </section>

      <form
        v-if="onboarding.status === 'waiting_2fa'"
        class="flex flex-col gap-3 rounded-lg border border-outline-gray-1 p-4"
        @submit.prevent="submitTwoFactor"
      >
        <p class="text-p-sm text-ink-gray-6">
          {{
            __('Enter the two-factor authentication password for this account.')
          }}
        </p>
        <FormControl
          v-model="password"
          type="password"
          autocomplete="off"
          :label="__('Two-factor authentication password')"
          :disabled="busy || !onboarding.can_submit_2fa"
          data-wazzup-2fa
        />
        <Button
          :label="__('Submit password')"
          variant="solid"
          :loading="action === 'submit_2fa'"
          :disabled="busy || !password || !onboarding.can_submit_2fa"
          @click="submitTwoFactor"
        />
      </form>

      <p
        v-if="
          !connectionWarning &&
          ['unauthorized', 'disabled', 'error', 'unknown'].includes(
            onboarding.status,
          )
        "
        class="text-p-sm text-ink-orange-7"
      >
        {{
          __(
            'Refresh the channel status or restore the connection to regain access.',
          )
        }}
      </p>

      <p
        v-if="connectionWarning"
        class="text-p-sm text-ink-orange-7"
        role="status"
        data-wazzup-connection-warning
      >
        {{ __(connectionWarning) }}
      </p>

      <div
        v-if="simulator && onboarding.status === 'waiting_qr' && !qrExpired"
        class="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-surface-gray-1 p-3"
      >
        <span class="text-p-sm text-ink-gray-6">{{
          __('Local simulator')
        }}</span>
        <Button
          :label="__('Simulate QR scan')"
          variant="subtle"
          :disabled="busy"
          :loading="action === 'simulator_scan'"
          @click="simulateScan"
        />
      </div>

      <div class="flex flex-wrap gap-2 border-t border-outline-gray-1 pt-4">
        <Button
          :label="__('Test')"
          variant="subtle"
          :disabled="busy"
          :loading="action === 'check_channel'"
          @click="checkConnection"
        />
        <Button
          :label="__('Connect / Restore')"
          variant="solid"
          :disabled="busy"
          :loading="action === 'connect_channel'"
          @click="connectChannel"
        />
        <Button
          :label="__('Refresh Status')"
          variant="subtle"
          :disabled="busy"
          :loading="action === 'get_onboarding_state'"
          @click="refresh"
        />
        <Button
          v-if="currentChannel.enabled"
          :label="__('Disconnect')"
          variant="subtle"
          theme="red"
          :disabled="busy"
          :loading="action === 'disconnect'"
          @click="disconnect"
        />
      </div>
      <details
        class="rounded-lg border border-outline-gray-1 p-4"
        data-wazzup-partner-diagnostics
      >
        <summary class="cursor-pointer text-base-medium text-ink-gray-8">
          {{ __('Connection details') }}
        </summary>
        <p
          v-if="diagnostics?.last_checked_at"
          class="mt-2 text-p-sm text-ink-gray-5"
        >
          {{ __('Last checked') }}:
          {{ diagnosticDate(diagnostics.last_checked_at) }}
        </p>
        <dl class="mt-3 flex flex-col gap-2">
          <div
            v-for="row in diagnosticRows"
            :key="row.key"
            :data-diagnostic="row.key"
            class="flex flex-wrap items-center justify-between gap-2"
          >
            <dt class="text-p-sm text-ink-gray-7">{{ __(row.title) }}</dt>
            <dd
              class="flex flex-wrap items-center gap-2 text-p-sm text-ink-gray-5"
            >
              <span v-if="row.checked_at"
                >{{ __('Last checked') }}:
                {{ diagnosticDate(row.checked_at) }}</span
              >
              <span v-if="row.received_at"
                >{{ diagnosticDate(row.received_at)
                }}<template v-if="row.event_label">
                  · {{ __(row.event_label) }}</template
                ></span
              >
              <Badge
                :label="__(row.label)"
                :theme="row.theme"
                variant="outline"
              />
            </dd>
          </div>
        </dl>
        <p class="mt-3 text-p-sm text-ink-gray-5">
          {{
            __(
              'The channel status is checked in its connected account. A successful check does not confirm webhook or message delivery.',
            )
          }}
        </p>
        <div
          class="mt-4 flex flex-wrap gap-2 border-t border-outline-gray-1 pt-4"
        >
          <Button
            v-if="onboarding.can_reconnect"
            :label="__('Reauthorize account')"
            variant="subtle"
            :disabled="busy"
            @click="showConfirmation('reauthorize')"
          />
          <Button
            :label="__('Delete Channel')"
            variant="subtle"
            theme="red"
            :disabled="busy"
            @click="showConfirmation('delete')"
          />
        </div>
        <div
          v-if="confirmReauthorize"
          class="mt-3 flex flex-col gap-3 rounded-lg border border-outline-gray-1 p-3"
        >
          <p class="text-p-sm text-ink-gray-7">
            {{
              __(
                'Start authorization again? You may need to scan a new QR code.',
              )
            }}
          </p>
          <div class="flex gap-2">
            <Button
              :label="__('Reauthorize account')"
              variant="solid"
              :disabled="busy"
              :loading="action === 'reconnect'"
              data-wazzup-confirm-reauthorize
              @click="reconnect"
            />
            <Button
              :label="__('Cancel')"
              variant="subtle"
              :disabled="busy"
              @click="confirmReauthorize = false"
            />
          </div>
        </div>
        <div
          v-if="confirmDelete"
          class="flex flex-col gap-3 rounded-lg border border-outline-red-2 p-3"
        >
          <p class="text-p-sm text-ink-gray-7">
            {{
              __(
                'Delete this channel from the provider? Existing messages will remain in CRM. Connecting it again will require authorization.',
              )
            }}
          </p>
          <div class="flex gap-2">
            <Button
              :label="__('Delete Channel')"
              variant="solid"
              theme="red"
              :loading="action === 'delete_channel'"
              :disabled="busy"
              data-wazzup-confirm-delete
              @click="deleteChannel"
            />
            <Button
              :label="__('Cancel')"
              variant="subtle"
              :disabled="busy"
              @click="confirmDelete = false"
            />
          </div>
        </div>
      </details>
    </template>

    <p
      v-if="error"
      class="rounded-lg bg-surface-red-2 p-3 text-p-sm text-ink-red-8"
      role="alert"
    >
      {{ __(error) }}
    </p>
  </div>
</template>
<script setup>
import {
  Badge,
  Button,
  FormControl,
  LoadingIndicator,
  dayjsLocal,
  toast,
} from 'frappe-ui'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  callWazzupPartner,
  normalizePartnerConnection,
  wazzupPartnerDiagnosticRows,
  wazzupPartnerConnectionWarning,
  wazzupPartnerError,
} from '@/utils/wazzupPartnerConnection'

const props = defineProps({
  channel: { type: Object, default: null },
  platform: { type: String, default: 'whatsapp' },
  displayName: { type: String, default: '' },
  available: { type: Boolean, default: true },
})
const emit = defineEmits(['updated', 'deleted', 'busy'])
const initial = normalizePartnerConnection({ channel: props.channel || {} })
const currentChannel = ref(initial.channel)
const onboarding = ref(initial.onboarding)
const diagnostics = ref(initial.integration?.wazzup_partner || null)
const simulator = ref(false)
const password = ref('')
const action = ref('')
const error = ref('')
const confirmDelete = ref(false)
const confirmReauthorize = ref(false)
const checkedConnection = ref(false)
const clock = ref(Date.now())
const requestId = globalThis.crypto.randomUUID()
let generation = 0
let disposed = false
let pollTimer = null

const busy = computed(() => Boolean(action.value))
watch(busy, (value) => emit('busy', value), { flush: 'sync' })
const connectionWarning = computed(() =>
  checkedConnection.value || diagnostics.value?.last_checked_at
    ? wazzupPartnerConnectionWarning(diagnostics.value)
    : '',
)
const diagnosticRows = computed(() =>
  wazzupPartnerDiagnosticRows(diagnostics.value),
)
const preparing = computed(
  () =>
    action.value === 'start_connection' ||
    ['provisioning', 'reconnecting'].includes(onboarding.value.status),
)
const qrExpired = computed(
  () =>
    onboarding.value.qr_expired ||
    Boolean(
      onboarding.value.qr_expires_at &&
        Date.parse(onboarding.value.qr_expires_at) <= clock.value,
    ),
)
const qrImage = computed(() =>
  qrExpired.value ? '' : onboarding.value.qr_code,
)

function cancelPoll() {
  if (pollTimer !== null) clearTimeout(pollTimer)
  pollTimer = null
}

function schedulePoll() {
  cancelPoll()
  if (
    !disposed &&
    currentChannel.value.name &&
    onboarding.value.status !== 'deleted'
  ) {
    pollTimer = setTimeout(() => refresh(true), 2500)
  }
}

async function operate(method, args, polling = false) {
  if (disposed || busy.value) return false
  const token = ++generation
  cancelPoll()
  clock.value = Date.now()
  if (!polling) action.value = method
  error.value = ''
  try {
    const result = await callWazzupPartner(method, args)
    if (disposed || token !== generation) return false
    if (!result.ok) {
      error.value = wazzupPartnerError(result.reason, method)
      return false
    }
    if (!result.channel.name) {
      error.value = wazzupPartnerError('', method)
      return false
    }
    currentChannel.value = result.channel
    onboarding.value = result.onboarding
    diagnostics.value = result.integration?.wazzup_partner || null
    simulator.value = result.simulator
    if (result.onboarding.has_error) {
      error.value = wazzupPartnerError(
        result.onboarding.status === 'waiting_2fa'
          ? 'two_factor_rejected'
          : result.onboarding.status === 'unknown'
            ? 'provider_unknown'
            : '',
        method,
      )
    }
    if (result.onboarding.status !== 'waiting_2fa') password.value = ''
    if (result.onboarding.status === 'deleted') {
      emit('deleted', result.channel.name)
    } else {
      emit('updated', result.channel, { method })
    }
    return true
  } catch {
    if (!disposed && token === generation)
      error.value = wazzupPartnerError('', method)
    return false
  } finally {
    if (token === generation) {
      action.value = ''
      schedulePoll()
    }
  }
}

function startConnection() {
  if (!props.available) return false
  return operate('start_connection', {
    platform: props.platform === 'telegram' ? 'telegram' : 'whatsapp',
    custom_display_name: props.displayName.trim(),
    client_request_id: requestId,
  })
}

function refresh(polling = false) {
  if (!currentChannel.value.name) return false
  return operate(
    'get_onboarding_state',
    { channel: currentChannel.value.name },
    polling === true,
  )
}

function showConfirmation(action) {
  confirmReauthorize.value = action === 'reauthorize'
  confirmDelete.value = action === 'delete'
}

function reconnect() {
  password.value = ''
  confirmDelete.value = false
  confirmReauthorize.value = false
  return operate('reconnect', { channel: currentChannel.value.name })
}

function saveSettings() {
  if (!currentChannel.value.name) return false
  return operate('save_channel_settings', {
    channel: currentChannel.value.name,
    custom_display_name: props.displayName.trim(),
  })
}

function connectChannel() {
  password.value = ''
  return operate('connect_channel', { channel: currentChannel.value.name })
}

function disconnect() {
  password.value = ''
  return operate('disconnect', { channel: currentChannel.value.name })
}

function diagnosticDate(value) {
  return value ? dayjsLocal(value).format('DD.MM.YYYY HH:mm') : ''
}

async function checkConnection() {
  const checked = await operate('check_channel', {
    channel: currentChannel.value.name,
  })
  if (disposed || !checked) return false
  checkedConnection.value = true
  if (!connectionWarning.value && !error.value)
    toast.success(__('Connection settings verified.'))
  return true
}

async function submitTwoFactor() {
  if (busy.value || !onboarding.value.can_submit_2fa || !password.value)
    return false
  const value = password.value
  password.value = ''
  try {
    return await operate('submit_2fa', {
      channel: currentChannel.value.name,
      password: value,
    })
  } finally {
    password.value = ''
  }
}

function simulateScan() {
  return operate('simulator_scan', {
    channel: currentChannel.value.name,
    require_2fa: currentChannel.value.platform === 'telegram',
  })
}

function deleteChannel() {
  password.value = ''
  return operate('delete_channel', { channel: currentChannel.value.name })
}

defineExpose({ startConnection, saveSettings })

onMounted(() => {
  if (currentChannel.value.name) refresh()
})
onUnmounted(() => {
  disposed = true
  emit('busy', false)
  generation += 1
  cancelPoll()
  password.value = ''
  onboarding.value = initial.onboarding
})
</script>
