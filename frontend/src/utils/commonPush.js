let loading
export function initCommonPush() {
  const boot = window.frappe?.boot || window.boot || window
  if (!boot?.exp_common_push_test) return Promise.resolve(null)
  if (!loading) loading = new Promise((resolve, reject) => {
    if (window.ExpCommonPushReady) return resolve()
    const script = document.createElement('script')
    script.src = '/assets/exp_theme/js/push/bootstrap.js'
    script.onload = resolve
    script.onerror = () => reject(new Error('Common push client unavailable'))
    document.head.append(script)
  }).then(() => window.ExpCommonPushReady).then(library => library.start({
    viewer: boot.exp_push_viewer, csrfToken: boot.csrf_token || window.csrf_token,
  }))
  return loading
}
