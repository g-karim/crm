import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'
import { computed, ref } from 'vue'

export const visible = ref(false)

export const notifications = createResource({
  url: 'crm.api.notifications.get_notifications',
  initialData: [],
  auto: true,
})

export const unreadNotificationsCount = computed(
  () =>
    notifications.data
      ?.filter((notification) => !notification.read)
      .reduce(
        (count, notification) =>
          count +
          (notification.type === 'Messenger'
            ? Math.max(Number(notification.event_count) || 1, 1)
            : 1),
        0,
      ) || 0,
)

export const notificationsStore = defineStore('crm-notifications', () => {
  let realtimeSocket = null
  let realtimeHandler = null

  const mark_as_read = createResource({
    url: 'crm.api.notifications.mark_as_read',
    onSuccess: () => {
      mark_as_read.params = {}
      notifications.reload()
    },
  })

  function toggle() {
    visible.value = !visible.value
  }

  function mark_doc_as_read(doc) {
    mark_as_read.params = { doc: doc }
    mark_as_read.reload()
    toggle()
  }

  function initializeRealtime(socket) {
    if (!socket || realtimeSocket === socket) return
    disposeRealtime()
    realtimeSocket = socket
    realtimeHandler = () => notifications.reload()
    realtimeSocket.on('crm_notification', realtimeHandler)
  }

  function disposeRealtime() {
    if (realtimeSocket && realtimeHandler)
      realtimeSocket.off('crm_notification', realtimeHandler)
    realtimeSocket = null
    realtimeHandler = null
  }

  return {
    unreadNotificationsCount,
    mark_as_read,
    mark_doc_as_read,
    initializeRealtime,
    disposeRealtime,
    toggle,
  }
})
