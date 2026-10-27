export function hasTaskDraft(resource) {
  return Boolean(resource.crmTaskTyping) || JSON.stringify(resource.doc || {}) !== JSON.stringify(resource.originalDoc || {})
}

export function taskChanges(resource) {
  const ignored = new Set(['doctype', 'name', 'creation', 'owner', 'modified', 'modified_by', 'docstatus', 'idx', '_assign', '__onload'])
  return Object.fromEntries(Object.entries(resource.doc || {}).filter(([key, value]) =>
    !ignored.has(key) && JSON.stringify(value) !== JSON.stringify(resource.originalDoc?.[key]),
  ))
}

export function standardTaskChanges(values) {
  return Object.keys(values).every(key => ['title', 'description', 'due_date', 'priority', 'assigned_to', 'status'].includes(key))
}

// Check again after the HTTP response: typing can begin while a read is pending.
export function createTaskRefresh({ resource, read, apply, viewer }) {
  let busy = false, stopped = false
  async function refresh(force = false) {
    if (busy || stopped || !resource.doc || resource.get?.loading || resource.save?.loading || resource.setValue?.loading || resource.crmTaskSaving) return
    busy = true
    try {
      const value = await read()
      if (stopped) return
      if (value.viewer !== viewer) {
        resource.crmTaskUnavailable = true
        return
      }
      resource.crmTaskUnavailable = false
      resource.crmTaskRefreshError = false
      resource.crmTaskSafeSave = Boolean(value.safe_save)
      const latest = value.document
      if (!force && resource.crmTaskPending) return
      if (!force && latest.modified === resource.originalDoc?.modified) return
      if (!force && hasTaskDraft(resource)) {
        resource.crmTaskRemoteChanged = true
        return
      }
      if (resource.save?.loading || resource.setValue?.loading || resource.crmTaskSaving) return
      await apply(latest)
      resource.crmTaskTyping = false
      resource.crmTaskRemoteChanged = false
    } catch (error) {
      if (stopped) return
      if (['PermissionError', 'AuthenticationError', 'DoesNotExistError'].includes(error.exc_type) || [401, 403].includes(error.status)) resource.crmTaskUnavailable = true
      resource.crmTaskRefreshError = true
    } finally { busy = false }
  }
  return { refresh, stop: () => { stopped = true } }
}
