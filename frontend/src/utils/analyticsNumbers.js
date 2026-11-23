/** Format an exact decimal API value without converting its integer part to Number. */
export function formatAnalyticsNumber(value, locale = 'ru-RU', digits = 2) {
  if (value === null || value === undefined || value === '') return '—'
  if (!Number.isInteger(digits) || digits < 0 || digits > 20) return '—'
  if (typeof value === 'number' && !Number.isFinite(value)) return '—'
  const match = String(value)
    .trim()
    .match(/^([+-]?)(\d+)(?:\.(\d+))?$/)
  if (!match) return '—'

  let integer = BigInt(match[2])
  let fraction = match[3] || ''
  if (fraction.length > digits) {
    const scale = 10n ** BigInt(digits)
    let units = BigInt(fraction.slice(0, digits) || '0')
    if (fraction[digits] >= '5') units += 1n
    if (units === scale) {
      integer += 1n
      units = 0n
    }
    fraction = digits ? units.toString().padStart(digits, '0') : ''
  }
  fraction = fraction.replace(/0+$/, '')

  const formatter = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 })
  const decimal =
    new Intl.NumberFormat(locale)
      .formatToParts(1.1)
      .find((part) => part.type === 'decimal')?.value || '.'
  const negative = match[1] === '-' && (integer !== 0n || fraction !== '')
  const minus = negative
    ? formatter.formatToParts(-1n).find((part) => part.type === 'minusSign')
        ?.value || '-'
    : ''
  return (
    minus + formatter.format(integer) + (fraction ? decimal + fraction : '')
  )
}
