import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import {
  acquireExolveTabLock,
  createExolveClient,
  normalizeExolveNumber,
} from '@/utils/exolveClient'

const fake = vi.hoisted(() => ({ ua: null }))
vi.mock('jssip', () => ({
  default: {
    WebSocketInterface: class {
      constructor(url) {
        this.url = url
      }
    },
    UA: class {
      constructor(config) {
        this.config = config
        this.events = {}
        fake.ua = this
      }
      on(name, cb) {
        this.events[name] = cb
      }
      start = vi.fn()
      isRegistered = () => true
      call = vi.fn()
      stop = vi.fn()
      terminateSessions = vi.fn()
      removeAllListeners = vi.fn()
    },
  },
}))

describe('Exolve SIP client', () => {
  let client, audio, credentials, onCall, onState
  beforeEach(() => {
    fake.ua = null
    vi.useFakeTimers()
    credentials = { username: '883140000000001', password: 'test-sip-secret' }
    audio = {
      pause: vi.fn(),
      play: vi.fn().mockResolvedValue(),
      srcObject: null,
    }
    onCall = vi.fn()
    onState = vi.fn()
    client = createExolveClient({
      sip: credentials,
      audio,
      onCall,
      onState,
      onError: vi.fn(),
    })
  })
  afterEach(() => {
    client.destroy()
    vi.useRealTimers()
  })

  it('normalizes Russian numbers and blocks SIP URI and control strings', () => {
    expect(normalizeExolveNumber('8 (999) 000-00-01')).toBe('79990000001')
    for (const value of [
      'sip:evil@host',
      '123',
      '79990000001;transport=tcp',
      '*100#',
    ]) {
      expect(() => normalizeExolveNumber(value)).toThrow()
    }
  })

  it('connects explicitly, clears returned credentials, and never persists SIP secrets', async () => {
    const storage = vi.spyOn(Storage.prototype, 'setItem')
    expect(fake.ua).toBeNull()
    await client.connect()
    expect(fake.ua.config.sockets[0].url).toBe('wss://webrtc.exolve.ru:443')
    expect(fake.ua.start).toHaveBeenCalledOnce()
    expect(credentials.password).toBe('')
    expect(storage).not.toHaveBeenCalled()
    fake.ua.events.registered()
    expect(onState).toHaveBeenLastCalledWith('ready')
    storage.mockRestore()
  })

  it('uses current selected microphone for outgoing calls and incoming answers', async () => {
    client.destroy()
    let selected = { deviceId: { exact: 'usb-input' } }
    client = createExolveClient({
      sip: credentials,
      audio,
      onCall,
      onState,
      getAudioConstraints: () => selected,
    })
    await client.connect()
    client.call('79990000001')
    expect(fake.ua.call.mock.lastCall[1].mediaConstraints.audio).toEqual(
      selected,
    )
    const incoming = makeSession()
    fake.ua.events.newRTCSession({ session: incoming, originator: 'remote' })
    selected = true
    client.answer()
    expect(incoming.answer).toHaveBeenCalledWith(
      expect.objectContaining({
        mediaConstraints: { audio: true, video: false },
      }),
    )
  })

  it('dials through the fixed Exolve realm and does not dial while a session exists', async () => {
    await client.connect()
    client.call('+7 (999) 000-00-01')
    expect(fake.ua.call).toHaveBeenCalledWith(
      'sip:79990000001@webrtc.exolve.ru',
      expect.objectContaining({
        mediaConstraints: { audio: true, video: false },
      }),
    )
    const session = makeSession()
    fake.ua.events.newRTCSession({ session, originator: 'local' })
    expect(() => client.call('79990000002')).toThrow()
    session.events.confirmed()
    expect(onCall).toHaveBeenLastCalledWith(
      expect.objectContaining({ state: 'connected' }),
    )
    client.mute(true)
    expect(session.mute).toHaveBeenCalledWith({ audio: true })
    client.sendDtmf('1')
    expect(session.sendDTMF).toHaveBeenCalledWith('1')
    client.sendDtmf('bad')
    expect(session.sendDTMF).toHaveBeenCalledTimes(1)
    session.events.ended()
    expect(audio.srcObject).toBeNull()
    expect(onCall).toHaveBeenLastCalledWith(
      expect.objectContaining({ state: 'ended' }),
    )
  })

  it('handles incoming accept/reject and rejects a second concurrent session', async () => {
    await client.connect()
    const session = makeSession()
    fake.ua.events.newRTCSession({ session, originator: 'remote' })
    expect(onCall).toHaveBeenLastCalledWith(
      expect.objectContaining({ state: 'incoming' }),
    )
    client.answer()
    expect(session.answer).toHaveBeenCalledOnce()
    const second = makeSession()
    fake.ua.events.newRTCSession({ session: second, originator: 'remote' })
    expect(second.terminate).toHaveBeenCalledWith(
      expect.objectContaining({ status_code: 486 }),
    )
    client.hangup()
    expect(session.terminate).toHaveBeenCalledOnce()
  })

  it('sends the offer once a public or relay candidate exists, retaining host-only gathering', async () => {
    await client.connect()
    const session = makeSession()
    fake.ua.events.newRTCSession({ session, originator: 'local' })
    const ready = vi.fn()
    session.events.icecandidate({ candidate: { type: 'host' }, ready })
    expect(ready).not.toHaveBeenCalled()
    session.events.icecandidate({ candidate: { type: 'srflx' }, ready })
    expect(ready).toHaveBeenCalledOnce()
    session.events.icecandidate({ candidate: { type: 'relay' }, ready })
    expect(ready).toHaveBeenCalledTimes(2)
  })

  it('stops sessions and ignores late registration after logout/unmount', async () => {
    await client.connect()
    const ua = fake.ua
    client.destroy()
    expect(ua.stop).toHaveBeenCalledOnce()
    expect(ua.terminateSessions).toHaveBeenCalledOnce()
    onState.mockClear()
    ua.events.registered()
    ua.events.disconnected()
    ua.events.unregistered()
    expect(onState).not.toHaveBeenCalled()
  })

  it('keeps the same client through transport recovery without another connect action', async () => {
    await client.connect()
    const ua = fake.ua
    ua.events.registered()
    ua.events.disconnected()
    expect(onState).toHaveBeenLastCalledWith('connecting')
    expect(ua.stop).not.toHaveBeenCalled()
    ua.events.registered()
    expect(onState).toHaveBeenLastCalledWith('ready')
    expect(fake.ua).toBe(ua)
    expect(ua.start).toHaveBeenCalledOnce()
    expect(ua.call).not.toHaveBeenCalled()
  })

  it('keeps a tab lock until disconnect and rejects a second owner', async () => {
    let held = false
    const original = navigator.locks
    Object.defineProperty(navigator, 'locks', {
      configurable: true,
      value: {
        request: async (_name, _options, handler) => {
          if (held) return handler(null)
          held = true
          await handler({ name: 'test' })
          held = false
        },
      },
    })
    try {
      const release = await acquireExolveTabLock('same-sip')
      expect(await acquireExolveTabLock('same-sip')).toBeNull()
      release()
      await Promise.resolve()
      const next = await acquireExolveTabLock('same-sip')
      expect(next).toBeTypeOf('function')
      next()
    } finally {
      Object.defineProperty(navigator, 'locks', {
        configurable: true,
        value: original,
      })
    }
  })
})

function makeSession() {
  return {
    events: {},
    remote_identity: { uri: { user: '79990000002' } },
    on(name, cb) {
      this.events[name] = cb
    },
    isEnded: () => false,
    terminate: vi.fn(),
    answer: vi.fn(),
    mute: vi.fn(),
    unmute: vi.fn(),
    sendDTMF: vi.fn(),
  }
}
