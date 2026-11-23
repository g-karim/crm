import { describe, it, expect } from 'vitest'
import { viewCacheKey, viewFilters } from '@/utils/viewResource'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

// Execute the actual deployed resource implementation with local transport.
const resourceSource = readFileSync(
  process.cwd() + '/node_modules/frappe-ui/src/resources/resources.js',
  'utf8',
)
function resourceFixture() {
  const pending = []
  const requests = []
  const context = {
    reactive: (x) => x,
    debounce: (x) => x,
    request: () => {
      throw new Error('Unexpected network')
    },
    getLocal: async () => null,
    saveLocal: () => {},
    getConfig: () => null,
    AbortController,
    Event,
  }
  vm.createContext(context)
  vm.runInContext(
    resourceSource.replace(/^import .*\n/gm, '').replace(/^export /gm, '') +
      '\nglobalThis.create = createResource;',
    context,
  )
  const fetcher = ({ params }) => {
    requests.push(params.default_filters.pipeline)
    return new Promise((resolve) => pending.push(resolve))
  }
  const mount = (pipeline) =>
    context.create({
      auto: true,
      params: { default_filters: { pipeline } },
      cache: viewCacheKey('CRM Deal', undefined, 'kanban', { pipeline }),
      resourceFetcher: fetcher,
    })
  return { pending, requests, mount }
}

const tick = () => new Promise((resolve) => setTimeout(resolve, 0))

describe('pipeline list scope', () => {
  it('keeps the newly selected pipeline visible when the previous response arrives later', async () => {
    const { mount, pending, requests } = resourceFixture()
    const a = mount('machines')
    const b = mount('shafts')
    expect(a).not.toBe(b)
    pending[1]({ pipeline: 'shafts' })
    await tick()
    pending[0]({ pipeline: 'machines' })
    await tick()
    expect(requests).toEqual(['machines', 'shafts'])
    expect(b.data.pipeline).toBe('shafts')
    expect(a.data.pipeline).toBe('machines')
  })
  it('overrides the saved pipeline without losing other filters or modifying the saved view', () => {
    const saved = { pipeline: 'machines', status: 'open', owner: 'me' }
    expect(viewFilters('CRM Deal', saved, { pipeline: 'shafts' })).toEqual({
      pipeline: 'shafts',
      status: 'open',
      owner: 'me',
    })
    expect(saved.pipeline).toBe('machines')
    expect(viewFilters('CRM Lead', saved, { pipeline: 'shafts' })).toEqual(
      saved,
    )
  })
})
