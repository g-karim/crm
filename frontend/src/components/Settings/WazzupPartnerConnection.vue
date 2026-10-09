<template>
  <div class="flex flex-col gap-4" data-wazzup-partner-connection>
    <div class="flex items-center justify-between gap-3 text-p-sm">
      <span class="text-ink-gray-6">{{ __('Connection status') }}</span>
      <span class="text-ink-gray-8" role="status">
        {{ __(presentation.label) }}
      </span>
    </div>
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
      <Button
        :label="__('Connect')"
        variant="solid"
        :loading="action === 'start_connection'"
        :disabled="busy || !available"
        @click="startConnection"
      />
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
            :disabled="busy"
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
        v-if="onboarding.status === 'active'"
        class="text-p-sm text-ink-green-7"
      >
        {{ __('The messenger account is connected.') }}
      </p>
      <p
        v-if="['unauthorized', 'error', 'unknown'].includes(onboarding.status)"
        class="text-p-sm text-ink-orange-7"
      >
        {{ __('Refresh the channel status or reconnect to restore access.') }}
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
          :label="__('Refresh Status')"
          variant="subtle"
          :disabled="busy"
          :loading="action === 'get_onboarding_state'"
          @click="refresh"
        />
        <Button
          v-if="onboarding.can_reconnect && !qrExpired"
          :label="__('Reconnect')"
          variant="subtle"
          :disabled="busy"
          :loading="action === 'reconnect'"
          @click="reconnect"
        />
        <Button
          :label="__('Delete Channel')"
          variant="subtle"
          theme="red"
          :disabled="busy"
          @click="confirmDelete = true"
        />
      </div>
      <div
        v-if="confirmDelete"
        class="flex flex-col gap-3 rounded-lg border border-outline-red-2 p-3"
      >
        <p class="text-p-sm text-ink-gray-7">
          {{ __('Delete this channel? Existing messages will remain in CRM.') }}
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
import { Button, FormControl, LoadingIndicator } from 'frappe-ui'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  callWazzupPartner,
  normalizePartnerConnection,
  wazzupPartnerError,
  wazzupPartnerStatus,
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
const simulator = ref(false)
const password = ref('')
const action = ref('')
const error = ref('')
const confirmDelete = ref(false)
const clock = ref(Date.now())
const requestId = globalThis.crypto.randomUUID()
let generation = 0
let disposed = false
let pollTimer = null

const busy = computed(() => Boolean(action.value))
watch(busy, (value) => emit('busy', value), { flush: 'sync' })
const presentation = computed(() =>
  wazzupPartnerStatus(onboarding.value.status),
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
  if (disposed || (!polling && busy.value)) return false
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
      emit('updated', result.channel)
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

function reconnect() {
  password.value = ''
  confirmDelete.value = false
  return operate('reconnect', { channel: currentChannel.value.name })
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
