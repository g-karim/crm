const keys = [
  'from_date',
  'to_date',
  'owner',
  'pipeline',
  'source',
  'call_line',
  'call_direction',
  'call_outcome',
  'call_view',
  'call_trend',
  'call_compare',
  'call_group',
  'call_metrics',
  'call_transcript_state',
  'call_review_script',
]
const outcomes = [
  'Agreed',
  'Callback',
  'Not interested',
  'Wrong number',
  'unprocessed',
]

export function callScopeQuery(query) {
  const result = {}
  for (const key of keys) {
    const value = query[key]
    if (typeof value !== 'string' || !value || value.length > 180) continue
    if (key === 'call_line' && !/^[0-9a-f]{24}$/.test(value)) continue
    if (
      key === 'call_direction' &&
      !['Incoming', 'Outgoing', 'unknown'].includes(value)
    )
      continue
    if (key === 'call_outcome' && !outcomes.includes(value)) continue
    if (key === 'call_view' && !['sla', 'team', 'quality'].includes(value))
      continue
    if (key === 'call_trend' && value !== 'weeks') continue
    if (key === 'call_compare' && value !== '1') continue
    if (
      key === 'call_group' &&
      !['employees', 'teams', 'lines', 'hours', 'weekdays'].includes(value)
    )
      continue
    if (key === 'call_metrics' && !['volume', 'answer', 'work'].includes(value))
      continue
    if (
      key === 'call_transcript_state' &&
      ![
        'ready',
        'not_started',
        'in_progress',
        'failed',
        'empty',
        'too_long',
        'unavailable',
        'eligible',
        'pending_review',
      ].includes(value)
    )
      continue
    if (key === 'call_review_script' && !/^[a-z][a-z0-9_-]{0,31}$/.test(value))
      continue
    if (key.endsWith('_date') && !/^\d{4}-\d{2}-\d{2}$/.test(value)) continue
    result[key] = value
  }
  return result
}

export function callReportFilters(query) {
  const filters = callScopeQuery(query)
  return {
    from_date: filters.from_date,
    to_date: filters.to_date,
    pipeline: filters.pipeline,
    source: filters.source,
    employee: filters.owner,
    line: filters.call_line,
    direction: filters.call_direction,
    outcome: filters.call_outcome,
  }
}
