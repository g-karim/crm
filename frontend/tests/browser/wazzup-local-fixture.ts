import { readFileSync } from 'node:fs'

export type WazzupFixture = {
  base_url: string
  frappe_origin: string
  user: string
  password: string
  lead?: string | null
  channel?: string
  conversation?: string | null
  simulator_origin: string
  control_token: string
  inbound_text: string
  file_name: string
  file_content: string
}

export function loadWazzupFixture(): WazzupFixture {
  const file = process.env.WAZZUP_E2E_FIXTURE
  if (!file)
    throw new Error(
      'WAZZUP_E2E_FIXTURE must point to the isolated runner fixture.',
    )
  const fixture = JSON.parse(readFileSync(file, 'utf8')) as WazzupFixture
  for (const key of [
    'base_url',
    'frappe_origin',
    'simulator_origin',
  ] as const) {
    const url = new URL(fixture[key])
    if (
      url.protocol !== 'http:' ||
      url.hostname !== '127.0.0.1' ||
      !url.port ||
      url.username ||
      url.password ||
      url.pathname !== '/' ||
      url.search ||
      url.hash
    ) {
      throw new Error(
        `The isolated runner must provide a loopback HTTP origin for ${key}.`,
      )
    }
  }
  for (const key of [
    'user',
    'password',
    'control_token',
    'inbound_text',
    'file_name',
    'file_content',
  ] as const) {
    if (typeof fixture[key] !== 'string' || !fixture[key]) {
      throw new Error(`The isolated runner fixture is missing ${key}.`)
    }
  }
  return fixture
}
