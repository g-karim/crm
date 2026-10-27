import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { frappeRequest } from 'frappe-ui'
import { globalStore } from '@/stores/global'

export function useNotificationDelivery() {
  const state = ref(null)
  const error = ref('')
  const loading = ref(false)
  const saving = ref(false)
  const pending = ref(null)
  const { $socket } = globalStore()
  let channel, timer, owner
  let disposed = false
  const source = computed(() =>
    state.value?.sources.find((item) => item.id === 'crm'),
  )

  function accept(value) {
    if (owner && owner !== value.viewer) {
      state.value = null
      pending.value = null
      throw new Error(__('Your session changed. Reload this page.'))
    }
    owner = value.viewer
    state.value = value
    if (!channel && typeof BroadcastChannel !== 'undefined') {
      channel = new BroadcastChannel(`exp-notifications:${owner}`)
      channel.onmessage = () => reload()
    }
  }

  async function reload() {
    if (loading.value || disposed) return
    loading.value = true
    try {
      accept(
        await frappeRequest({
          url: '/api/method/crm.api.application_notifications.get_settings',
          method: 'GET',
          signal: AbortSignal.timeout(20000),
        }),
      )
      if (!pending.value) error.value = ''
    } catch (exception) {
      error.value =
        exception.messages?.[0] || __('Could not load notification settings.')
      if (
        [401, 403].includes(exception.status) ||
        ['AuthenticationError', 'PermissionError'].includes(exception.exc_type)
      )
        state.value = null
    } finally {
      loading.value = false
    }
  }

  async function save(draft) {
    if (saving.value || !source.value) return
    const request = pending.value || {
      enabled: draft.enabled,
      sender: draft.sender || null,
      push_route: draft.push ? 'One' : 'None',
      expected_revision: draft.revision,
      mutation_id: crypto.randomUUID(),
      expected_viewer: owner,
    }
    pending.value = request
    saving.value = true
    error.value = ''
    try {
      accept(
        await frappeRequest({
          url: '/api/method/crm.api.application_notifications.save_settings',
          method: 'POST',
          params: request,
          signal: AbortSignal.timeout(20000),
        }),
      )
      pending.value = null
      channel?.postMessage({ changed: true })
      return true
    } catch (exception) {
      // Unknown HTTP outcome keeps this exact operation for a safe retry.
      if (exception.exc_type || exception.exception) pending.value = null
      if (
        [401, 403].includes(exception.status) ||
        ['AuthenticationError', 'PermissionError'].includes(exception.exc_type)
      )
        state.value = null
      error.value =
        exception.messages?.[0] || __('Could not save notification settings.')
      return false
    } finally {
      saving.value = false
    }
  }

  function visibility() {
    if (!document.hidden) reload()
  }
  async function discardAndReload() {
    pending.value = null
    await reload()
  }
  onMounted(() => {
    reload()
    $socket?.on('exp_notifications_changed', reload)
    window.addEventListener('focus', reload)
    document.addEventListener('visibilitychange', visibility)
    timer = setInterval(visibility, 15000)
  })
  onBeforeUnmount(() => {
    disposed = true
    $socket?.off('exp_notifications_changed', reload)
    window.removeEventListener('focus', reload)
    document.removeEventListener('visibilitychange', visibility)
    clearInterval(timer)
    channel?.close()
  })
  return {
    state,
    source,
    error,
    loading,
    saving,
    pending,
    reload,
    save,
    discardAndReload,
  }
}
