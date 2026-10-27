import { createResource } from 'frappe-ui'
import { computed, reactive, ref } from 'vue'

const integrations = ref({})
export const defaultCallingMedium = ref('')
export const callEnabled = ref(false)
// In-memory UI state only. Never put SIP credentials in this shared object.
export const callSessions = reactive({
  exolve: {
    active: false,
    connection: 'offline',
    line: '',
    state: 'idle',
    error: '',
  },
  twilio: { active: false },
  exotel: { active: false },
})
export const hasActiveCall = computed(() =>
  Object.values(callSessions).some((session) => session.active),
)

createResource({
  url: 'crm.integrations.api.is_call_integration_enabled',
  cache: 'Is Call Integration Enabled',
  auto: true,
  onSuccess: (data) => {
    integrations.value = data.integrations || {}
    defaultCallingMedium.value = data.default_calling_medium
    callEnabled.value = Object.values(integrations.value).some(Boolean)
  },
})

export function setEnabled(name, value) {
  integrations.value[name] = value
  callEnabled.value = Object.values(integrations.value).some(Boolean)
}

export function useTelephony() {
  const allIntegrations = computed(() =>
    Object.entries(integrations.value).map(([name, enabled]) => ({
      name,
      enabled,
    })),
  )

  function isEnabled(name) {
    return Boolean(integrations.value[name])
  }

  const isAnyEnabled = computed(() =>
    Object.values(integrations.value).some(Boolean),
  )

  const preferredIntegration = computed(() => {
    const enabled = ['twilio', 'exotel', 'exolve'].filter(isEnabled)
    const preferred = String(defaultCallingMedium.value || '').toLowerCase()
    return enabled.includes(preferred) ? preferred : enabled[0] || ''
  })
  return {
    integrations: allIntegrations,
    isEnabled,
    isAnyEnabled,
    preferredIntegration,
  }
}
