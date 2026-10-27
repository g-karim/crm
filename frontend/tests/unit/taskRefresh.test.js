import { describe, it, expect, vi } from 'vitest'
import { createTaskRefresh, hasTaskDraft, taskChanges, standardTaskChanges } from '../../src/utils/taskRefresh'
import { saveCRMTaskDraft } from '../../src/utils/taskSave'

const fixture = () => ({ name: '42', doc: { name: '42', title: 'Original', modified: 'M1' }, originalDoc: { name: '42', title: 'Original', modified: 'M1' }, setDoc(doc) { this.doc = doc } })

describe('CRM task updates across applications', () => {
  it('keeps input typed while a background read is pending', async () => {
    const resource = fixture(), apply = vi.fn()
    let resolve
    const controller = createTaskRefresh({ resource, viewer: 'me', read: () => new Promise(done => { resolve = done }), apply })
    const read = controller.refresh()
    resource.doc.title = 'My new draft'
    resolve({ viewer: 'me', document: { title: 'Other tab', modified: 'M2' } })
    await read
    expect(apply).not.toHaveBeenCalled()
    expect(resource.doc.title).toBe('My new draft')
    expect(resource.crmTaskRemoteChanged).toBe(true)
  })
  it('keeps native input that commits only on blur', async () => {
    const resource = fixture(), apply = vi.fn()
    resource.crmTaskTyping = true
    await createTaskRefresh({ resource, viewer: 'me', read: async () => ({ viewer: 'me', document: { modified: 'M2' } }), apply }).refresh()
    expect(apply).not.toHaveBeenCalled()
    expect(resource.crmTaskRemoteChanged).toBe(true)
  })
  it('a committed unknown save remains replayable after a background read', async () => {
    const resource = fixture(), apply = vi.fn()
    resource.crmTaskPending = { mutation_id: 'same-committed-request' }
    await createTaskRefresh({ resource, viewer: 'me', read: async () => ({ viewer: 'me', document: { modified: 'M2' } }), apply }).refresh()
    expect(apply).not.toHaveBeenCalled()
    expect(resource.crmTaskRemoteChanged).not.toBe(true)
    expect(resource.crmTaskPending.mutation_id).toBe('same-committed-request')
  })
  it('refreshes a clean form without a page reload', async () => {
    const resource = fixture(), apply = vi.fn()
    const value = { title: 'Other tab', modified: 'M2' }
    await createTaskRefresh({ resource, viewer: 'me', read: async () => ({ viewer: 'me', document: value }), apply }).refresh()
    expect(apply).toHaveBeenCalledWith(value)
  })
  it('hides a revoked source without erasing its unsaved draft', async () => {
    const resource = fixture();resource.doc.title = 'Retain draft'
    await createTaskRefresh({ resource, viewer: 'me', read: async () => { throw { exc_type: 'PermissionError' } }, apply: vi.fn() }).refresh()
    expect(resource.crmTaskUnavailable).toBe(true)
    expect(resource.doc.title).toBe('Retain draft')
  })
  it('does not apply a response for another session', async () => {
    const resource = fixture(), apply = vi.fn()
    await createTaskRefresh({ resource, viewer: 'me', read: async () => ({ viewer: 'other', document: { modified: 'M2' } }), apply }).refresh()
    expect(resource.crmTaskUnavailable).toBe(true)
    expect(apply).not.toHaveBeenCalled()
  })
  it('ignores a late response after the form is unmounted', async () => {
    const resource = fixture(), apply = vi.fn();let resolve
    const controller = createTaskRefresh({ resource, viewer: 'me', read: () => new Promise(done => { resolve = done }), apply })
    const read = controller.refresh();controller.stop();resolve({ viewer: 'me', document: { modified: 'M2' } });await read
    expect(apply).not.toHaveBeenCalled()
  })
  it('retries the same unknown save rather than applying a different draft', async () => {
    const resource = fixture();resource.doc.title = 'Save me'
    const request = vi.fn().mockRejectedValueOnce(Error('Lost response')).mockResolvedValueOnce({ task: { name: '42' } }).mockResolvedValueOnce({ viewer: 'me', document: { name: '42', title: 'Save me', modified: 'M2' } })
    const options = { request, viewer: 'me', mutationId: () => 'stable-operation' }
    await saveCRMTaskDraft(resource, options)
    const first = structuredClone(request.mock.calls[0][1]);expect(resource.crmTaskPending).toBeTruthy()
    resource.doc.title = 'Do not substitute this'
    await saveCRMTaskDraft(resource, options)
    expect(request.mock.calls[1][1]).toEqual(first)
    expect(resource.doc.title).toBe('Save me');expect(hasTaskDraft(resource)).toBe(false)
  })
  it('blocks a stale save, keeping the draft', async () => {
    const resource = fixture();resource.doc.title = 'Keep'
    await saveCRMTaskDraft(resource, { viewer: 'me', mutationId: () => 'key', request: async () => { throw { exc_type: 'TimestampMismatchError' } } })
    expect(resource.crmTaskRemoteChanged).toBe(true);expect(resource.crmTaskPending).toBeNull();expect(resource.doc.title).toBe('Keep')
  })
  it.each(['QueryDeadlockError', 'QueryTimeoutError', 'DuplicateEntryError', 'TypeError'])('retains the original request after %s and a later source update', async (exc_type) => {
    const resource = fixture();resource.doc.title = 'Original save'
    const request = vi.fn().mockRejectedValueOnce({ exc_type, status: 500 }).mockResolvedValueOnce({ replayed: true }).mockResolvedValueOnce({ viewer: 'me', document: { name: '42', title: 'Original save', modified: 'M2' } })
    const mutationId = vi.fn(() => 'one-operation')
    const options = { request, viewer: 'me', mutationId }
    await saveCRMTaskDraft(resource, options)
    const first = structuredClone(resource.crmTaskPending)
    expect(first.mutation_id).toBe('one-operation')
    await createTaskRefresh({ resource, viewer: 'me', read: async () => ({ viewer: 'me', document: { modified: 'M2' } }), apply: vi.fn() }).refresh()
    resource.doc.title = 'Do not substitute another draft'
    await saveCRMTaskDraft(resource, options)
    expect(request.mock.calls[1][1]).toEqual(first)
    expect(mutationId).toHaveBeenCalledTimes(1)
    expect(resource.crmTaskPending).toBeNull()
    expect(resource.doc.title).toBe('Original save')
  })
  it('allows editing rejected input after a definitive validation error', async () => {
    const resource = fixture();resource.doc.title = 'Rejected'
    await saveCRMTaskDraft(resource, { viewer: 'me', mutationId: () => 'rejected', request: async () => { throw { exc_type: 'ValidationError', status: 417 } } })
    expect(resource.crmTaskPending).toBeNull()
    expect(resource.doc.title).toBe('Rejected')
    expect(resource.crmTaskRemoteChanged).not.toBe(true)
  })
  it('keeps custom fields on the existing native save path', () => {
    const resource = fixture();resource.doc.title = 'Changed';resource.doc.custom_approved = 1
    expect(standardTaskChanges(taskChanges(resource))).toBe(false)
    delete resource.doc.custom_approved
    expect(standardTaskChanges(taskChanges(resource))).toBe(true)
  })
})
