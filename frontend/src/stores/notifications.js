import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'
import { computed, ref } from 'vue'

export const visible = ref(false)

export const notifications = createResource({
  url: 'crm.api.notifications.get_notifications',
  initialData: { notifications: [], unread_count: 0, has_more: false },
  auto: true,
})

export const unreadNotificationsCount = computed(
  () => Number(notifications.data?.unread_count) || 0,
)

export const notificationsStore = defineStore('crm-notifications', () => {
  let realtimeSocket = null
  let realtimeHandler = null

  const mark_as_read = createResource({
    url: 'crm.api.notifications.mark_as_read',
    onSuccess: () => notifications.reload(),
  })
  const mark_all_as_read = createResource({
    url: 'crm.api.notifications.mark_all_as_read',
  })

  function toggle() {
    visible.value = !visible.value
  }

  function markNotificationAsRead(notification) {
    if (!notification) return
    mark_as_read.submit({ notification })
  }

  async function markAllAsRead() {
    let hasMore = true
    while (hasMore) {
      let result = await mark_all_as_read.submit({ limit: 500 })
      hasMore = Boolean(result?.has_more)
    }
    notifications.reload()
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
    mark_all_as_read,
    markNotificationAsRead,
    markAllAsRead,
    initializeRealtime,
    disposeRealtime,
    toggle,
  }
})
