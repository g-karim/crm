import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const resources = vi.hoisted(() => new Map())

vi.mock('frappe-ui', () => ({
  createResource(options) {
    let resource = {
      data: options.initialData,
      reload: vi.fn(),
      submit: vi.fn(async () => ({})),
    }
    resources.set(options.url, resource)
    return resource
  },
}))

import {
  notifications,
  notificationsStore,
  unreadNotificationsCount,
} from '@/stores/notifications'

describe('notifications store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    notifications.data = {
      notifications: [],
      unread_count: 0,
      has_more: false,
    }
    vi.clearAllMocks()
  })

  it('uses the server unread count instead of the limited list', () => {
    notifications.data = {
      notifications: [{ name: 'N-1', read: false }],
      unread_count: 37,
      has_more: true,
    }

    expect(unreadNotificationsCount.value).toBe(37)
  })

  it('marks one notification by name', () => {
    let store = notificationsStore()

    store.markNotificationAsRead('N-1')

    expect(
      resources.get('crm.api.notifications.mark_as_read').submit,
    ).toHaveBeenCalledWith({
      notification: 'N-1',
    })
  })

  it('repeats bounded mark-all requests while the server has more rows', async () => {
    let store = notificationsStore()
    let markAll = resources.get('crm.api.notifications.mark_all_as_read')
    markAll.submit
      .mockResolvedValueOnce({ has_more: true })
      .mockResolvedValueOnce({ has_more: false })

    await store.markAllAsRead()

    expect(markAll.submit).toHaveBeenCalledTimes(2)
    expect(markAll.submit).toHaveBeenNthCalledWith(1, { limit: 500 })
    expect(notifications.reload).toHaveBeenCalledOnce()
  })
})
