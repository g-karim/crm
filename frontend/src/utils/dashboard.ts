export type DashboardDateRange = string | [string, string] | [] | null

export function parseDateRange(range: DashboardDateRange): [string, string] {
  if (!range) return ['', '']
  const dates = Array.isArray(range) ? range : range.split(',')
  return [dates[0] || '', dates[1] || '']
}

export function formatter(range: DashboardDateRange) {
  const [from, to] = parseDateRange(range)
  return `${formatRange(from)} to ${formatRange(to)}`
}

export function formatRange(date: string) {
  const dateObj = new Date(date)
  return dateObj.toLocaleDateString('en-US', {
    timeZone: 'UTC',
    month: 'short',
    day: 'numeric',
    year:
      dateObj.getUTCFullYear() === new Date().getUTCFullYear()
        ? undefined
        : 'numeric',
  })
}
