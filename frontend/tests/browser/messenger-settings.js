// Isolated test entry: real settings and frappe-ui components, no CRM boot/login.
import { createApp, h } from 'vue'
import { ToastProvider } from 'frappe-ui'
import MessengerSettings from '@/components/Settings/MessengerSettings.vue'
import { setupCalendarLocalization } from '@/utils/calendarLocalization'
import '@/index.css'

globalThis.__ = (message, args = []) =>
  args.reduce(
    (text, value, index) => text.replace(`{${index}}`, value),
    window.__fixtureTranslations?.[message] || message,
  )
window.csrf_token = 'browser-fixture-csrf'
window.timezone = {
  system: new URLSearchParams(window.location.search).get('timezone') || 'UTC',
}
const app = createApp({
  render: () => [h(MessengerSettings), h(ToastProvider)],
})
app.config.globalProperties.__ = globalThis.__
app.mount('#app')
setupCalendarLocalization()
