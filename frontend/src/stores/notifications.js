import { defineStore } from 'pinia'
import { createResource, frappeRequest } from 'frappe-ui'
import { computed, ref } from 'vue'
import { formatCompactNumber } from '@/utils/numberFormat.js'

export const visible = ref(false)
export const notificationError = ref('')

export const notifications = createResource({
  url: 'crm.api.notifications.get_notifications',
  // This resource loads before main.js configures the global fetcher.
  resourceFetcher: frappeRequest,
  initialData: { notifications: [], unread_count: 0, has_more: false },
  // App loads this after frappe-ui's request configuration is installed.
  auto: false,
})

export function loadNotificationsForUser(user) {
  notifications.reset()
  return user ? notifications.reload() : Promise.resolve()
}

export const unreadNotificationsCount = computed(() => {
  const count = Number(notifications.data?.unread_count) || 0
  return count >= 1000 ? formatCompactNumber(count) : count
})

export const notificationsStore = defineStore('crm-notifications', () => {
  let realtimeSocket = null
  let realtimeHandler = null
  let channel = null
  let timer = null
  let markingAll = false

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

  async function markNotificationAsRead(notification) {
    if (!notification) return
    const row =
      typeof notification === 'string'
        ? notifications.data?.notifications.find(
            (item) => item.name === notification,
          )
        : notification
    const params = { notification: row?.name || notification }
    if (row?.head) params.observed_head = row.head
    if (notifications.data?.viewer)
      params.expected_viewer = notifications.data.viewer
    try {
      await mark_as_read.submit(params)
      notificationError.value = ''
      channel?.postMessage('changed')
    } catch {
      notificationError.value = __(
        'Could not update notification read state. Refresh and try again.',
      )
    }
  }

  async function markAllAsRead() {
    if (markingAll) return
    markingAll = true
    let hasMore = true
    let token = notifications.data?.snapshot_token
    let cursor = 0
    const viewer = notifications.data?.viewer
    try {
      while (hasMore) {
        const params = { limit: 500 }
        if (token) Object.assign(params, { snapshot_token: token, cursor })
        if (viewer) params.expected_viewer = viewer
        let result = await mark_all_as_read.submit(params)
        token = result?.snapshot_token
        cursor = result?.cursor
        hasMore = Boolean(result?.has_more)
      }
      notificationError.value = ''
      channel?.postMessage('changed')
      notifications.reload()
    } catch {
      notificationError.value = __(
        'Could not update notification read state. Refresh and try again.',
      )
    } finally {
      markingAll = false
    }
  }

  function initializeRealtime(socket) {
    if (!socket || realtimeSocket === socket) return
    disposeRealtime()
    realtimeSocket = socket
    realtimeHandler = () => notifications.reload()
    realtimeSocket.on('crm_notification', realtimeHandler)
    realtimeSocket.on('exp_notifications_changed', realtimeHandler)
    const user = new URLSearchParams(document.cookie.split('; ').join('&')).get(
      'user_id',
    )
    if (user && typeof BroadcastChannel !== 'undefined') {
      channel = new BroadcastChannel(`exp-notifications:${user}`)
      channel.onmessage = realtimeHandler
    }
    window.addEventListener('focus', refreshVisible)
    document.addEventListener('visibilitychange', refreshVisible)
    timer = setInterval(refreshVisible, 15000)
  }

  function refreshVisible() {
    if (!document.hidden) notifications.reload()
  }

  function disposeRealtime() {
    if (realtimeSocket && realtimeHandler)
      realtimeSocket.off('crm_notification', realtimeHandler)
    if (realtimeSocket && realtimeHandler)
      realtimeSocket.off('exp_notifications_changed', realtimeHandler)
    channel?.close()
    channel = null
    clearInterval(timer)
    window.removeEventListener('focus', refreshVisible)
    document.removeEventListener('visibilitychange', refreshVisible)
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
