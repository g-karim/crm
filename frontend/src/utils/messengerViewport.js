export const MESSENGER_BOTTOM_THRESHOLD = 96

export function isMessengerViewportNearBottom(
  element,
  threshold = MESSENGER_BOTTOM_THRESHOLD,
) {
  if (!element) return true
  return (
    element.scrollHeight - element.scrollTop - element.clientHeight < threshold
  )
}

export function shouldFollowMessengerTyping({ active, wasNearBottom } = {}) {
  return Boolean(active && wasNearBottom)
}
