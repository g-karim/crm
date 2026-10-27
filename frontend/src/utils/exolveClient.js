export function normalizeExolveNumber(value) {
  const raw = String(value || '').trim()
  if (!/^\+?[\d\s().-]+$/.test(raw)) {
    throw new Error('Enter a valid phone number.')
  }
  let number = raw.replace(/\D/g, '')
  if (number.length === 11 && number.startsWith('8')) {
    number = '7' + number.slice(1)
  }
  if (number.length < 7 || number.length > 15) {
    throw new Error('Enter a valid phone number.')
  }
  return number
}

export async function acquireExolveTabLock(username) {
  if (!navigator.locks) return () => {}
  return new Promise((resolve, reject) => {
    navigator.locks
      .request(`crm-exolve:${username}`, { ifAvailable: true }, (lock) => {
        if (!lock) {
          resolve(null)
          return
        }
        return new Promise((release) => resolve(release))
      })
      .catch(reject)
  })
}

// Same WSS/realm/STUN endpoints as Exolve Web Voice SDK 1.4.0.
// JsSIP keeps the SIP secret in memory; there is no SDK localStorage mirror.
export function createExolveClient({
  sip,
  audio,
  onState,
  onCall,
  onError,
  onAudioBlocked,
  getAudioConstraints = () => true,
}) {
  let ua = null
  let session = null
  let destroyed = false
  let registrationTimer = null
  const audioConnections = new WeakSet()

  const callOptions = () => ({
    mediaConstraints: { audio: getAudioConstraints(), video: false },
    sessionTimersExpires: 500,
    pcConfig: { iceServers: [{ urls: ['stun:webrtc.exolve.ru:3478'] }] },
  })

  function attachAudio(connection) {
    if (audioConnections.has(connection)) return
    audioConnections.add(connection)
    connection.addEventListener('track', (event) => {
      audio.srcObject = event.streams[0] || new MediaStream([event.track])
      audio.play().catch(() => onAudioBlocked?.())
    })
  }

  function bindSession(next, incoming) {
    if (session && !session.isEnded()) {
      next.terminate({ status_code: 486, reason_phrase: 'Busy Here' })
      return
    }
    session = next
    const number = next.remote_identity?.uri?.user || ''
    onCall({ number, incoming, state: incoming ? 'incoming' : 'dialing' })
    next.on('peerconnection', ({ peerconnection }) =>
      attachAudio(peerconnection),
    )
    if (next.connection) attachAudio(next.connection)
    next.on('icecandidate', ({ candidate, ready }) => {
      // A usable public/relay candidate is enough for Exolve. Waiting for
      // unrelated interfaces/STUN timeouts delayed real INVITEs by ~40s.
      if (candidate?.type === 'srflx' || candidate?.type === 'relay') ready()
    })
    next.on('progress', () =>
      onCall({ number, incoming, state: incoming ? 'incoming' : 'ringing' }),
    )
    next.on('confirmed', () => onCall({ number, incoming, state: 'connected' }))
    const finish = (failed) => {
      if (session !== next) return
      session = null
      audio.pause()
      audio.srcObject = null
      if (!destroyed)
        onCall({ number, incoming, state: failed ? 'failed' : 'ended' })
    }
    next.on('ended', () => finish(false))
    next.on('failed', ({ cause } = {}) => {
      finish(true)
      if (cause === 'User Denied Media Access' || cause === 'WebRTC Error') {
        onError('Could not access the microphone. Check browser permissions.')
      }
    })
  }

  return {
    async connect() {
      onState('connecting')
      const module = await import('jssip')
      if (destroyed) return
      const JsSIP = module.default || module
      const socket = new JsSIP.WebSocketInterface('wss://webrtc.exolve.ru:443')
      const id = crypto.randomUUID().replaceAll('-', '')
      ua = new JsSIP.UA({
        sockets: [socket],
        uri: `sip:${sip.username}@webrtc.exolve.ru`,
        realm: 'webrtc.exolve.ru',
        password: sip.password,
        contact_uri: `sip:${sip.username}-${id}@${id}.invalid`,
        display_name: sip.username,
        register_expires: 100,
        session_timers: true,
      })
      sip.password = ''
      ua.on('registered', () => {
        clearTimeout(registrationTimer)
        if (!destroyed) onState('ready')
      })
      ua.on('unregistered', () => {
        if (!destroyed) onState('connecting')
      })
      ua.on('disconnected', () => {
        // JsSIP reconnects its transport and registers again automatically.
        // Keep the same UA and tab ownership instead of requiring another click.
        if (!destroyed) onState('connecting')
      })
      ua.on('registrationFailed', () => {
        clearTimeout(registrationTimer)
        if (!destroyed) {
          onState('offline')
          onError('Could not register the Exolve SIP account.')
        }
      })
      ua.on('newRTCSession', ({ session: next, originator }) =>
        bindSession(next, originator === 'remote'),
      )
      registrationTimer = setTimeout(() => {
        if (!destroyed && !ua?.isRegistered()) {
          ua?.stop()
          onState('offline')
          onError('Exolve connection timed out. Try connecting again.')
        }
      }, 20000)
      ua.start()
    },
    call(number) {
      if (!ua?.isRegistered() || session)
        throw new Error('Connect Exolve before making a call.')
      ua.call(
        `sip:${normalizeExolveNumber(number)}@webrtc.exolve.ru`,
        callOptions(),
      )
    },
    answer() {
      session?.answer(callOptions())
    },
    hangup() {
      session?.terminate()
    },
    mute(value) {
      if (value) session?.mute({ audio: true })
      else session?.unmute({ audio: true })
    },
    sendDtmf(tone) {
      if (/^[0-9*#]$/.test(tone)) session?.sendDTMF(tone)
    },
    destroy() {
      destroyed = true
      clearTimeout(registrationTimer)
      ua?.terminateSessions()
      ua?.stop()
      ua?.removeAllListeners()
      ua = null
      session = null
      sip.password = ''
      audio.pause()
      audio.srcObject = null
    },
  }
}
