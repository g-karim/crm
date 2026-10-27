<template>
  <TwilioCallUI ref="twilio" />
  <ExotelCallUI ref="exotel" />
  <ExolveCallUI ref="exolve" :enabled="isEnabled('exolve')" />
  <Dialog
    v-model:open="show"
    :title="__('Make Call')"
    :actions="[
      {
        label: __('Call using {0}', [callMedium]),
        variant: 'solid',
        onClick: makeCallUsing,
      },
    ]"
  >
    <template #default>
      <div class="flex flex-col gap-4">
        <FormControl
          v-model="mobileNumber"
          type="text"
          :label="__('Mobile Number')"
        />
        <FormControl
          v-model="callMedium"
          type="select"
          :label="__('Calling Medium')"
          :options="enabledIntegrations.map((integration) => integration.label)"
        />
        <div class="flex flex-col gap-1">
          <FormControl
            v-model="isDefaultMedium"
            type="checkbox"
            :label="__('Make {0} as default calling medium', [callMedium])"
          />

          <div v-if="isDefaultMedium" class="text-sm text-ink-gray-4">
            {{
              __('You can change the default calling medium from the settings')
            }}
          </div>
        </div>
      </div>
    </template>
  </Dialog>
</template>
<script setup>
import TwilioCallUI from '@/components/Telephony/TwilioCallUI.vue'
import ExotelCallUI from '@/components/Telephony/ExotelCallUI.vue'
import ExolveCallUI from '@/components/Telephony/ExolveCallUI.vue'
import { defaultCallingMedium, useTelephony } from '@/composables/telephony'
import { globalStore } from '@/stores/global'
import { FormControl, call, toast } from 'frappe-ui'
import { computed, nextTick, ref, watch } from 'vue'

const { setMakeCall, setPrepareCall } = globalStore()
const { isEnabled, isAnyEnabled, preferredIntegration } = useTelephony()

const twilio = ref(null)
const exotel = ref(null)
const exolve = ref(null)

const callMedium = ref('Twilio')
const isDefaultMedium = ref(false)

const show = ref(false)
const mobileNumber = ref('')
const callContext = ref(null)

const enabledIntegrations = computed(() =>
  [
    { key: 'twilio', label: 'Twilio', ref: twilio },
    { key: 'exotel', label: 'Exotel', ref: exotel },
    { key: 'exolve', label: 'Exolve', ref: exolve },
  ].filter(({ key }) => isEnabled(key)),
)

function makeCall(number, context = null) {
  callContext.value = context
  const validDefault = enabledIntegrations.value.some(
    ({ label }) => label === defaultCallingMedium.value,
  )
  if (enabledIntegrations.value.length > 1 && !validDefault) {
    mobileNumber.value = number
    show.value = true
    return
  }

  callMedium.value = enabledIntegrations.value[0]?.label ?? 'Twilio'
  if (
    enabledIntegrations.value.some(
      ({ label }) => label === defaultCallingMedium.value,
    )
  ) {
    callMedium.value = defaultCallingMedium.value
  }

  mobileNumber.value = number
  makeCallUsing()
}

function makeCallUsing() {
  if (isDefaultMedium.value && callMedium.value) {
    setDefaultCallingMedium()
  }

  enabledIntegrations.value
    .find(({ label }) => label === callMedium.value)
    ?.ref.value?.makeOutgoingCall(mobileNumber.value, callContext.value)
  show.value = false
}

// Workspace actions always open controls first, including for legacy providers
// whose makeOutgoingCall() places a call immediately.
function prepareCall(number = '', context = null) {
  callContext.value = context
  const preferred = enabledIntegrations.value.find(
    ({ key }) => key === preferredIntegration.value,
  )
  if (!preferred) return
  if (preferred.key === 'exolve') {
    preferred.ref.value?.makeOutgoingCall(number, context)
    return
  }
  mobileNumber.value = number
  callMedium.value = preferred.label
  show.value = true
}

setPrepareCall(prepareCall)

async function setDefaultCallingMedium() {
  await call('crm.integrations.api.set_default_calling_medium', {
    medium: callMedium.value,
  })

  defaultCallingMedium.value = callMedium.value
  toast.success(
    __('Default calling medium set successfully to {0}', [callMedium.value]),
  )
}

watch(
  () => enabledIntegrations.value.map(({ key }) => key).join(','),
  (_keys, previousKeys = '') =>
    nextTick(() => {
      for (const {
        key,
        label,
        ref: integrationRef,
      } of enabledIntegrations.value) {
        if (!previousKeys.split(',').includes(key))
          integrationRef.value?.setup()
        callMedium.value = label
      }

      if (isAnyEnabled.value) {
        callMedium.value = enabledIntegrations.value[0]?.label ?? 'Twilio'
        setMakeCall(makeCall)
      }
    }),
  { immediate: true },
)
</script>
