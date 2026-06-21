import './index.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createDialog } from './utils/dialogs'
import { setupCalendarLocalization } from './utils/calendarLocalization'
import { initSocket } from './socket'
import router from './router'
import translationPlugin from './translation'
import App from './App.vue'

import {
  FrappeUI,
  Button,
  Input,
  TextInput,
  FormControl,
  ErrorMessage,
  Dialog,
  Alert,
  Badge,
  setConfig,
  frappeRequest,
  FeatherIcon,
  toast,
} from 'frappe-ui'

import { telemetryPlugin } from 'frappe-ui/frappe'

let globalComponents = {
  Button,
  TextInput,
  Input,
  FormControl,
  ErrorMessage,
  Dialog,
  Alert,
  Badge,
  FeatherIcon,
}

// create a pinia instance
let pinia = createPinia()

let app = createApp(App)
let calendarLocalizationObserver = null

setConfig('resourceFetcher', frappeRequest)
setConfig('serverMessagesHandler', (messages = []) => {
  messages.forEach((message) => {
    let text = message
    try {
      let parsed = JSON.parse(message)
      text = parsed?.message || parsed
    } catch {
      // message is already plain text
    }

    if (text) {
      toast.info(text)
    }
  })
})
app.use(FrappeUI)
app.use(pinia)
app.use(router)
app.use(translationPlugin)
for (let key in globalComponents) {
  app.component(key, globalComponents[key])
}
app.use(telemetryPlugin, { app_name: 'crm' })

app.config.globalProperties.$dialog = createDialog

function mountApp() {
  app.mount('#app')
  calendarLocalizationObserver = setupCalendarLocalization()
}

let socket
if (import.meta.env.DEV) {
  frappeRequest({ url: '/api/method/crm.www.crm.get_context_for_dev' }).then(
    (values) => {
      for (let key in values) {
        window[key] = values[key]
      }
      socket = initSocket()
      app.config.globalProperties.$socket = socket
      mountApp()
    },
  )
} else {
  socket = initSocket()
  app.config.globalProperties.$socket = socket
  mountApp()
}

if (import.meta.env.DEV) {
  window.$dialog = createDialog
}
