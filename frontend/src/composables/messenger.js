import { createResource } from 'frappe-ui'
import { ref } from 'vue'

export const isMessengerInstalled = ref(false)

createResource({
  url: 'crm.api.messenger.is_messenger_installed',
  cache: 'Is CRM Messenger Installed',
  auto: true,
  onSuccess(data) {
    isMessengerInstalled.value = Boolean(data)
  },
})
