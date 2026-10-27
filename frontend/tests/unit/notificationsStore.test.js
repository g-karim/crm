import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const resources = vi.hoisted(() => new Map())

vi.mock('frappe-ui', () => ({
  frappeRequest: vi.fn(),
  createResource(options) {
    let resource = {
      options,
      data: options.initialData,
      reload: vi.fn(),
      reset: vi.fn(),
      submit: vi.fn(async () => ({})),
    }
    resources.set(options.url, resource)
    return resource
  },
}))

import {
  notifications,
  notificationsStore,
  loadNotificationsForUser,
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

  it('loads notifications after session startup and clears them on logout', async () => {
    expect(
      resources.get('crm.api.notifications.get_notifications').options.auto,
    ).toBe(false)

    await loadNotificationsForUser('specialist@example.test')
    expect(notifications.reset).toHaveBeenCalledOnce()
    expect(notifications.reload).toHaveBeenCalledOnce()

    await loadNotificationsForUser(null)
    expect(notifications.reset).toHaveBeenCalledTimes(2)
    expect(notifications.reload).toHaveBeenCalledOnce()
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

  it('passes the displayed head and session owner to a read request', async () => {
    notifications.data = {
      notifications: [{ name: 'N-1', head: 'loaded-head' }],
      viewer: 'person@example.invalid',
    }
    await notificationsStore().markNotificationAsRead('N-1')
    expect(
      resources.get('crm.api.notifications.mark_as_read').submit,
    ).toHaveBeenCalledWith({
      notification: 'N-1',
      observed_head: 'loaded-head',
      expected_viewer: 'person@example.invalid',
    })
  })

  it('keeps one frozen snapshot while paging mark-all', async () => {
    notifications.data = {
      notifications: [],
      viewer: 'person@example.invalid',
      snapshot_token: 'loaded-snapshot',
    }
    const store = notificationsStore()
    const markAll = resources.get('crm.api.notifications.mark_all_as_read')
    markAll.submit
      .mockResolvedValueOnce({
        has_more: true,
        snapshot_token: 'loaded-snapshot',
        cursor: 500,
      })
      .mockResolvedValueOnce({
        has_more: false,
        snapshot_token: 'loaded-snapshot',
        cursor: 1000,
      })
    await store.markAllAsRead()
    expect(markAll.submit).toHaveBeenNthCalledWith(1, {
      limit: 500,
      snapshot_token: 'loaded-snapshot',
      cursor: 0,
      expected_viewer: 'person@example.invalid',
    })
    expect(markAll.submit).toHaveBeenNthCalledWith(2, {
      limit: 500,
      snapshot_token: 'loaded-snapshot',
      cursor: 500,
      expected_viewer: 'person@example.invalid',
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
