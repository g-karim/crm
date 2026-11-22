<template>
  <div class="flex h-full min-h-0 min-w-0 flex-col gap-6 p-4 sm:p-6">
    <!-- Header -->
    <div class="flex shrink-0 flex-wrap justify-between gap-3 text-ink-gray-8">
      <div class="flex min-w-0 flex-1 flex-col gap-1">
        <h2
          class="flex flex-wrap gap-2 text-2xl-semibold leading-6 text-ink-gray-8"
        >
          {{ __('Telephony Settings') }}
          <Badge
            v-if="isDirty"
            :label="__('Not Saved')"
            variant="subtle"
            theme="orange"
          />
        </h2>
        <p class="text-p-base text-ink-gray-6">
          {{ __('Configure telephony settings for your CRM') }}
        </p>
      </div>
      <div class="flex shrink-0 items-center gap-2">
        <Button
          v-if="isDirty"
          :loading="
            isNewDoc
              ? insertResource.loading
              : telephonyAgent.save?.loading || createdAgentSave.loading
          "
          :label="__('Update')"
          variant="solid"
          @click="update"
        />
      </div>
    </div>

    <div v-if="telephonyAgent.doc" class="flex-1 flex flex-col overflow-y-auto">
      <div
        class="flex flex-col items-stretch justify-between gap-3 py-3 sm:flex-row sm:items-center sm:gap-8"
      >
        <div class="flex flex-col">
          <div class="text-p-base-medium text-ink-gray-7 truncate">
            {{ __('Default Medium') }}
          </div>
          <div class="text-p-sm text-ink-gray-5">
            {{ __('Default calling medium for logged-in user') }}
          </div>
        </div>
        <div class="flex items-center gap-1">
          <FormControl
            v-model="telephonyAgent.doc.default_medium"
            type="select"
            class="w-full sm:w-44"
            :options="[
              { label: __(''), value: '' },
              { label: __('Twilio'), value: 'Twilio' },
              { label: __('Exotel'), value: 'Exotel' },
              { label: __('Exolve'), value: 'Exolve' },
            ]"
            :placeholder="__('Select Medium')"
          />
          <Button
            v-if="telephonyAgent.doc.default_medium"
            icon="lucide-x"
            :tooltip="__('Clear')"
            @click="telephonyAgent.doc.default_medium = ''"
          />
        </div>
      </div>
      <div
        v-if="isEnabled('twilio')"
        class="h-px border-t mx-2 border-outline-elevation-2"
      />
      <div
        v-if="isEnabled('twilio')"
        class="flex flex-col items-stretch justify-between gap-3 py-3 sm:flex-row sm:items-center sm:gap-8"
      >
        <div class="flex flex-col">
          <div class="text-p-base-medium text-ink-gray-7 truncate">
            {{ __('Twilio Number') }}
          </div>
          <div class="text-p-sm text-ink-gray-5">
            {{ __('Set the Twilio number to be used for outgoing calls.') }}
          </div>
        </div>
        <div>
          <FormControl
            v-model="telephonyAgent.doc.twilio_number"
            class="w-full min-w-0 sm:w-44"
            :placeholder="__('Enter Twilio Number')"
            :error="
              Boolean(telephonyAgent.doc.twilio_number) &&
              !validatePhone(telephonyAgent.doc.twilio_number)
                ? __('Enter a valid phone number')
                : undefined
            "
            placement="bottom-end"
          />
        </div>
      </div>
      <div
        v-if="isEnabled('exotel')"
        class="h-px border-t mx-2 border-outline-elevation-2"
      />
      <div
        v-if="isEnabled('exotel')"
        class="flex flex-col items-stretch justify-between gap-3 py-3 sm:flex-row sm:items-center sm:gap-8"
      >
        <div class="flex flex-col">
          <div class="text-p-base-medium text-ink-gray-7 truncate">
            {{ __('Exotel Number') }}
          </div>
          <div class="text-p-sm text-ink-gray-5">
            {{ __('Set the Exotel number to be used for outgoing calls.') }}
          </div>
        </div>
        <div>
          <FormControl
            v-model="telephonyAgent.doc.exotel_number"
            class="w-full min-w-0 sm:w-44"
            :placeholder="__('Enter Exotel Number')"
            :error="
              Boolean(telephonyAgent.doc.exotel_number) &&
              !validatePhone(telephonyAgent.doc.exotel_number)
                ? __('Enter a valid phone number')
                : undefined
            "
            placement="bottom-end"
          />
        </div>
      </div>
      <div
        v-if="isEnabled('exotel')"
        class="flex flex-col items-stretch justify-between gap-3 py-3 sm:flex-row sm:items-center sm:gap-8"
      >
        <div class="flex flex-col">
          <div class="text-p-base-medium text-ink-gray-7 truncate">
            {{ __('Personal Mobile Number') }}
          </div>
          <div class="text-p-sm text-ink-gray-5">
            {{
              __(
                'Enter your personal mobile number used by Exotel to make calls',
              )
            }}
          </div>
        </div>
        <div>
          <FormControl
            v-model="telephonyAgent.doc.mobile_no"
            class="w-full min-w-0 sm:w-44"
            :placeholder="__('Enter Personal Mobile Number')"
            :error="
              Boolean(telephonyAgent.doc.mobile_no) &&
              !validatePhone(telephonyAgent.doc.mobile_no)
                ? __('Enter a valid phone number')
                : undefined
            "
            placement="bottom-end"
          />
        </div>
      </div>

      <div
        v-if="isManager()"
        class="flex items-center justify-between text-lg-semibold text-ink-gray-8 mt-4 py-3 px-2"
      >
        {{ __('Integrations') }}
      </div>

      <div
        v-if="isManager()"
        class="flex items-center justify-between py-3 px-2"
      >
        <div class="flex flex-col gap-1">
          <span class="text-base-medium text-ink-gray-8">
            {{ __('Twilio') }}
          </span>
          <span class="text-p-sm text-ink-gray-6">
            {{
              __('Configure your Twilio telephony integration settings here')
            }}
          </span>
        </div>
        <Button
          :label="
            isEnabled('twilio') ? __('Update Configuration') : __('Configure')
          "
          @click="emit('updateStep', 'twilio-settings')"
        />
      </div>

      <div
        v-if="isManager()"
        class="h-px border-t mx-2 border-outline-elevation-2"
      />

      <div
        v-if="isManager()"
        class="flex items-center justify-between py-3 px-2"
      >
        <div class="flex flex-col gap-1">
          <span class="text-base-medium text-ink-gray-8">
            {{ __('Exotel') }}
          </span>
          <span class="text-p-sm text-ink-gray-6">
            {{
              __('Configure your Exotel telephony integration settings here')
            }}
          </span>
        </div>
        <Button
          :label="
            isEnabled('exotel') ? __('Update Configuration') : __('Configure')
          "
          @click="emit('updateStep', 'exotel-settings')"
        />
      </div>
      <div
        v-if="isManager()"
        class="flex items-center justify-between gap-4 border-t border-outline-gray-2 px-2 py-3"
      >
        <div class="flex flex-col gap-1">
          <span class="text-base-medium text-ink-gray-8">{{
            __('Exolve')
          }}</span>
          <span class="text-sm text-ink-gray-6">{{
            __('Make and receive calls in CRM using Exolve SIP accounts.')
          }}</span>
        </div>
        <Button
          :label="
            isEnabled('exolve') ? __('Update Configuration') : __('Configure')
          "
          @click="emit('updateStep', 'exolve-settings')"
        />
      </div>
    </div>
    <ErrorMessage
      :message="
        isNewDoc
          ? insertResource.error
          : telephonyAgent.save?.error || createdAgentSave.error
      "
    />
  </div>
</template>
<script setup>
import {
  FormControl,
  Badge,
  ErrorMessage,
  createResource,
  toast,
} from 'frappe-ui'
import { useTelephony } from '@/composables/telephony'
import { useDocument } from '@/data/document'
import { usersStore } from '@/stores/users'
import { validatePhone } from '@/utils'
import { ref, computed } from 'vue'

const { isEnabled } = useTelephony()

const emit = defineEmits(['updateStep'])

const { getUser, isManager } = usersStore()

// The session already tells us whether this user's agent exists.
// New users must not fetch a missing document and its permissions.
const isNewDoc = ref(!getUser().is_telephony_agent)

const { document: telephonyAgent } = useDocument(
  'CRM Telephony Agent',
  isNewDoc.value ? undefined : getUser().name,
  {
    onError: (err) => {
      if (err.exc_type === 'DoesNotExistError') {
        isNewDoc.value = true
        telephonyAgent.doc = {}
        telephonyAgent.originalDoc = {}
      }
    },
  },
)

if (isNewDoc.value) {
  telephonyAgent.originalDoc = JSON.parse(JSON.stringify(telephonyAgent.doc))
}

function acceptAgent(data) {
  isNewDoc.value = false
  getUser().is_telephony_agent = true
  telephonyAgent.doc = data
  telephonyAgent.originalDoc = JSON.parse(JSON.stringify(data))
}

const createdAgentSave = createResource({
  url: 'frappe.client.save',
  onSuccess: acceptAgent,
})

const insertResource = createResource({
  url: 'frappe.client.insert',
  onSuccess: (data) => {
    acceptAgent(data)
    toast.success(__('Document created successfully'))
  },
  onError: (err) => {
    err.messages?.forEach((msg) => toast.error(__(msg)))
  },
})

async function update() {
  if (!isDirty.value) return
  try {
    if (isNewDoc.value) {
      const doc = {
        doctype: 'CRM Telephony Agent',
        user: getUser().name,
        ...telephonyAgent.doc,
      }
      delete doc.__newDocument
      await insertResource.submit({ doc })
    } else if (telephonyAgent.save) {
      await telephonyAgent.save.submit()
    } else {
      await createdAgentSave.submit({ doc: telephonyAgent.doc })
    }
  } catch {
    // Resource errors remain visible in ErrorMessage below the form.
  }
}

const isDirty = computed(() => {
  return (
    telephonyAgent.doc &&
    telephonyAgent.originalDoc &&
    JSON.stringify(telephonyAgent.doc) !==
      JSON.stringify(telephonyAgent.originalDoc)
  )
})
</script>
