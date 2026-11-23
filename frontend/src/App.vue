<template>
  <FrappeUIProvider>
    <NotPermitted v-if="$route.name === 'Not Permitted'" />
    <router-view v-else-if="$route.name === 'Onboarding'" />
    <Layout v-else-if="session.isLoggedIn" class="isolate">
      <router-view
        :key="
          ['Telephony', 'Messenger', 'Lead', 'Deal'].includes($route.name)
            ? $route.path
            : $route.fullPath
        "
      />
    </Layout>
    <Dialogs />
    <DoctypeModals />
    <EventNotificationPopup />
  </FrappeUIProvider>
</template>

<script setup>
import NotPermitted from '@/pages/NotPermitted.vue'
import EventNotificationPopup from '@/components/EventNotificationPopup.vue'
import DoctypeModals from '@/components/Modals/DoctypeModals.vue'
import { Dialogs } from '@/utils/dialogs'
import { sessionStore } from '@/stores/session'
import {
  loadNotificationsForUser,
  notificationsStore,
} from '@/stores/notifications'
import { globalStore } from '@/stores/global'
import { FrappeUIProvider, setConfig, useTheme } from 'frappe-ui'
import {
  defineAsyncComponent,
  onBeforeUnmount,
  onMounted,
  provide,
  watch,
} from 'vue'

const session = sessionStore()
provide('session', session)
watch(
  () => session.user,
  (user) => {
    // createResource keeps the error state; avoid an unhandled bootstrap promise.
    loadNotificationsForUser(user).catch(() => {})
  },
  { immediate: true },
)

const { $socket } = globalStore()
const { initializeRealtime, disposeRealtime } = notificationsStore()
onMounted(() => initializeRealtime($socket))
onBeforeUnmount(disposeRealtime)

const { setTheme } = useTheme()
if (!localStorage.getItem('theme')) {
  setTheme('light')
}

const Layout = defineAsyncComponent(
  () => import('./components/Layouts/ResponsiveLayout.vue'),
)

setConfig('systemTimezone', window.timezone?.system || null)
setConfig('localTimezone', window.timezone?.user || null)
setConfig('translatedMessages', window.translated_messages || {})
</script>
