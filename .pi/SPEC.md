# CRM Scripting — Stable Contracts

> **This file**: Stable, user-facing API contracts only. No future plans. No implementation history.  
> **Roadmap**: [PLAN.md](./PLAN.md)  
> **Completed phases**: [ARCHIVE.md](./ARCHIVE.md)  
> **Full scripting guide**: [feats/form-scripting/guide.md](./feats/form-scripting/guide.md)  
> **formDialog full reference**: [feats/form-scripting/form-dialog.md](./feats/form-scripting/form-dialog.md)

---

## Table of Contents

1. [Form Script Class Contract](#form-script-class-contract)
2. [Lifecycle Hooks](#lifecycle-hooks)
3. [Field Change Hooks](#field-change-hooks)
4. [setFieldProperty API](#setfieldproperty-api)
5. [Supported Field Properties](#supported-field-properties)
6. [Override Priority](#override-priority)
7. [formDialog API](#formdialog-api)
8. [Available Helpers](#available-helpers)
9. [Testing](#testing)

---

## Form Script Class Contract

Class name = DocType name with spaces removed:

| DocType | Class name |
|---|---|
| `CRM Lead` | `CRMLead` |
| `CRM Deal` | `CRMDeal` |
| `Contact` | `Contact` |
| `CRM Organization` | `CRMOrganization` |

```js
class CRMLead {
  // hooks go here
}
```

`this.doc` — live proxy to the document. Read/write fields directly. No `.value`.  
`this.doc.trigger('methodName')` — the correct way to call methods on your own class.

---

## Lifecycle Hooks

| Hook | Aliases | When it fires |
|---|---|---|
| `onLoad` | `on_load` | Once, when document first loads from server |
| `onRender` | `on_render`, `refresh` | Every time the page renders (first visit + re-visits) |
| `onValidate` | `on_validate`, `validate` | Before every save — throw to block |
| `onSave` | `on_save` | After a successful save |
| `onError` | `on_error` | When a save fails |
| `onBeforeCreate` | `on_before_create` | Before a new document is created via modal |
| `onCreateLead` | `on_create_lead` | CRM Lead only — lead creation flow |
| `convertToDeal` | `convert_to_deal` | CRM Lead only — lead to deal conversion |

All hooks are optional. All hooks can be `async`.

---

## Field Change Hooks

Define a method named **exactly the same as the fieldname**:

```js
class CRMLead {
  status() { /* fires when status field changes */ }
  annual_revenue() { /* fires when annual_revenue changes */ }
}
```

Inside a field hook:
- `this.value` — the new value just set
- `this.oldValue` — the previous value
- `this.currentRowIdx` — the row index if the change was inside a child table

**Row add/remove hooks:**
- `[parentfield]_add` — fires after a row is added. `this.value` = new row object
- `[parentfield]_remove` — fires after row(s) are deleted. `this.selectedRows` = removed names

---

## setFieldProperty API

### `this.setFieldProperty(target, property, value [, rowName])`

```js
// Field
this.setFieldProperty('annual_revenue', 'hidden', true)
this.setFieldProperty('status', 'options', 'New\nOpen\nClosed')

// Section or tab (by name from layout)
this.setFieldProperty('financial_section', 'hidden', true)
this.setFieldProperty('advanced_tab', 'hidden', true)

// Child table column (dot notation)
this.setFieldProperty('products.discount', 'hidden', true)

// Specific row in child table (4th param: row.name)
this.setFieldProperty('products.rate', 'read_only', true, row.name)
```

### `this.setFieldProperties(target, properties [, rowName])`

```js
this.setFieldProperties('annual_revenue', {
  read_only: true,
  label: 'Revenue (USD)',
  description: 'Auto-calculated',
})
```

### `this.removeFieldProperty(target, property [, rowName])`

```js
this.removeFieldProperty('annual_revenue', 'hidden')
this.removeFieldProperty('products.rate', 'read_only', row.name)
```

### `this.getField(fieldname)`

Returns effective field definition (raw meta merged with current script overrides). Not reactive — call again after changes.

```js
const field = this.getField('status')
console.log(field.options, field.read_only, field.hidden)
```

---

## Supported Field Properties

### Field

| Property | Type | Effect |
|---|---|---|
| `hidden` | `boolean` | Show/hide the field |
| `read_only` | `boolean` | Make non-editable |
| `reqd` | `boolean` | Make mandatory (asterisk + validation) |
| `label` | `string` | Field label |
| `placeholder` | `string` | Input placeholder |
| `description` | `string` | Help text below the field |
| `options` | `string` | Select choices (newline-separated) or Link doctype |
| `link_filters` | `object` | Filter object for Link autocomplete |
| `precision` | `string` | Decimal precision for Float/Currency/Percent |
| `button_color` | `string` | `"Default"`, `"Primary"`, `"Info"`, `"Success"`, `"Warning"`, `"Danger"` |

**Select `options` format** — always a newline-separated string:
```js
this.setFieldProperty('status', 'options', 'New\nIn Progress\nClosed')
```

**`link_filters` format** — plain object:
```js
this.setFieldProperty('lead_owner', 'link_filters', { enabled: 1 })
```

### Section

| Property | Type | Effect |
|---|---|---|
| `hidden` | `boolean` | Show/hide entire section |
| `label` | `string` | Section heading |
| `collapsible` | `boolean` | Make collapsible |
| `opened` | `boolean` | Default expanded state |
| `hideLabel` | `boolean` | Hide the section label |
| `hideBorder` | `boolean` | Remove top border |

### Tab

| Property | Type | Effect |
|---|---|---|
| `hidden` | `boolean` | Show/hide the entire tab |
| `label` | `string` | Tab heading |

---

## Override Priority

```
Final value =
  1. Script per-row override  (products.qty:row_name)    ← highest
  2. Script column override   (products.qty)
  3. Script field override    (fieldname)
  4. depends_on expression    (read_only_depends_on, etc.)
  5. Server meta default                                  ← lowest
```

**Hidden fields are always skipped in mandatory validation.** A field hidden via script override is never checked for `reqd`, even if `reqd: 1` in the DocType.

---

## formDialog API

Opens a dialog with a full FieldLayout. Returns a `Promise<object|null>`.

```js
formDialog(options)
```

### Three patterns (all composable)

```js
// 1. Promise — sequential, await the result
const data = await formDialog({ title: 'Step 1', fields: [...] })
if (!data) return  // cancelled

// 2. onSubmit callback — fire-and-forget, code after runs immediately
formDialog({
  title: 'Mark as Lost',
  fields: [...],
  submitLabel: 'Mark as Lost',
  cancelLabel: 'Cancel',
  onSubmit(data) { ... },
  onCancel() { ... },
})

// 3. Custom actions — full control
formDialog({
  title: 'Review',
  fields: [...],
  actions: [
    { label: 'Approve', variant: 'solid', onClick({ data, close, validate }) { close(data) } },
    { label: 'Cancel', onClick({ close }) { close(null) } },
  ],
})
```

### Options

| Option | Type | Description |
|---|---|---|
| `title` | `string` | Dialog title |
| `fields` | `Array` | Flat field definitions — auto-wrapped in single section |
| `tabs` | `Array` | Full layout: `tabs > sections > columns > fields` |
| `doctype` | `string` | Fetch Quick Entry layout for this doctype |
| `fieldnames` | `Array<string>` | With `doctype` — pick only these fields from doctype meta |
| `defaults` | `object` | Pre-fill field values |
| `required` | `Array<string>` | Force mandatory: shows asterisk + validates |
| `size` | `string` | Dialog size: `'sm'`, `'md'`, `'lg'`, `'xl'`, `'2xl'`. Default: `'xl'` |
| `actions` | `Array` | Custom buttons — overrides default Submit and `onSubmit` |
| `onSubmit` | `Function` | Called with `data` on submit. Throw to stay open |
| `onCancel` | `Function` | Called on cancel/close/overlay/escape |
| `submitLabel` | `string` | Default Submit button label. Default: `'Submit'` |
| `cancelLabel` | `string` | If provided, shows a Cancel button with this label |

### Behavior matrix

| `actions` | `onSubmit` | Behavior |
|---|---|---|
| ✗ | ✗ | Submit button → validates → closes → Promise resolves with data |
| ✗ | ✓ | Submit button → validates → `onSubmit(data)` → closes → Promise resolves |
| ✓ | (ignored) | Custom buttons only. Each calls `close(result)` |

> Full reference with layout modes, column layouts, and examples: [feats/form-scripting/form-dialog.md](./feats/form-scripting/form-dialog.md)

---

## Available Helpers

All helpers are available as bare names everywhere in your script — no imports needed.

| Helper | Description |
|---|---|
| `call(method, params)` | Frappe backend RPC — returns a `Promise` |
| `toast.success(msg)` | Green toast notification |
| `toast.error(msg)` | Red toast notification |
| `toast.info(msg)` | Info toast notification |
| `createDialog(options)` | Simple frappe-ui confirm/message dialog (fire-and-forget) |
| `formDialog(options)` | Form dialog with FieldLayout — returns a Promise. See [form-dialog.md](./feats/form-scripting/form-dialog.md) |
| `router` | Vue Router — `router.replace()`, `router.push()`, `router.currentRoute` |
| `router.previousRoute` | Route navigated from — compare `.path` (not `.fullPath`) |
| `socket` | Socket.io instance for realtime events |
| `throwError(message)` | `toast.error` + `throw` in one call — stops execution |
| `crm.makePhoneCall(number)` | Initiate a phone call via CRM call integration |
| `crm.openSettings(page)` | Open the CRM settings panel to a specific page |

---

## Testing

**Runner**: Vitest · **Environment**: happy-dom  
**Location**: `frontend/tests/`

```bash
cd frontend
yarn test          # watch mode
yarn test:run      # single run (CI)
```

**Current state**: 6 test files · 118 tests · ~250ms

### Test files

| File | What it tests |
|---|---|
| `processField.test.js` | Field clone, Select/Link transforms, perm + script overrides |
| `fieldPropertyOverrides.test.js` | setFieldProperty / remove / batch / dot notation / per-row |
| `checkMandatory.test.js` | findMissingMandatory with script override scenarios |
| `scriptHelpers.test.js` | getClassNames, createDocProxy |
| `parseLinkFilters.test.js` | Safe JSON/object parsing for link_filters |
| `renderFieldLayoutDialog.test.js` | Promise behavior, options passthrough, onSubmit/onCancel, concurrent dialogs |

### Rules for adding tests

- Functions under test must be **pure** and **importable without side effects**
- If a function needs extraction from a Vue component, extract to `src/utils/` first
- Use `@/` alias (resolves to `src/`), standard `describe`/`it`/`expect` (vitest globals)

```js
import { processField } from '@/utils/fieldTransforms'

describe('processField', () => {
  it('clones the field', () => {
    const raw = { fieldname: 'x', fieldtype: 'Data' }
    expect(processField(raw)).not.toBe(raw)
  })
})
```

> See `tests/setup.js` for available globals (`__`, `window.sysdefaults`)


---

## Touch Tracking — Backend Records

> Реализовано в отдельном checkout (`codex/crm-touch-tracking-stage2`), выпущено на Таткардан 2026-10-09: [Stage 7](./ARCHIVE.md#touch-tracking--stage-7). Начальный профиль — создание/смена статуса; каналы ожидают live acceptance. Контракт не меняет Form Script API. История и проверки: [Stage 2](./ARCHIVE.md#touch-tracking--stage-2), [Stage 3](./ARCHIVE.md#touch-tracking--stage-3).

| Record / field | Contract |
|---|---|
| `CRM Lead.last_touch_at`, `CRM Deal.last_touch_at` | Server-owned nullable Datetime; increases on selected successful events, never copied or set from client input. Does not replace `modified`. |
| `CRM Touch Settings.enabled` | Check, default 0; settings belong to the current site database. |
| `track_leads`, `track_deals` | Independent Check flags, default 1; inactive until `enabled=1`. Creation initializes the selected type. |
| `lead_status_changes`, `deal_status_changes` | Independent Check flags, default 1; only a real native status transition qualifies. |
| `lead_fields`, `deal_fields` | JSON arrays of editable business field names from site metadata, default `[]`. Status uses its own rule; technical, computed, fetched, secret and table fields are unavailable. |
| `lead_events`, `deal_events` | JSON arrays of internal rule keys, default `[]`. Accepted keys are listed below; unsupported selections are rejected on the server. |
| `lead_allow_automation`, `deal_allow_automation` | Independent Check flags, default 0; permit selected additional internal rules for identified automation sources. Creation/native status retain the Stage 2 profile. |
| `policy_revision` | Server-owned identifier of the immutable settings snapshot; unchanged on a no-op settings save. |
| `CRM Touch Policy` | Immutable configuration snapshot with `effective_from`; recovery uses the snapshot at the source event time. |
| `CRM Touch Event` | Immutable event identity/source/reason/time/actor/policy; mutable server-owned processing metadata only. No copied business content. |
| `CRM Touch Event.state` | Pending → Applied or Ignored (deleted target). Recoverable failures remain Pending with attempts/next_retry_at/last_error. |
| `CRM Touch Change` | Immutable minimal transactional source for mutable internal edits; same identity as its Event. Stores reason keys and source revision, never old/new values or content. Allows materialization retries after disable. |
| `source_revision`, `reasons`, `origin` | Stable saved revision, JSON array of reason keys, and User/Automation/External. Repeated edits of one source have distinct revisions; numeric and textual source names have the same identity. |

Settings writes require System Manager or Sales Manager. Direct journal/policy access is read-only for System Manager; user creation/editing is prohibited. The reason endpoint additionally enforces target, source and linked-document read permissions and filters reason labels by field permissions.

Creation uses the card's `creation`. A status transition uses the persisted new native status-log row's `creation`. Replays use the original timestamp and identity. Applying a background event leaves parent `modified`/`modified_by` unchanged; an ordinary save restores the current server-owned date before writing its row and retains Frappe's concurrency check.

`crm.touch_tracking.maintenance` is a private scheduled job, not an HTTP API. Retry at the transaction boundary is allowed only for this dedicated job. Applying an accepted Pending event after disable retains its original policy; disable prevents accepting new events. No automatic historical replay is performed on enable or policy change.

Internal rule keys: `comment_created`, `comment_edited`, `note_created`, `note_edited`, `task_created`, `task_completed`, `task_status`, `task_due_date`, `task_start_date`, `task_priority`, `task_assigned_to`, `task_title`, `task_description`, `task_comment`. Only `Comment.comment_type=Comment` is eligible. Task comments use only `task_comment` on creation. `Done` transitions use only `task_completed`, not `task_status`. Task/note relinking alone and deletes do not touch; a selected edit uses the new explicit target only.

One card save groups selected fields and an enabled native status transition into one event. Input is compared before and after native validation so values derived by validation are not extra user edits. Native ToDo owner mirrors are observed separately; nested assignments inside a card save do not duplicate that save's reasons.

Internal timestamps use the successful source save's `creation`/`modified`, never the task's planned date. Field edits on a locked card may apply in its transaction. Task/note/comment/assignment events apply in a private worker after commit, with the five-minute scheduler as fallback. Queue submission errors are isolated even after commit. Recovery requires the accepted minimal source to exist; a failure writing that source is diagnosed and preserves the business save, but task history without a source is never guessed.

Authenticated session requests are User actions. Imports, patches, migrations, safe-exec scripts, jobs, Guest/token requests and Python calls without a request are conservatively Automation. This classification does not infer origin from `modified_by`; new adapters must supply verified source semantics. Raw SQL/`frappe.db.set_value` outside the observed native ToDo mirror is not intercepted globally.


### Touch Tracking — Settings UI and List API

The manager-only **Touches and interactions** page is part of CRM Settings. It edits the current site's Singleton, with independent Lead/Deal tabs, selected fields/internal events and automation flags. Missing fields can be removed even while tracking is disabled. Channel selections are independent of internal events. New provider rules remain unavailable until site acceptance; installing an app does not verify a provider. Manual call logging is available without an external provider.

| Endpoint / parameter | Contract |
|---|---|
| `crm.touch_tracking_ui.get_settings()` | Requires System Manager or Sales Manager and Singleton write permission. Returns allowed settings (selection arrays), normalized `modified` version token, eligible field/rule labels and channel availability descriptions. No provider configuration or secrets. A fresh Singleton has token `""`. |
| `crm.touch_tracking_ui.save_settings(settings, expected_modified)` | Same permission checks; locks the Singleton and checks the version. Unknown keys and unsupported rules are rejected. Saves through the original Document path; a stale version raises TimestampMismatchError and retains the previous accepted settings. |
| `crm.touch_tracking_ui.get_reason(doctype, name)` | Requires target read permission and permission for `last_touch_at`. Returns only `date`, translated `reasons`, and a permitted source link or null. No values, content or actor identity. Chooses an Applied event at the current date, with deterministic name tie-breaking; unavailable/deleted/private sources return a generic explanation. |
| `crm.api.doc.get_data(..., view.default_sort)` | Opt-in signal for an unsorted standard view. The server resolves the enabled site's default while preserving stored accessible view choices. An empty order with this flag represents an explicit Clear Sort request. Requests without the flag keep their explicit/native order. Returns effective `order_by` and `default_order_by`. |
| Touch ordering | `COALESCE(last_touch_at, creation) DESC, creation DESC, name DESC`. Ascending touch selection also uses creation fallback. For explicit compound touch sorts, chosen fields/directions retain precedence and missing creation/name tie-breakers are appended. Names/directions are validated; framework query permissions and filters remain active. |
| Columns / saved views | Adds Last Touch only to fresh controller-default Lead/Deal lists of an enabled type. Ordinary list/settings requests never rewrite saved columns/filters/sorts. Explicit migration alone renames legacy field keys, as specified below. The column chooser and sort menu expose Last Touch when enabled; existing saved touch columns remain readable after disabling. List cells load reasons on demand, invalidate cached reasons on timestamp changes and do not open the card on click. |

UI requests have a 20-second timeout and an explicit retry/reload path. A timeout stops the UI loader, not an already running server transaction; retrying a settings write with an outdated token cannot overwrite a committed change. Turning tracking on or changing rules does not recalculate past records. No site/view data migration occurs in Stage 4.

Manual Kanban card ordering remains native and takes precedence over automatic sorting. Reason popovers are implemented in the Lead/Deal list tables; group/Kanban date cells retain their existing date rendering.

### Touch Tracking — Export and Explicit Migration (Stage 6)

- CRM selects `crm.touch_tracking_export.export_query` only for Lead/Deal requests whose effective order contains the exact `last_touch_at` term. CSV/Excel use the same validated permission-aware query, creation fallback, stable tie-breakers and normalized phone filters as the list. Exported empty touch dates use creation, matching the visible column. Offset/page length are honored; selected names intersect existing filters.
- Native reportview validates fields/filters; direct permitted CRM fields only, native export permission including owner-only checks, field metadata, file formatters and Access Log remain in use. Unsupported background/group/or-filter requests are rejected on this CRM route. Other DocTypes and explicit non-touch sorts use the original framework export endpoint. No framework function is patched.
- Hidden readonly Singleton controls `legacy_sort_retired`, `legacy_sort_migration_id`, `legacy_sort_retired_at` are server-managed. Normal saves preserve them; the public settings API does not accept them. Migration-only writes set `flags.touch_migration`.
- Private CLI `crm.touch_tracking_migration.prepare()`, `apply(manifest)`, `rollback(manifest)` require System Manager and installed Lead/Deal touch schema. No automatic patch, HTTP endpoint or implicit commit. Manifest schema 1 is site-bound and hashes its source/seed values; keep the full file for rollback. Prepare requires disabled tracking and no active migration ID.
- Apply locks current settings, targets, history and views, checks source equality and recomputes seeds. Lead uses valid legacy date exactly; otherwise Lead/Deal use creation plus credible consecutive native status transitions, including the final open row. Modified is never a seed. Existing newer touch values are retained. Original business columns/IDs/relations/history remain unchanged and no historical events are invented.
- Only legacy Lead view field keys change, preserving directions, filter values and manual Kanban arrays. Initial profile enables creation/status for both types and disables all additional fields/events/channels/automation. Old writer is retired; a later ordinary disable does not unretire it. Same active manifest ID is a no-op, preserving later dates/settings/preferences.
- Rollback disables tracking/unretires the writer. Rebuilds old Lead dates from original legacy values/creation plus genuine native transitions after cutover; includes newly created leads, never copies unrelated touches. Restores only view slots still equal to the migration's values. New business rows, metadata, touch dates/audit and newer user preferences are retained; repeated rollback is a no-op.
- Ordinary failures roll back the operation savepoint; fatal DB aborts propagate for caller rollback and whole-transaction retry. Locking reads avoid using stale history/view snapshots; MariaDB snapshot conflicts are not treated as success. Code rollback keeps additive schema, clears site hooks/cache and synchronizes the old native schedule, without an old-code migrate. See [migration/release procedure](./feats/touch-tracking/migration.md) for ordering and verification boundaries.


### Touch Tracking — Channel Contracts (Stage 5 local implementation)

- `lead_channels` / `deal_channels`: canonical JSON arrays, default `[]`; keys `message_received`, `message_sent`, `call_incoming_answered`, `call_outgoing_answered`, `call_incoming_missed`, `call_outgoing_unsuccessful`, `call_manual`, `email_received`, `email_sent`.
- `lead_messenger_automation` / `deal_messenger_automation` and `lead_email_automation` / `deal_email_automation`: independent Check flags, default 0. An automated send requires both its outgoing rule and its channel automation permission. Unknown authors are excluded, including when automation is allowed. Internal `allow_automation` does not enable channel sends.
- Settings `channels[].rules` are `{value, label, available}` objects. Category metadata includes `key`, `installed`, `available`, `description`, and optional `automation` suffix. A saved unavailable selection can be removed; new unavailable selections are rejected by Singleton validation as well as the API.
- `CRM Touch Receipt`: private, server-managed source/card/adapter/origin binding, and immutable first confirmed rule/time/hashed identity/policy. No content, addresses, recordings, source values, or raw payload are copied. Bindings remain on their original card after relinking; `event_source_*` preserves the original Communication even after Email Queue cleanup. Accepted receipts materialize `Channel Interaction` Change/Event records through the existing outbox.
- Outgoing authorship is captured at enqueue time; delivery/worker sessions do not redefine it. Only accepted facts claim a unique native confirmation identity: an unknown provider echo cannot suppress a later verified CRM send. A receipt's accepted policy is the immutable snapshot at the occurrence time. Recovery after disable retains accepted facts and cannot accept occurrences governed by a disabled policy.
- `extend_doctype_class` cooperatively extends native Email Account/Queue on Frappe 16. The native receive pipeline exposes parsed headers and new-message state; inbound time is local successful receipt (`Communication.creation`), not an untrusted Date header. MIME transport notifications and Auto-Submitted automatic replies are excluded. Outgoing confirmation observes the native transport's recipient Sent writes and final queue Sent update; a Communication marked Sent alone is insufficient. Queued, failed, and partial delivery do not count; no second event for redaction/delivery/UID updates.
- Messenger document hooks require the provenance/confirmation fields of the audited `crm_messenger` schema. Inbound is a new `provider_webhook` received message with native identity/time. History/import/edits/deletes are excluded. Outbound needs persistent first `sent_at`, native external identity and sent/delivered/read state; queue/retries/failure/read changes are not new events. Pending previously bound successful sends can be recovered without historical scans.
- `capture_provider_call(doc, provider, event_id, direction, outcome, occurred_at, employee, authenticated=False)` is a private server adapter contract, not a whitelisted endpoint. Requires authenticated provider proof, matching native ID/provider/direction and a single primary CRM reference. Outcomes are explicitly `answered` / `missed` / `unsuccessful`; a generic Completed and recording existence are insufficient. Answered and outgoing events require a verified existing employee. The Novofon producer in the isolated fcrm_telephony branch binds a receipt before dispatch and confirms it after an authenticated statistics read; other native fcrm providers are not wired.
- Manual calls count once at successful authenticated user creation, using creation time. Changing old start_time, recording, analysis, or metadata does not represent another call.
- External timestamp offsets are normalized to site timezone; unknown/future timestamps are excluded. Replay identity and existing monotonic application protect newer dates. The receipt recovery query selects missing outbox rows and eligible confirmed native sends before applying a batch limit, so pending queues cannot starve successful sends.
- Server config `crm_touch_verified_adapters` is an acceptance allowlist, default empty; examples of identifiers are `email:frappe`, `messenger:telegram_bot`, `calls:<provider>`. This is not a bypass for missing provider code: call availability also checks registered `crm_touch_call_adapters` readiness hooks. The release workflow must register only adapters with recorded live acceptance. No production allowlist has been changed.

- Novofon producer contract: new native END/OUT_END call sources only; private immutable receipt context `provider_started_at`, `provider_timezone`, `provider_agent_id`, hashed `provider_phone_key` and `provider_call_key`. One mapped enabled employee and one primary card are required. Mutable server-only `probe_attempts`, `next_probe_at`, `probe_state` are retry metadata, never reasons for another touch. No raw callback or phone is copied.
- The Novofon legacy REST producer reads authenticated version-2 PBX statistics; verifies native PBX identity, extension, full phone, direction window and call start time, excludes duplicate/ambiguous legs and unknown results. Answered, busy/cancel/no-answer have separate normalized rules; generic Completed, failed/no-money/unallocated results are insufficient. Automatic outgoing attempts do not bypass the employee requirement.
- `crm_touch_novofon_timezone` must be an explicitly verified IANA zone; unknown, future, date-only and DST-ambiguous clocks have no fallback. Producer readiness requires the updated schema, Novofon settings and site acceptance; a bare allowlist entry cannot enable calls.
- Novofon probes enqueue after business commit, without parent-card locks; bounded cron recovery retries pending receipts with 5–60 minute backoff for seven days. Repeated confirmations are immutable; relinking cannot move the bound card. Native call creation/recording behavior is preserved. Fatal DB aborts propagate for normal Frappe rollback/retry. Actual account/API and whole-PBX completion/transfer/IVR semantics remain live acceptance requirements.
