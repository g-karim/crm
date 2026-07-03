export function getMessengerChannelType(channel = {}) {
  return channel?.channel_type || channel?.chat_type || ''
}

export function getMessengerPlatformLabel(channel = {}) {
  let type = getMessengerChannelType(channel)

  if (type === 'avito') return 'Avito'
  if (type === 'whatsapp') return 'WhatsApp'

  return (
    channel?.display_name ||
    channel?.plain_id ||
    type ||
    channel?.name ||
    'Wazzup'
  )
}

export function buildMessengerChannelOptions(channels = []) {
  let baseLabels = channels.map((channel) => getMessengerPlatformLabel(channel))
  let totals = baseLabels.reduce((acc, label) => {
    acc[label] = (acc[label] || 0) + 1
    return acc
  }, {})
  let seen = {}

  return channels.map((channel, index) => {
    let baseLabel = baseLabels[index]
    seen[baseLabel] = (seen[baseLabel] || 0) + 1

    return {
      label:
        totals[baseLabel] > 1 && seen[baseLabel] > 1
          ? `${baseLabel} ${seen[baseLabel]}`
          : baseLabel,
      value: channel.name,
    }
  })
}
