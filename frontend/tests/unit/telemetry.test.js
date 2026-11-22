import { describe, expect, it, vi } from 'vitest'
import { initializeTelemetry } from '@/utils/telemetry'

describe('telemetry consent before remote plugin loading', () => {
  it.each([undefined, null, {}, { enabled: false }, { enabled: 1 }])(
    'does not load the remote client without explicit consent: %s',
    async (config) => {
      const app = { use: vi.fn() }
      expect(await initializeTelemetry(app, {}, async () => config)).toBe(false)
      expect(app.use).not.toHaveBeenCalled()
    },
  )

  it('keeps the client unloaded when the backend is unavailable', async () => {
    const app = { use: vi.fn() }
    const fetchConfig = vi.fn().mockRejectedValue(new Error('offline'))
    expect(await initializeTelemetry(app, {}, fetchConfig)).toBe(false)
    expect(app.use).not.toHaveBeenCalled()
  })

  it.each([
    { enabled: true },
    { enabled: true, host: 'https://pulse.example' },
  ])(
    'fails closed for incomplete enabled configuration: %s',
    async (config) => {
      const app = { use: vi.fn() }
      expect(await initializeTelemetry(app, {}, async () => config)).toBe(false)
      expect(app.use).not.toHaveBeenCalled()
    },
  )

  it('preserves the server consent, client and anonymous identity settings', async () => {
    const app = { use: vi.fn() }
    const plugin = {}
    const config = {
      enabled: true,
      host: 'https://pulse.example',
      key: 'fixture-public-ingest-key',
      site: 'fixture.localhost',
      client_url: 'https://pulse.example/client.js',
      user: null,
      team: 'fixture-team',
    }
    const fetchConfig = vi.fn().mockResolvedValue(config)
    expect(await initializeTelemetry(app, plugin, fetchConfig)).toBe(true)
    expect(fetchConfig).toHaveBeenCalledTimes(1)
    expect(app.use).toHaveBeenCalledTimes(1)
    const [installedPlugin, options] = app.use.mock.calls[0]
    expect(installedPlugin).toBe(plugin)
    expect(options).toMatchObject({
      app_name: 'crm',
      enabled: true,
      host: config.host,
      apiKey: config.key,
      site: config.site,
      clientUrl: config.client_url,
    })
    expect(options.getContext()).toEqual({ user: null, team: 'fixture-team' })
  })
})
