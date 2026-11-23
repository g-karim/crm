/** Inclusive calendar periods anchored to the server report date, never UTC now. */
export function analyticsPeriod(key, today) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(today))
    throw new RangeError('Invalid calendar date')
  const [year, month, day] = today.split('-').map(Number)
  const end = new Date(Date.UTC(year, month - 1, day))
  if (end.toISOString().slice(0, 10) !== today)
    throw new RangeError('Invalid calendar date')
  const start = new Date(end)
  if (key === 'month') start.setUTCDate(1)
  else if (key === 'quarter') {
    start.setUTCDate(1)
    start.setUTCMonth(Math.floor((month - 1) / 3) * 3)
  } else if (key === '30days') start.setUTCDate(day - 29)
  else throw new RangeError('Unknown analytics period')
  return { from_date: start.toISOString().slice(0, 10), to_date: today }
}
