import { describe, expect, it, vi } from 'vitest'
import {
  contextLocked,
  createWorkItem,
  itemDirty,
  saveWorkItem,
  workSnapshot,
  workValues,
} from '@/utils/callWork'

const context = { kind: 'lead', name: 'lead-a' }
const viewer = 'test@example.invalid'
const note = () => createWorkItem('note', { title: 'Call', text: '' })
const response = (name = 'note-a', text = 'First') => ({
  note: { name, title: 'Call', text, modified: '2026-10-23 12:00:01.000000' },
  replayed: false,
})

describe('call work saving', () => {
  it('does not apply a response after the account changes', async () => {
    const item = note()
    item.values.text = 'First'
    await saveWorkItem(item, {
      request: vi.fn().mockResolvedValue(response()),
      viewer,
      context,
      isCurrentViewer: () => false,
    })
    expect(item.name).toBeNull()
    expect(item.values.text).toBe('First')
    expect(itemDirty(item)).toBe(true)
  })
  it('normalizes note whitespace and task datetime values consistently', () => {
    expect(
      workValues('note', { title: ' Call ', text: ' First\nSecond ' }),
    ).toEqual({ title: 'Call', text: 'First\nSecond' })
    expect(
      workValues('task', {
        title: 'Task',
        due_date: '2026-10-23T12:30',
        status: 'Todo',
        priority: 'Medium',
      }).due_date,
    ).toBe('2026-10-23 12:30:00')
  })

  it('requires an explicit customer and never sends a contextless save', async () => {
    const item = note(),
      request = vi.fn()
    item.values.text = 'First'
    await saveWorkItem(item, { request, viewer, context: null })
    expect(request).not.toHaveBeenCalled()
    expect(itemDirty(item)).toBe(true)
    expect(item.pending).toBeNull()
  })

  it('freezes the exact operation and payload after an unknown outcome, retaining later typing', async () => {
    const item = note(),
      request = vi
        .fn()
        .mockRejectedValueOnce(new Error('Lost response'))
        .mockResolvedValueOnce(response())
    item.values.text = 'First'
    const options = {
      request,
      viewer,
      context,
      mutationId: vi.fn().mockReturnValue('mutation-00000001'),
    }
    await saveWorkItem(item, options)
    const pending = item.pending
    expect(contextLocked({ note: item, tasks: [] })).toBe(true)
    item.values.text = 'Later typing'
    await saveWorkItem(item, options)
    expect(request.mock.calls[0][1]).toBe(request.mock.calls[1][1])
    expect(pending.values.text).toBe('First')
    expect(options.mutationId).toHaveBeenCalledOnce()
    expect(item.name).toBe('note-a')
    expect(item.values.text).toBe('Later typing')
    expect(itemDirty(item)).toBe(true)
    expect(item.pending).toBeNull()
  })

  it('does not claim later typing is saved while a request is in flight', async () => {
    let complete
    const item = note(),
      request = vi.fn().mockImplementation(
        () =>
          new Promise((resolve) => {
            complete = resolve
          }),
      )
    item.values.text = 'First'
    const saving = saveWorkItem(item, { request, viewer, context })
    item.values.text = 'Second'
    complete(response())
    await saving
    expect(item.values.text).toBe('Second')
    expect(item.snapshot).toBe(
      workSnapshot('note', { title: 'Call', text: 'First' }),
    )
    expect(itemDirty(item)).toBe(true)
  })

  it('clears rejected operations, preserves text and blocks conflicting saves', async () => {
    const item = note()
    item.name = 'note-a'
    item.values.text = 'Draft'
    const request = vi
      .fn()
      .mockRejectedValue({ exc_type: 'TimestampMismatchError' })
    await saveWorkItem(item, { request, viewer, context })
    expect(item.pending).toBeNull()
    expect(item.conflict).toBe(true)
    expect(item.values.text).toBe('Draft')
    await saveWorkItem(item, { request, viewer, context })
    expect(request).toHaveBeenCalledOnce()
  })

  it('does not overwrite a changed server version returned by a replay', async () => {
    const item = note()
    item.values.text = 'First'
    const request = vi.fn().mockResolvedValue({
      ...response('note-a', 'Someone edited it'),
      replayed: true,
    })
    await saveWorkItem(item, { request, viewer, context })
    expect(item.conflict).toBe(true)
    expect(item.values.text).toBe('First')
    expect(item.snapshot).toBe(
      workSnapshot('note', { title: 'Call', text: 'Someone edited it' }),
    )
  })

  it('keeps different conversations and tasks independent and prevents double submit', async () => {
    const first = note(),
      second = note()
    first.values.text = 'First'
    second.values.text = 'Second'
    let complete
    const request = vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          complete = resolve
        }),
    )
    const saving = saveWorkItem(first, { request, viewer, context })
    await saveWorkItem(first, { request, viewer, context })
    complete(response())
    await saving
    expect(request).toHaveBeenCalledOnce()
    expect(second.name).toBeNull()
    expect(second.values.text).toBe('Second')
  })

  it('keeps permission failures as an unsaved draft and allows a new checked request', async () => {
    const item = note()
    item.values.text = 'First'
    await saveWorkItem(item, {
      request: vi.fn().mockRejectedValue({ exc_type: 'PermissionError' }),
      viewer,
      context,
    })
    expect(item.pending).toBeNull()
    expect(item.values.text).toBe('First')
    expect(itemDirty(item)).toBe(true)
    expect(item.name).toBeNull()
  })
})
