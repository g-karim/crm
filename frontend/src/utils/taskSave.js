import { taskChanges } from './taskRefresh'

const rejectedSaveErrors = new Set(['ValidationError', 'MandatoryError', 'LinkValidationError', 'InvalidSelectValueError', 'PermissionError', 'AuthenticationError', 'DoesNotExistError', 'TimestampMismatchError'])

export async function saveCRMTaskDraft(resource, { request, viewer, mutationId, onSuccess, onError }) {
  if (resource.crmTaskSaving || resource.crmTaskRemoteChanged || resource.crmTaskUnavailable) return
  resource.crmTaskPending ||= {
    name: String(resource.name), values: taskChanges(resource), expected_modified: resource.originalDoc?.modified,
    expected_viewer: viewer, mutation_id: mutationId(),
  }
  resource.crmTaskSaving = true
  try {
    await request('save_task', resource.crmTaskPending, 'POST')
    const latest = await request('get_document', { name: String(resource.name) }, 'GET')
    if (latest.viewer !== viewer) throw { exc_type: 'AuthenticationError', messages: ['Your account changed. Reload before saving.'] }
    resource.setDoc(latest.document)
    resource.originalDoc = JSON.parse(JSON.stringify(resource.doc))
    resource.crmTaskPending = null
    resource.crmTaskRemoteChanged = false
    onSuccess?.(latest.document)
  } catch (error) {
    // A transient server error can race an earlier commit. Keep its exact retry.
    if (rejectedSaveErrors.has(error.exc_type)) resource.crmTaskPending = null
    if (error.exc_type === 'TimestampMismatchError') resource.crmTaskRemoteChanged = true
    if (['AuthenticationError', 'PermissionError'].includes(error.exc_type)) resource.crmTaskUnavailable = true
    onError?.(error)
  } finally { resource.crmTaskSaving = false }
}
