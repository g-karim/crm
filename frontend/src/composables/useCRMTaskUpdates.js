import { onMounted, onBeforeUnmount } from 'vue'
import { frappeRequest } from 'frappe-ui'
import { createTaskRefresh } from '@/utils/taskRefresh'

const observers = new WeakMap()

export function useCRMTaskUpdates(resource, doctype, name, socket, afterRead) {
  if (doctype !== 'CRM Task' || !name) return
  let owned
  onMounted(() => {
    owned = observers.get(resource)
    if (owned) { owned.users += 1; return }
    const viewer = new URLSearchParams(document.cookie.split('; ').join('&')).get('user_id')
    resource.crmTaskViewer ||= viewer
    const controller = createTaskRefresh({
      resource, viewer: resource.crmTaskViewer,
      read: () => frappeRequest({ url: '/api/method/crm.api.celio_tasks.get_document', method: 'GET', params: { name: String(name) }, signal: AbortSignal.timeout(20000) }),
      apply: async (doc) => {
        resource.setDoc(doc)
        resource.originalDoc = JSON.parse(JSON.stringify(resource.doc))
        await afterRead?.()
      },
    })
    const refresh = () => { if (!document.hidden) controller.refresh() }
    const channel = typeof BroadcastChannel === 'undefined' ? null : new BroadcastChannel(`exp-notifications:${viewer}`)
    channel?.addEventListener('message', refresh)
    const timer = setInterval(refresh, 10000)
    window.addEventListener('focus', refresh)
    document.addEventListener('visibilitychange', refresh)
    socket?.on('crm_tasks_changed', refresh)
    resource.crmTaskReload = () => controller.refresh(true)
    owned = { users: 1, stop() {
      controller.stop(); clearInterval(timer); channel?.close()
      window.removeEventListener('focus', refresh)
      document.removeEventListener('visibilitychange', refresh)
      socket?.off('crm_tasks_changed', refresh)
    } }
    observers.set(resource, owned)
    refresh()
  })
  onBeforeUnmount(() => {
    if (owned && --owned.users === 0) { owned.stop(); observers.delete(resource) }
  })
}
