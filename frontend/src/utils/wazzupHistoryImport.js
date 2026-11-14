import { dayjs } from 'frappe-ui'

const API = 'crm_messenger.api.wazzup_partner_history'
const REQUEST_FIELDS = {
  get_channel_import: ['channel'],
  get_import_status: ['import_id'],
  start_import: [
    'channel',
    'start_at',
    'end_at',
    'create_conversations',
    'create_leads',
  ],
  start_processing: ['import_id', 'expected_generation'],
}
const ACTIVE_STATES = [
  'queued',
  'requesting_export',
  'waiting_export',
  'export_unknown',
  'export_ready',
]
export const HISTORY_COUNTERS = {
  created: 'Messages imported: {0}',
  duplicate: 'Duplicate messages: {0}',
  tombstone: 'Deleted messages skipped: {0}',
  unknown_conversation: 'Messages without a conversation: {0}',
  unresolved: 'Messages awaiting resolution: {0}',
  rejected: 'Rejected messages: {0}',
}
const ERROR_MESSAGES = {
  provider_rejected: 'The provider rejected the export request.',
  export_unknown: 'The export request result is unknown. Review is required.',
  rate_limited: 'The provider rate limit was reached.',
  export_expired: 'The provider export is no longer available.',
  export_not_found: 'The provider export was not found.',
  invalid_response: 'The provider returned an invalid export response.',
  channel_unavailable: 'The messenger channel is unavailable.',
  account_unavailable: 'The Wazzup account is unavailable.',
  export_subscription_unconfirmed:
    'The Wazzup history webhook subscription is unconfirmed.',
  export_url_unavailable: 'The provider export file is not available yet.',
  download_unavailable: 'The history file download is temporarily unavailable.',
  download_rejected: 'The history file download was rejected.',
  download_unsafe: 'The history file download destination was rejected.',
  download_limit: 'The history file exceeds download limits.',
  download_invalid: 'The history file could not be verified.',
  file_unavailable: 'Private history file storage is unavailable.',
  invalid_csv: 'The history CSV could not be validated.',
  invalid_file: 'The history file could not be verified.',
  unsupported_file: 'This history file format is not supported.',
  scope_unavailable: 'The history import account or channel is unavailable.',
  policy_unavailable: 'The saved history import settings are unavailable.',
  batch_failed: 'History processing stopped after the last saved batch.',
  snapshot_changed: 'The saved history processing context has changed.',
  internal_error: 'History import could not continue.',
}
const RPC_MESSAGES = [
  'You are not permitted to access this history import.',
  'History import or channel was not found.',
  'History import parameters or state are invalid.',
  'History import is temporarily unavailable.',
]

export function historyImportError(code) {
  return Object.hasOwn(ERROR_MESSAGES, code)
    ? ERROR_MESSAGES[code]
    : 'History import could not continue.'
}

export function historyImportRpcError(message) {
  return RPC_MESSAGES.includes(message) ? message : RPC_MESSAGES[3]
}

export function historyImportTimezone() {
  return (
    globalThis.window?.timezone?.system ||
    Intl.DateTimeFormat().resolvedOptions().timeZone
  )
}

export function newHistoryImportForm() {
  return {
    from: '',
    through: dayjs().tz(historyImportTimezone()).format('YYYY-MM-DD'),
    createConversations: true,
    createLeads: false,
  }
}

export function historyImportPeriod(
  from,
  through,
  timezone = historyImportTimezone(),
) {
  const validDate = (value) => {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value))
      return false
    const date = new Date(`${value}T00:00:00Z`)
    return (
      Number.isFinite(date.getTime()) &&
      date.toISOString().slice(0, 10) === value
    )
  }
  if (!validDate(from) || !validDate(through) || from > through) {
    throw new Error('Select an ordered date range for history import.')
  }
  // Parse each boundary in the CRM zone separately: DST days need not be 24 hours.
  return {
    start_at: dayjs.tz(`${from} 00:00:00.000`, timezone).toISOString(),
    end_at: dayjs.tz(`${through} 23:59:59.999`, timezone).toISOString(),
  }
}

export function formatHistoryImportTime(value) {
  return dayjs(value).tz(historyImportTimezone()).format('DD.MM.YYYY HH:mm')
}

export function canResumeHistoryImport(status) {
  return Boolean(
    status?.state === 'export_ready' &&
    status.file_status === 'ready' &&
    status.file?.format === 'csv' &&
    Number.isSafeInteger(status.generation) &&
    (!status.processing.enabled ||
      (status.processing.phase === 'blocked' &&
        [
          'file_unavailable',
          'scope_unavailable',
          'policy_unavailable',
          'batch_failed',
          'snapshot_changed',
        ].includes(status.processing.error))),
  )
}

export function historyImportStatusLabel(status) {
  if (status?.result) {
    return {
      succeeded: 'History import completed',
      partial: 'History import partially completed',
      failed: 'History import failed',
    }[status.result.outcome]
  }
  if (status?.state === 'failed') return 'History import failed'
  if (status?.state === 'cancelled') return 'History import cancelled'
  if (status?.state === 'completed') return 'History import completed'
  if (status?.state === 'export_ready') {
    if (status.file_status !== 'ready') return 'Downloading history export'
    if (!status.processing.enabled) return 'History file ready for processing'
    return {
      validate: 'Validating history CSV',
      existing: 'Importing messages into existing conversations',
      replay: 'Creating missing conversations and importing messages',
      blocked: 'History processing needs attention',
      awaiting_followup: 'Finishing history import',
    }[status.processing.phase]
  }
  return (
    {
      queued: 'History export queued',
      requesting_export: 'Requesting history export',
      waiting_export: 'Exporting history in Wazzup',
      export_unknown: 'History export result unknown',
    }[status?.state] || 'Import status'
  )
}

function normalizeSummary(value, replay = false) {
  if (value == null) return null
  const count = (number) => Number.isSafeInteger(number) && number >= 0
  if (
    !count(value.processed) ||
    !(
      value.total === null ||
      (count(value.total) && value.total >= value.processed)
    ) ||
    !count(value.conversations_created) ||
    !count(value.leads_created) ||
    value.leads_created > value.conversations_created ||
    !value.counts ||
    !Object.keys(HISTORY_COUNTERS).every((key) => count(value.counts[key]))
  )
    throw new Error()
  const summary = {
    total: value.total,
    processed: value.processed,
    counts: Object.fromEntries(
      Object.keys(HISTORY_COUNTERS).map((key) => [key, value.counts[key]]),
    ),
    conversations_created: value.conversations_created,
    leads_created: value.leads_created,
  }
  if (replay) {
    if (
      !(
        (value.replay_processed === null && value.replay_total === null) ||
        (count(value.replay_processed) &&
          count(value.replay_total) &&
          value.replay_processed <= value.replay_total)
      )
    )
      throw new Error()
    summary.replay_processed = value.replay_processed
    summary.replay_total = value.replay_total
  } else {
    if (!['succeeded', 'partial', 'failed'].includes(value.outcome))
      throw new Error()
    summary.outcome = value.outcome
    summary.reason = Object.hasOwn(ERROR_MESSAGES, value.reason)
      ? value.reason
      : null
  }
  return summary
}

export function normalizeHistoryImport(value) {
  if (
    value?.ok !== true ||
    typeof value.import_id !== 'string' ||
    !value.import_id ||
    typeof value.channel !== 'string' ||
    !value.channel ||
    !Number.isSafeInteger(value.generation) ||
    value.generation < 1 ||
    ![...ACTIVE_STATES, 'completed', 'failed', 'cancelled'].includes(
      value.state,
    ) ||
    value.active !== ACTIVE_STATES.includes(value.state) ||
    typeof value.policy?.create_conversations !== 'boolean' ||
    typeof value.policy?.create_leads !== 'boolean' ||
    typeof value.processing?.enabled !== 'boolean' ||
    ![
      null,
      'validate',
      'existing',
      'replay',
      'blocked',
      'awaiting_followup',
    ].includes(value.processing.phase) ||
    ![value.start_at, value.end_at].every(
      (date) =>
        typeof date === 'string' &&
        date.endsWith('Z') &&
        Number.isFinite(Date.parse(date)),
    )
  )
    throw new Error()
  return {
    import_id: value.import_id,
    channel: value.channel,
    generation: value.generation,
    state: value.state,
    active: value.active,
    start_at: value.start_at,
    end_at: value.end_at,
    policy: {
      create_conversations: value.policy.create_conversations,
      create_leads: value.policy.create_leads,
    },
    processing: {
      enabled: value.processing.enabled,
      phase: value.processing.phase,
      error: value.processing.error
        ? Object.hasOwn(ERROR_MESSAGES, value.processing.error)
          ? value.processing.error
          : 'internal_error'
        : null,
    },
    file_status: value.file_status,
    file: value.file ? { format: value.file.format } : null,
    result: normalizeSummary(value.result),
    progress: normalizeSummary(value.progress, true),
    error: value.error?.code ? historyImportError(value.error.code) : null,
    duplicate: value.duplicate === true,
  }
}

// No resource retries or provider calls: every mutation needs a separate user action.
// Keep server exceptions, URLs and message content out of both UI and console.
export async function callWazzupHistory(action, args = {}) {
  let message = 'History import is temporarily unavailable.'
  try {
    const fields = REQUEST_FIELDS[action]
    if (
      !fields ||
      Object.keys(args).some((key) => !fields.includes(key)) ||
      fields.some((key) => !(key in args))
    )
      throw new Error()
    const headers = {
      Accept: 'application/json',
      'Content-Type': 'application/json; charset=utf-8',
      'X-Frappe-Site-Name': window.location.hostname,
    }
    if (window.csrf_token && window.csrf_token !== '{{ csrf_token }}')
      headers['X-Frappe-CSRF-Token'] = window.csrf_token
    const response = await fetch(`/api/method/${API}.${action}`, {
      method: 'POST',
      credentials: 'same-origin',
      redirect: 'error',
      headers,
      body: JSON.stringify(args),
    })
    const data = await response.json()
    if (response.ok && !data.exc && Object.hasOwn(data, 'message')) {
      let value = data.message
      if (action === 'get_channel_import') {
        if (value?.ok !== true || !Object.hasOwn(value, 'import'))
          throw new Error()
        value = value.import
        if (value === null) return null
      }
      const status = normalizeHistoryImport(value)
      if (
        (args.channel && status.channel !== args.channel) ||
        (args.import_id && status.import_id !== args.import_id)
      )
        throw new Error()
      return status
    }
    if (response.status === 403) message = RPC_MESSAGES[0]
    else if (response.status === 404) message = RPC_MESSAGES[1]
    else if (response.status === 417) message = RPC_MESSAGES[2]
    if (RPC_MESSAGES.includes(data.message)) message = data.message
  } catch {
    // Deliberately discard untrusted exception text and never retry here.
  }
  throw new Error(message)
}
