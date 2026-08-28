import {
  isMessengerViewportNearBottom,
  shouldFollowMessengerTyping,
} from '@/utils/messengerViewport'

describe('messenger viewport', () => {
  it('follows an appearing or updated typing indicator near the bottom', () => {
    expect(
      isMessengerViewportNearBottom({
        scrollHeight: 1000,
        scrollTop: 420,
        clientHeight: 500,
      }),
    ).toBe(true)
    expect(
      shouldFollowMessengerTyping({ active: true, wasNearBottom: true }),
    ).toBe(true)
  })

  it('does not force the viewport down after the user scrolls up', () => {
    expect(
      isMessengerViewportNearBottom({
        scrollHeight: 1000,
        scrollTop: 100,
        clientHeight: 500,
      }),
    ).toBe(false)
    expect(
      shouldFollowMessengerTyping({ active: true, wasNearBottom: false }),
    ).toBe(false)
  })

  it('never follows disappearance of the typing indicator', () => {
    expect(
      shouldFollowMessengerTyping({ active: false, wasNearBottom: true }),
    ).toBe(false)
  })
})
