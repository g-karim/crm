import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  createDraftSync,
  draftSnapshot,
  draftFingerprint,
  restoreConversation,
} from '@/utils/callDrafts'
import { createWorkItem } from '@/utils/callWork'
const viewer = 'sales@example.invalid'
function work() {
  return {
    id: crypto.randomUUID(),
    number: '79990000001',
    created: new Date().toISOString(),
    started: true,
    ended: true,
    incoming: false,
    context: { kind: 'lead', name: 'LEAD-1', title: 'Customer' },
    note: createWorkItem('note', { title: 'Conversation', text: 'Draft' }),
    tasks: [],
  }
}
const ok = (revision) => ({ viewer, revision, modified: '2026-10-23 12:00:00' })
afterEach(() => vi.useRealTimers())

describe('private conversation draft queue', () => {
  it('serializes only conversation data, excluding transient flags and credentials', () => {
    const w = work()
    w.password = 'secret'
    w.sip = { password: 'secret' }
    w.note.saving = true
    const data = draftSnapshot(w)
    expect(JSON.stringify(data)).not.toContain('secret')
    expect(data.note).not.toHaveProperty('saving')
    expect(data.context).toEqual({ kind: 'lead', name: 'LEAD-1' })
  })
  it('reports saved only after the matching server acknowledgement', async () => {
    const w = work()
    let resolve
    const request = vi.fn(
      () =>
        new Promise((yes) => {
          resolve = yes
        }),
    )
    const sync = createDraftSync({ work: w, viewer, request })
    const pending = sync.flush()
    await Promise.resolve()
    expect(w.draft.state).toBe('saving')
    expect(w.draft.acknowledged).toBe('')
    resolve(ok(1))
    await pending
    expect(w.draft.state).toBe('saved')
    expect(w.draft.acknowledged).toBe(draftFingerprint(w))
    sync.dispose()
  })
  it('freezes an uncertain request and sends later typing as a subsequent version', async () => {
    const w = work()
    const sent = []
    const request = vi.fn(async (_url, payload) => {
      sent.push(structuredClone(payload))
      if (sent.length === 1) throw Error('lost')
      return ok(sent.length - 1)
    })
    const sync = createDraftSync({ work: w, viewer, request })
    await expect(sync.flush()).rejects.toThrow('lost')
    w.note.values.text = 'Later typing'
    await sync.retry()
    expect(sent[1]).toEqual(sent[0])
    expect(sent[2].snapshot.note.values.text).toBe('Later typing')
    expect(sent[2].mutation_id).not.toBe(sent[1].mutation_id)
    expect(sent[2].expected_revision).toBe(1)
    expect(w.note.values.text).toBe('Later typing')
    expect(w.draft.state).toBe('saved')
    sync.dispose()
  })
  it('serializes simultaneous flushes and never overlaps writes for one draft', async () => {
    const w = work()
    let resolve
    let active = 0,
      max = 0,
      revision = 0
    const request = vi.fn(async () => {
      active++
      max = Math.max(max, active)
      if (revision === 0)
        await new Promise((yes) => {
          resolve = yes
        })
      active--
      return ok(++revision)
    })
    const sync = createDraftSync({ work: w, viewer, request })
    const first = sync.flush()
    await Promise.resolve()
    w.note.values.text = 'Changed'
    const second = sync.flush()
    resolve()
    await Promise.all([first, second])
    expect(max).toBe(1)
    expect(request).toHaveBeenCalledTimes(2)
    expect(w.draft.state).toBe('saved')
    sync.dispose()
  })
  it('stops automatic overwrite on another-tab revision conflict', async () => {
    vi.useFakeTimers()
    const w = work()
    const request = vi
      .fn()
      .mockRejectedValue(
        Object.assign(Error('changed'), { exc_type: 'TimestampMismatchError' }),
      )
    const sync = createDraftSync({ work: w, viewer, request })
    await expect(sync.flush()).rejects.toThrow()
    w.note.values.text = 'Keep me'
    sync.schedule()
    await vi.advanceTimersByTimeAsync(1000)
    expect(request).toHaveBeenCalledOnce()
    expect(w.draft.state).toBe('conflict')
    expect(w.note.values.text).toBe('Keep me')
    sync.dispose()
  })
  it('debounces typing and cancels capture on disposal without marking text saved', async () => {
    vi.useFakeTimers()
    const w = work()
    const request = vi.fn(async () => ok(1))
    const sync = createDraftSync({ work: w, viewer, request })
    sync.schedule()
    w.note.values.text = 'Second'
    sync.schedule()
    await vi.advanceTimersByTimeAsync(599)
    expect(request).not.toHaveBeenCalled()
    sync.dispose()
    await vi.advanceTimersByTimeAsync(1000)
    expect(request).not.toHaveBeenCalled()
    expect(w.draft.acknowledged).toBe('')
  })
  it('does not accept a late acknowledgement for another account', async () => {
    const w = work()
    let resolve,
      current = true
    const request = () =>
      new Promise((yes) => {
        resolve = yes
      })
    const sync = createDraftSync({
      work: w,
      viewer,
      request,
      isCurrentViewer: () => current,
    })
    const pending = sync.flush()
    await Promise.resolve()
    current = false
    resolve(ok(1))
    await expect(pending).rejects.toThrow('Account changed')
    expect(w.draft.acknowledged).toBe('')
    sync.dispose()
  })
  it('can retry a synchronous network exception', async () => {
    const w = work()
    let fail = true
    const request = () => {
      if (fail) throw Error('offline')
      return Promise.resolve(ok(1))
    }
    const sync = createDraftSync({ work: w, viewer, request })
    await expect(sync.flush()).rejects.toThrow('offline')
    fail = false
    await sync.retry()
    expect(w.draft.state).toBe('saved')
    sync.dispose()
  })
  it('refreshes clean canonical records while preserving unsaved conversation text', () => {
    const w = work()
    w.note.name = 'NOTE-1'
    const record = {
      snapshot: draftSnapshot(w),
      revision: 2,
      call_log: null,
      latest: {
        [w.note.key]: {
          name: 'NOTE-1',
          title: 'Updated elsewhere',
          text: 'Current canonical note',
          modified: 'new revision',
        },
      },
    }
    const clean = restoreConversation(record)
    expect(clean.note.values.text).toBe('Current canonical note')
    expect(clean.note.modified).toBe('new revision')
    record.snapshot.note.values.text = 'Unsaved personal text'
    const dirty = restoreConversation(record)
    expect(dirty.note.values.text).toBe('Unsaved personal text')
  })
  it('restores frozen canonical mutations and record IDs without resuming media', () => {
    const w = work()
    w.note.name = 'NOTE-1'
    w.note.pending = {
      mutation_id: crypto.randomUUID(),
      expected_viewer: viewer,
      values: { text: 'Frozen' },
    }
    const restored = restoreConversation({
      snapshot: draftSnapshot(w),
      revision: 7,
      call_log: 'CALL-1',
      modified: 'now',
    })
    expect(restored.note.name).toBe('NOTE-1')
    expect(restored.note.pending.mutation_id).toBe(w.note.pending.mutation_id)
    expect(restored.note.error).toContain('Retry safely')
    expect(restored.note.saving).toBe(false)
    expect(restored.restored).toBe(true)
    expect(restored).not.toHaveProperty('client')
    expect(restored.draft.acknowledged).toBe(draftFingerprint(restored))
  })
})
