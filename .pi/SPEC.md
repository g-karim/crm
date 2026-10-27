# CRM Scripting — Stable Contracts

> **This file**: Stable, user-facing API contracts only. No future plans. No implementation history.  
> **Roadmap**: [PLAN.md](./PLAN.md)  
> **Completed phases**: [ARCHIVE.md](./ARCHIVE.md)  
> **Full scripting guide**: [feats/form-scripting/guide.md](./feats/form-scripting/guide.md)  
> **formDialog full reference**: [feats/form-scripting/form-dialog.md](./feats/form-scripting/form-dialog.md)

---

## Home presentation — local Signal styling, 2026-10-25

Standalone `/home` uses the existing Celio Signal light/dark palette and Inter,
with shared semantic tokens in `exp_theme/public/css/home_workspace.css`.
Separators use 1 px low-emphasis borders; selection and keyboard focus retain
distinct indicators. Mail direction backgrounds and black unread dots remain.
The 208/68 px navigation widths, compact-state persistence, mail reading area and
existing actions are preserved. Component treatments are scoped to
`.exp-home-standalone`; embedded/native Desk defaults and authored message HTML
are not restyled by this change. No backend, permissions or mail transport change.

## Personal correspondence in Home — local contract, 2026-10-24

`/home?view=correspondence` is a native-mail/channel workspace for System Users,
independent of CRM roles or customer links. `exp_theme.correspondence` reads native
User Email assignments and optional existing account grants, with explicit opt-in
for additional configured accounts/channels. Selection never grants access or
creates provider accounts. Mailbox ownership authorizes the mail copy only;
business context is checked independently. Native channel reference checks remain.

On CRM sites, the source/user read cursor and revision reuse `CRM Inbox State`.
Home's reply lives in the optional `correspondence_draft` field; `data` retains the
existing CRM reply/internal-note draft unchanged. This permits an internal note
and a mail reply at the same time. Other sites use the service-only Theme state.
Native mail history, source IDs and sender-account binding remain canonical.
The current Home mail UI defaults to Inbox and the employee's own assigned
mailbox. Folder order is Inbox, Favorites, Sent, Drafts, Spam, All, Trash. It requests
`list_threads(message_list=1)` and `get_thread(message_only=1)`: one native
Communication per list item and reading pane. The same flag on save/send/upload/
download binds private drafts/attachments and reply identity to the exact letter;
legacy thread calls without that flag retain their previous behavior.
`update_flags(kind,name,values,expected_revision,expected_viewer)` stores personal
read/favorite/spam/archived/trash boolean metadata after source/viewer checks. Native
Spam/Trash are fallbacks; personal restore does not write to the provider. Archive
excludes Inbox only; Trash excludes every other folder and their counts, preserving
other flags/drafts for restoration. Explicit letter read
state never acknowledges other messages in its chain. Nonempty drafts and internal
CRM notes remain independent. Sample transport guards are server-only.
`get_thread` adds `reply.can_reply_all` only when distinct other To/CC participants
exist. Actual own source/user addresses, reply recipients and BCC are excluded.
Readable body HTML uses a strict server-side tag/attribute/URL allowlist; no remote
content or scripts are loaded, HTTP(S)/simple mailto links remain usable.
`prepare_forward(name,draft_id,expected_viewer)` creates one private compose draft
with blank recipients, source quote and native attachments. A server-only origin
marker rechecks source access on subsequent reads/sends. Forwarding uses compose,
so native `in_reply_to` and CRM reference are not inherited.
`discard_draft(kind,name,expected_revision,expected_viewer,account,message_only)`
clears only the current user's exact draft with revision checking. Private DTOs
include `cleared_revision`; old browser drafts cannot resurrect deleted/sent text.
The state and clear marker remain for stale save/send/discard detection. Internal
CRM `data`, neighboring letter drafts, source messages and attachments are retained.
Local docs: [Home correspondence](../../exp_theme/docs/home-correspondence-2026-10-24.md).

Mail-client additions use the same source/user access rules and native records:

- `list_threads(message_list=1, search, offset, limit)` accepts sender, recipient,
  inclusive local-calendar from/to dates, unread and attachment filters. Account
  scope applies before counts/search. MariaDB projects at most `limit+1` headers
  for a mailbox page, including deep offsets; exact reads never regroup history.
  Explicit index installation is `exp_theme.correspondence_query.ensure_indexes()`;
  reads never run DDL. Mixed optional channels retain native source checks.
- `search_recipients(query,account)` suggests at most eight addresses from that
  accessible mailbox's history. Incoming BCC and unrelated contact lists are excluded.
- `update_many(items,values,mutation_id,expected_viewer)` checks every source and
  revision before applying up to 100 personal metadata changes. Retries return
  the operation receipt. `get_neighbors` respects the current folder/search.
- Drafts accept sanitized `html` alongside `text`. Inline images require a native
  attachment ID owned by this draft/source; remote images stay blocked. Native
  MIME uses verified original bytes and CID images, with native queue/account
  binding checked before accepting send. File uploads/copies/downloads preserve
  bytes without the generic text-decoding helper.
- `get_signature`/`save_signature` use the current user's native
  `User.email_signature`; revision plus a content stamp detect other Home/Desk
  edits. Only the signature field is written, leaving mailbox assignments intact.
- `preview_attachment` rechecks file/source access. PDF pages are rendered to PNG;
  image type/pixel/size limits apply. `download_attachments` returns a source-bound
  ZIP (up to 100 files/50 MB). Originals remain native private Files.
- `get_delivery` reads native Email Queue/Recipient status only. SMTP acceptance
  is labelled as acceptance by the mail server, not receipt by the addressee.
  `retry_delivery` requires current send access, original author and a current
  queue stamp; it preserves recipients already Sent and is idempotent.
  `get_mailbox_status` exposes connection flags without hosts or credentials.

Personal read/spam/archive/trash state and drafts synchronize between Home
sessions through the server. They do not mutate IMAP folders or provider flags.
Real Beget SMTP/IMAP self-addressed acceptance for g.karim@exp-verse.com is verified
locally. Credentials use native encrypted Email Account storage; production supplied
only read-only SMTP metadata. Generic mail/scheduler remain paused.

The optional admin-only `exp_home_mail_pilot` site config selects one exact account
and employee. It requires the isolated switches and read-only IMAP and has no public
configuration API. Legacy self-only policy remains valid; external To/CC/BCC require
both `recipients=[]` and explicit `allow_external_recipients=true`. Home retains its
native send receipt. The private worker selects only receipt-backed native queues,
rechecks author/account/source rights, compares the entire queue envelope against
the Communication's To/CC/BCC and binds the sender to the configured employee.
It respects queue suspension/retry delays and verified TLS; generic queues stay muted.

The configured folder manifest uses independent UIDVALIDITY/UID cursors, including
the existing INBOX cursor. History is seeded explicitly by an authorized local import.
EXAMINE/BODY.PEEK never mutate provider flags or folders. Native MIME parsing/File
storage create Communication Email with the original date and appropriate Sent/
Received direction. Native Message-ID dedup is scoped to account and direction;
folder/UID provenance handles missing IDs and restart safety without rewriting old
messages or their UIDs. Replies stay within the same account; CRM references are
not inferred. Provider drafts become the employee's editable private Home compose
drafts, with no outgoing Communication/queue until explicit Send. Reimport cannot
overwrite or resurrect a locally edited/deleted draft. Initial read/star/spam/trash/
archive flags seed personal metadata only for newly imported mail. Later Home changes
remain independent of external IMAP flags. Auto replies/participant forwarding never
run. The isolated inbox runner checks all configured folders; absent policy is a no-op.

Outgoing native MIME receives original file bytes. Text attachments use binary MIME
to preserve line endings and legacy encodings. Display normalization flattens only
known native/presentation layout tables, retains authored data tables, and starts
an exact letter at its top. The original mail HTML is not rewritten.

## Messenger workspace — local contract, 2026-10-24

`/crm/messenger?open=<messenger|email>:<source name>` opens the exact source.
The source is Messenger Conversation/Message or Communication Email. No history
copies, name/phone merges or subject-based email grouping are created.

- `crm.api.inbox.list_threads(view='open', query='', channel='', account='',
  reference_doctype='', reference_name='', offset=0, limit=30)` returns headers,
  authorized queue counts, available accounts and `has_more`. Views: open, mine,
  unassigned, needs_reply, waiting_customer, unread, snoozed, closed, all. Page size
  1–100. Account and current source CRM permissions apply before search/counts;
  native source subscription restrictions also apply to previews/body search.
  Reference filtering includes explicit Deal.lead relationships under both records'
  independent permissions. It never grants Deal-only readers access to a private Lead.
- `get_thread(kind,name,before_cursor=None)` rechecks source access and returns
  native messages/attachments, private state, explicit CRM contexts, permitted
  customer/company/contacts, native notes/tasks/calls and actual send capabilities.
  Messenger history uses its native bounded cursor API. Read APIs perform no
  provider calls, delivery, provider-read acknowledgements or business writes.
- `save_private(kind,name,expected_revision,draft,read_cursor)` stores only the
  current user's draft/read cursor. A cursor must identify a real inbound source
  message; it cannot acknowledge a concurrent unseen message in another thread.
  Revision conflicts retain text and require explicit user resolution. Browser
  copies are user/source scoped, with their last known server revision.
- `update_work(...,expected_revision,status,assigned_to,snoozed_until,
  context_doctype,context_name)` manages shared operator work separately from
  source/provider states. Snooze requires a future deadline; new inbound identity
  reopens closed/waiting/snoozed work. Read does not close work. Assignment requires
  the assignee's source/account/customer access. Context must be an independently
  writable explicit related Lead/Deal; already saved materials never move.
- `add_note(...,text,mutation_id,context_doctype,context_name)` creates one native
  FCRM Note; `add_task(...,values,mutation_id)` delegates to native CRM Task with
  normal assignment/hooks. Both recheck source and selected context, escape note
  text and retain canonical idempotence. No second task/note is created after a
  lost-response retry. Suggestions and personal drafts are not CRM activities.
- `send_reply(...,text,mutation_id,subject,to,cc,bcc,attachments)` uses the exact
  source account. Messenger calls its native delivery API; its request key is
  server-namespaced by author and prefixed `crm-inbox-`. Email uses native
  Communication creation/queueing, with a transactionally stored operation receipt.
  Header injection and another author's/another thread's attachments are rejected.
  Current local `mute_emails` prevents real email send; local examples never send.
- `upload_attachment` uses private source- and author-bound storage. Email uploads
  belong to the user's CRM Inbox State until native Communication attachment
  creation on explicit send. `email_attachment(file)` rechecks current mailbox
  and CRM context on download. Native Communication/File permission hooks also
  enforce account revocation/private draft ownership. They retain all other
  framework restrictions, including native Inbox User role requirements.
- `set_account_access(kind,account,user,can_read,can_send)` is admin-only. Explicit
  policies override implicit User Email access; absent a policy, personal email
  follows native membership. System Managers retain account administration and
  are the only readers/operators of unlinked conversations. Native Messenger
  lists/history/deltas/attachments/send paths apply the same optional inbox policy.
- `link_customer` is admin-only for Messenger, requires the new primary customer's
  write permission, and does not move saved notes/tasks. Email reference ownership
  stays native. `search_customers` returns at most 20 independently readable cards.

CRM Inbox Work/State/Access/Operation are service-only DocTypes with no generic
REST permissions or writes. Content is never placed in realtime notifications.
All write endpoints accept `expected_viewer`; the UI always binds it to the
author of the captured draft/action. A changed session rejects the write before
any mutation. When a read detects another viewer, the page reloads after keeping
the old draft only under its original user's local key.
The local delivery process selects only explicit `crm-inbox-` outbound messages,
rechecks the author, and uses native outbound state/retry/unknown handling. It
does not consume legacy RQ jobs or send email. Local examples require the explicit
local config flag, have isolated customers and a visible local-only notice.
Usage and acceptance: [Мессенджер](./feats/communications/messenger.md).

## Telephony workspace — local contract, 2026-10-23

`/crm/telephony` is the workspace; `?open=<CRM Call Log.name>` selects a call.
The technical `Call Logs` route, `/crm/call-logs`, saved views and legacy `open`
links remain available. Telephony and Messenger preserve their page instances
across query changes, keeping filters and drafts while selecting records. Other
route keys are unchanged.

- `crm.api.telephony.get_calls(search='', view='all', period='30', mine=0,
  offset=0, page_length=40)` is read-only. Views: all/missed/incoming/outgoing/
  recorded. Periods: all/today/7/30. Page size is bounded to 1–100. Native call
  permissions and primary Lead/Deal/Contact access apply in SQL before search,
  pagination and `has_more`. Unlinked calls follow native call-log access.
  Ordering is start_time-or-creation descending with name as a tie breaker.
  No global total or team analytics are inferred from the loaded page.
- Results expose client number, own line, agent, timestamp, status, duration,
  permitted context and `has_recording`. Provider recording URLs are excluded.
  Search escapes LIKE wildcards and normalizes formatted phone input. Deal
  customer names/search use explicit primary Contact links under Contact's own
  permissions; a private Contact name is not exposed through a readable Deal.
- `get_call(name)` checks call and primary-context access again, including on
  direct links. Its references contain only accessible explicit CRM links.
  `recording_path` reuses the existing authenticated recording proxy or native
  local File path. The proxy also rechecks primary-context read access before
  provider/cache handling; Exolve's participant/application checks remain.
- `search_customers(search)` returns up to five readable phone-bearing records
  per Lead/Deal/Contact type. Choosing a result fills a number; it never places a
  call, creates a CRM record, merges customers or changes call relationships.
- `globalStore.prepareCall(number='')` opens controls before any provider action.
  Exolve uses its persistent dialog; legacy providers receive the existing
  explicit confirmation dialog. Existing card `makeCall` behavior is retained.
  Shared in-memory session state contains connection/line/activity only, no SIP
  credentials. Record players pause during live calls and never auto-resume.
- A missed filter is incoming No Answer/Busy/Failed/Canceled, separate from any
  callback task. Outgoing No Answer remains an unanswered attempt. Completed is
  displayed as a provider completion, not evidence of two-way speech.

The workspace issues no provider requests, imports, calls, paid analysis, messages
or schema changes from its list/detail/search APIs. Since the 23 October
refinement, the separate app-level Exolve client automatically registers the
current mapped user on CRM load. `get_connection_status()` checks only local
enabled/user/role/mapping/key readiness and returns available/reason, without
credentials, other users or provider calls. Unmapped users never borrow an
Administrator mapping. Registration preferences persist a non-secret per-user browser opt-out;
earlier paused connections can be enabled by manual Connect. Settings
saves revalidate the connection. Microphone, dialing and answering stay explicit;
native JsSIP transport recovery retains the client and tab lock. No call starts
from registration. The UI entry to the legacy journal is List view; the separate
recorded tab is removed, while the backend recorded filter remains compatible.
Existing Exolve post-call reconciliation remains independent.
The workspace header exposes List view and Dial a number; settings and connection
status actions are removed. The call dialog is titled Telephony, up to 7xl wide
and sized to the available viewport height. One shared top bar holds the number,
call state/timer and call actions on desktop and mobile. Customer selection is a
compact bar below it. Notes and tasks occupy separate desktop panes; mobile
buttons switch between them without losing input. Manual history refresh, disconnect and
auto-connect help are removed from this dialog. Current connection state remains
inside the call controls; settings remain accessible through the main settings UI.
Physical-mic/DTMF/incoming-route acceptance remains pending. Callback work is
implemented locally in Stage 3 below. In-call note/task writing is available locally:
[ownership and correlation limits](./feats/telephony/call-work-notes.md).

## Telephony Stage 4 — call analysis and metrics, local 2026-10-23

- `?pane=analytics` selects the analytics workspace. Journal and analytics share
  `telephony.filtered_query`; native call/customer permissions and all filters
  precede pagination/metrics. Raw transcript search also checks the analysis's
  original customer independently of the current Call Log reference. Metrics cover
  all permitted imported rows; task counts deduplicate explicit native links and
  independently gate task/customer access. Completed is a journal status, not
  universal proof of an answered conversation.
- `crm.call_analysis.workspace.get(name, run_name=None)` returns an authorized
  immutable analysis version, its accessible versions and opt-in status. Analysis
  source customer is snapshotted and checked again after call relinking. Legacy
  text remains readable with explicit provenance limitations. `recording_matches`
  prevents old timestamps from seeking a replacement recording. Original audio,
  manager notes and provider facts are never analysis output targets.
- Service-only `CRM Call Analysis` and `CRM Call AI Control` have no native CRUD
  role grants and use guarded writes. Once saved, raw text, STT/summary responses,
  segments, hash and summary are immutable. Call/source/customer/request identity
  is immutable from insertion. Settings use revision CAS and native audit versions.
- `start(name, mutation_id, retry=0)` is POST-only, manual, call-write gated and
  disabled by default. It reserves a shared daily USD budget using fresh locking
  reads under one control lock, deduplicates active/exact requests and retries
  stale-snapshot admission only at the owning RPC transaction boundary. Old
  unbudgeted enqueue/worker routes cannot send audio; call save/import does not
  schedule AI. Only the isolated opted-in queue processes new runs.
- Every paid step records durable intent, checks current user/call/source access,
  daily reservations and the provider key's daily limit. A duration-priced STT
  catalog check, actual audio-duration/size bound, summary token cap and chat price
  limits bound inputs. Missing cost or interrupted/unknown response retains the
  reservation and blocks further AI until explicit manager reconciliation. Known
  summary failures retain raw output and reuse it on a new explicit request.
- `confirm_task(name, run_name, index, values, mutation_id, expected_viewer)` is
  POST-only. It requires an explicit edited title/customer/assignee/deadline and
  creates through native CRM task operations. Author/call/run locking and a
  per-suggestion receipt make exact retries idempotent and reject a second edited
  confirmation. Assignment/access/notification behavior stays source-owned.
- `crm.call_analysis.analytics.report` applies the same journal filters to server
  metrics. `callback_status`/`callback_candidates` never infer a link;
  `link_callback(name,outgoing,expected_revision,expected_viewer)` requires explicit
  confirmation of an accessible later outgoing attempt to the same number. The
  separately guarded outcome stores its ID/author/time. Speed counts only readable
  confirmed missed→attempt links, never Task completion as evidence of a call.

Usage, spending behavior, sources and local queue: [Stage 4](./feats/telephony/stage4.md).
Production, SMS and live paid acceptance remain outside this local contract.

### Existing shared AI key — explicit local opt-in, 2026-10-23

`crm_call_analysis_allow_shared_key=true` enables reuse of an existing inference
key when explicitly authorized. Default remains dedicated-key enforcement.
Shared mode never changes provider credentials/limits: it checks GET /key and
GET /credits, current STT rate, bounded UTF-8 prompt/output costs and the complete
local reserve before paid I/O. Existing daily locking/receipts/unknown-cost blocks
remain mandatory. `settings.shared_key` identifies this mode in the budget UI.

Analysis admission and `get.can_start` enforce Exolve's current mapping, exact
application and participant recording access before reserving money. The known
legacy Call Log shape `CRM Lead` with no reference_docname is treated as unlinked
by journal/recording/analysis reads without changing its stored fields. Named
customer references remain permission gated. Failed preflight is retained at zero
cost; it is not a paid retry. A current-caller recording completed live acceptance
locally with immutable raw text, timestamps, summary and actual cost.

## Telephony Stage 3 — outcomes and callback work, local 2026-10-23

- `CRM Call Outcome` is service-only storage keyed by the exact Call Log name.
  It stores the manager outcome independently of provider status: `Agreed`,
  `Callback`, `Not interested`, `Wrong number`. No native role CRUD grants;
  normal service writes use the existing guarded internal-write controller.
- `crm.api.call_followups.get_workspace(name)` projects readable canonical notes
  and tasks from explicit Dynamic Links, plus outcome/revision and accessible
  customer choices, including customers of explicitly linked canonical materials.
  The finished conversation prefers its already selected customer. Each material
  and its current customer are checked independently.
  Personal `CRM Call Work.data` is never part of the response. A revoked callback
  customer hides that review/materials even if the unlinked call remains readable.
- `save_outcome(name, outcome, expected_revision, mutation_id, expected_viewer,
  callback)` is POST-only. It checks current enabled user, call/customer access,
  terminal provider status and native Call Log write permission. Author/call/review
  locking, fresh parent checks, revision CAS and exact last-operation replay prevent
  accidental overwrite. Only the top-level RPC owns deadlock retry/rollback.
- Callback requires explicit `{context_kind,context_name,title,assigned_to,due_date}`.
  One transaction creates a native CRM Task through the source task API, links its
  existing ID to the call and records the outcome. The assignee must independently
  read that task/customer. The task receipt ID is bound to call and operation UUID.
  The form converts the chosen user-local deadline with public `dayjs/getConfig`,
  using the inverse of native `dayjsLocal`;
  the API stores the system-timezone datetime, and native `formatDate` displays it.
  Native assignments, notifications, permissions and task revisions remain canonical.
- An open callback must be explicitly completed/canceled before replacing its
  outcome or scheduling another. Old tasks and links remain. `complete_task` is
  POST-only and updates that linked native task to `Done` or `Canceled` using its
  expected modified value and a task-operation UUID; it does not delete calls/tasks.
- `telephony.get_calls` additionally accepts `view=attention`, exact `employee`,
  `line` and `outcome` filters. `outcome=unprocessed` means no accessible saved
  manager outcome. Legacy `mine` remains compatible. All predicates and native
  call/task/customer permissions apply before pagination/has_more.
- Attention = accessible incoming missed calls without a saved accessible outcome,
  or calls with accessible linked open CRM Tasks due before tomorrow. Future tasks
  wait until due; call-date period is ignored in attention. Employee filters use
  missed-call receiver or due-task assignee there; ordinary views use call participant.
  Completing a task removes that pending work, preserving missed-call history.
- Filter directories contain only employees/lines from permitted calls; SQL distinct
  avoids scanning a truncated page. List rows expose outcome and authorized due/
  overdue task counts, never restricted material titles or provider recording URLs.
- The journal sidebar and explicitly linked finished-conversation screen share the
  outcome UI. Unknown responses freeze/retry the same mutation. Conflict reload
  retains input and requires another deliberate save. Quiet journal refresh keeps
  player/component identity and does not pause playback or discard outcome input.
  Playback offers 0.75–2x and bounded +/-10s seeking; live calls still pause audio.

See [Stage 3 usage](./feats/telephony/stage3.md). Production, new channels and Stage 4
are separate work; none are enabled by this contract.

## Telephony Stage 1 — local call controls and audio, 2026-10-23

- `useTelephony().preferredIntegration` follows the enabled Twilio/Exotel/Exolve
  order, preferring the configured calling medium when it is enabled. Workspace
  and provider controls use the same choice. For Exolve, Dial a number opens the
  same app-level conversation as card/journal actions, without a second dialer.
  Legacy provider preparation and confirmation remain compatible.
- The unified recipient field searches `crm.api.telephony.search_customers`.
  Choosing a result fills the number and passes its explicit `{doctype,name}`
  into the existing permission-checked resolver; it never places a call. Editing
  the number invalidates old context. Versioned requests discard stale results.
  Ambiguous linked cards still require an explicit Lead/Deal choice.
- Minimize preserves the existing SIP client and conversation store. The compact
  panel shows customer/state/timer and supports mute, hangup, incoming answer/
  decline, audio unblocking and reopening the full workspace. SPA navigation
  does not discard the call or drafts. Stage 2 below adds private draft recovery;
  a media session is never resumed after a reload.
- Audio device preferences contain only input/output device IDs under the current
  user's browser key. SIP credentials, note/task content and sound are excluded.
  `createExolveClient({getAudioConstraints})` reads fresh microphone constraints
  for each call and incoming answer; the default remains `audio: true`.
- A selected microphone uses exact `deviceId`. The chosen speaker is applied to
  the actual call audio element before dial/answer, using feature-detected
  `setSinkId`; a routing failure blocks that action and is shown to the user.
  Browsers without output selection use system output and explain this in audio
  controls. Device changes apply before the next call, without replacing active
  tracks. A pending answer cannot answer a later incoming conversation.
- Audio controls are a view in the same Dialog, retaining conversation input.
  Enumerating devices does not request microphone access. Explicit microphone
  check uses a local Web Audio RMS meter, without recording or network output.
  Stop/back/close/device change/incoming call/unmount and the 20-second deadline
  release tracks, animation and AudioContext; a late permission result is stopped.
  Speaker check plays a short generated local WAV through the selected output;
  closing/changing devices ends playback and revokes its object URL.

Physical microphone/two-way speech/recording and delivered DTMF are separate live
acceptance checks, deferred by the user on 23 October. See
[Stage 1 instructions](./feats/telephony/stage1.md).

## In-call customer work — local contract, 2026-10-23

- `makeCall(number, context=null)` and `prepareCall(number='', context=null)`
  retain their string-number behavior. The optional context is `{doctype,name}`
  or explicit references; Lead/Deal cards, lists and Contact actions pass it.
  Exolve resolves it under current permissions. Multiple candidate deals require
  selection; changing a prepared number invalidates its context. Legacy providers
  retain their existing call behavior and ignore this extra parameter.
- `crm.api.call_work.resolve_context`, `search_contexts`, `options`, `get_item`
  read local data only. Supported save targets are CRM Lead / CRM Deal. Contact
  resolution uses explicit Dynamic Links / CRM Contacts, never phone matching.
- `save_note` and `save_task` take `values`, `mutation_id`, `expected_viewer`,
  optional `name` and `expected_modified`. Values include an explicit
  `context_kind`/`context_name`. Notes use plain `title`/`text`; tasks use the native
  title/description/assignee/date/status/priority fields, with plain description
  escaped on the server. Both create ordinary native records with CRM references.
  Workspace edits are restricted to the author's records and cannot retarget them.
  When explicit candidates exist, search for another customer is collapsed until
  requested; a number with no candidates shows the search immediately.
  The note title is optional to display and remains editable through its pencil
  action. New tasks show title/deadline first; description/assignee/priority/status
  are under Task details. Confirmed clean task saves collapse to a summary; Edit
  task opens the same record. Unknown outcomes and later edits keep the editor open.
  Previous conversations are available through the history action while inactive.
- Note retry receipts use the private CRM Note Operation table, with no client
  CRUD, storing user/request hash/note ID only. Task saves reuse the existing CRM
  Task Operation service and native assignment hooks. User/context/record checks,
  transaction retry and `modified` comparison apply on writes and replays.
  An unknown outcome retries the same operation ID and frozen payload; later text
  stays unsaved until a subsequent operation. Conflicts preserve the draft.
- Native record/list hooks apply customer access checks to operation-managed
  notes/tasks too. Records without receipts and Frappe's explicit document-sharing
  semantics keep their prior behavior. Workspace APIs always recheck the target.
- The app-level store holds separate work items per conversation after hangup and
  SPA navigation. Stage 2 persists private drafts on the server; it never stores
  customer text in localStorage. Saved/pending work fixes the target context.
  Beforeunload warns for active calls or unacknowledged drafts. Browser call
  states remain untrusted UI metadata; provider history is not fabricated.

## Telephony Stage 2 — private recovery and server history, 2026-10-23

- Private service-managed DocTypes `CRM Call Work` and `CRM Exolve History Sync`
  have no ordinary CRUD permissions. Controllers restrict writes/deletes to an
  internal context. Draft RPCs always bind the enabled authenticated user and
  require native call creation permission; manager roles cannot request another
  user's draft. Saved items also recheck native author and customer permissions.
  Unreadable/deleted customer drafts remain stored but are omitted from recovery.
- `call_drafts.save_draft(snapshot, expected_revision, mutation_id, expected_viewer)`
  stores a bounded, validated private conversation snapshot without creating a
  Note/Task. User/work UUID identifies the row; revision CAS and the frozen last
  mutation/hash make unknown outcomes replayable and reject conflicting payloads.
  There are at most 30 tasks, 100k note text and a 1.2MB snapshot. Started attempt
  number/direction and saved/pending context cannot be silently changed.
- `list_drafts(offset)` pages 30 personal entries; `get_draft(work_id|call_log)`
  rechecks access, returns a current context and canonical saved-record versions.
  Recovery refreshes clean records while retaining personal edits/conflicts and
  exact pending native mutation IDs. UI autosave is debounced and serial per work.
  Native Save waits until its frozen request is durable, then uses the existing
  canonical Note/Task APIs. A draft acknowledgement is distinct from Saved in CRM.
- Unknown autosave outcomes retry the exact snapshot and UUID before later edits.
  Two-tab CAS conflicts stop overwrites. Loading the server's version first saves
  the local version as a separate private draft; Restore switches to that copy.
  This cannot silently move text to another tab's customer or discard it on reload.
  Restoring a prior incoming attempt never reuses it for a later incoming call.
- `call_candidates(work_id)` reads up to 50 accessible Exolve calls for the same
  number/current participant and attempt direction; it never chooses a result.
  `link_call(work_id, call_log, expected_revision, expected_viewer)` requires an
  explicit selection, participant/read permission, matching number/direction,
  author/customer access and an exclusive call/conversation association. It adds
  Dynamic Links to existing native Note/Task IDs under transaction locks. Later
  confirmed saves add the same IDs to that call; no native record is copied.
  No SIP/provider correlation is inferred from phone, clock, duration or a browser
  supplied disposition. Call detail can open the current user's linked materials.
- Exolve settings add opt-in `history_enabled` and optional `history_start` (site
  date; default initial recovery is 30 days). `history.run` is registered at one
  minute intervals but requires both calling and history enabled. A site/account
  lock, fixed page windows, stored offsets and per-page commits permit bounded
  recovery after a closed CRM or failed process. Recent two-day overlapping scans
  and repeated daily historical sweeps recover delayed data and recording readiness.
  Failure preserves the last committed cursor and retries with 1–60 minute backoff.
- Each row is normalized against the authenticated application and exact SIP,
  with terminal provider facts and stable application/call identity. Existing
  imported call participants, owner, caller line and relationships are retained
  when the SIP mapping changes; existing start/end timestamps are immutable even
  after a site timezone change. The foreground user's RPC cannot take over those
  calls. Existing ready recording URLs are never erased by a late empty snapshot.
  History requests perform reads only and never change routes, send messages,
  start calls or enqueue paid analysis. The credentials remain server-only.
- `history.status()` exposes the current mapped user's local progress/error only.
  Workspace refresh polls local APIs while visible. Recording state is ready,
  pending or unavailable based on provider flags, with a separate client loading
  error/retry state; a download error never means that a recording is absent.
  The authenticated recording proxy, source files and byte-range behavior remain.

Local runtime: `/Users/g-karim/frappe/crm-exolve-20261022` runs only this job in
`config/run_exolve_history.py`, maintained by `config/start_demo.py`. The shared
scheduler stays paused and emails muted. Additive schema and history opt-in were
applied only to `crm-exolve.localhost`. See [Stage 2](./feats/telephony/stage2.md).

## CRM tasks exposed in Celio — local contract, 2026-10-19

`crm.api.celio_tasks` owns optional Celio task operations. It reads/updates the
same CRM Task through the native controller, including ToDo and notification
hooks. There is no mirrored ERP Task, execution handoff or project capability
added to CRM tasks. Personal My Work scope uses assigned_to=current user.

Read/search/count/update require current CRM Task permission and read access to
its linked context. Creation offers permitted Lead/Deal contexts; a new assignee
must be enabled and able to read both CRM Task and its context. Celio membership
or notification subscription does not grant CRM roles or private customer access.

`save_task(values, mutation_id, name=None, expected_modified=None,
expected_viewer=None)` accepts only title/description/due_date/priority/assigned_to/
status, plus context_kind/context_name on create. Updates require the exact saved
modified revision. Unknown HTTP outcomes reuse the exact operation ID and values;
CRM Task Operation stores user/task/request hash only and has no ordinary CRUD.
Replays recheck current source access and return the present permitted task.
Native assignment changes may update modified after insertion; the response reloads
that saved revision. Clearing an assignee also cancels its previous native ToDo.

Concurrent source saves serialize on the authenticated User row until commit.
Only the two top-level CRM/Celio save POST RPCs retry a whole failed transaction,
up to three attempts for database deadlocks/timeouts. A retry clears cached actor
permissions and rechecks current access. Embedded server calls leave rollback
and retry to their own caller. No explicit commit or new schema is introduced.
Both forms retain the immutable operation after transient/unknown server errors;
definitive input/access/version rejection permits correction or explicit reload.

`get_task`, `options`, `search_contexts` and `search_people` are source-owned;
Celio delegates to them. Current permissions filter before list/count/pagination
and export. Native statuses stay native, with display-only state groups. Minimal
recipient-scoped realtime invalidation contains no task text; focus/poll/refetch
preserves local drafts. CRM Task notifications remain CRM source regardless of
which app saved the task. Nothing is automatically copied into Celio projects.

## Shared EXP Notifications — local contract, 2026-10-19

This contract is implemented locally and has no production release. The server
service belongs to `exp_theme.notifications`; CRM and One remain independently
installable. CRM registers `crm.notification_source.make_source` through the
`exp_notification_sources` hook. No personal notification or read-state copy is
stored in Theme or One.

- An installed older EXP Theme without the shared notification schema is treated
  as an unavailable optional service. Native CRM notification creation/updates
  still work; installing the visual theme does not enable shared delivery.
- `CRM Notification` remains the canonical record. The adapter checks the
  recipient, enabled account, current Lead/Deal permission and current linked
  CRM Task/parent permission before every list, count, read, open and delivery.
  The native API applies these checks to ordinary notices as well as Messenger.
  Generic notification writes by ordinary recipients are denied; read actions
  use the authorized native endpoints.
- Native `get_notifications()` additionally returns `viewer`, per-row `head`
  and safe internal `path`, and a 15-minute `snapshot_token` covering all visible
  unread rows. Existing fields remain. Counts retain Messenger `event_count`
  weighting, including in Home.
- `mark_as_read(notification, observed_head=None, expected_viewer=None)` rejects
  stale heads. Messenger requires an observed head; the existing conversation
  endpoint still requires the exact loaded `last_event_id`. Both paths retain
  native read state, clear the read aggregate's `aggregation_key` and leave the
  conversation unread count and task status unchanged.
- `mark_all_as_read(limit=500, snapshot_token=None, cursor=0,
  expected_viewer=None)` returns the same token, next cursor and `has_more`.
  The updated client reuses one snapshot. New rows and aggregates whose head
  changed since the snapshot stay unread. A snapshot cannot be used by another
  account. Old callers omitting a token get a fresh bounded snapshot per call;
  they must upgrade to the new protocol for the multi-page guarantee.
- New assignment identity is `crm-assignment:<ToDo.name>:assigned|removed`.
  The native notification name is an atomic unique hash of event and recipient.
  Replaying the same ToDo event does not create a second CRM notice or delivery;
  a later new ToDo assignment has a different identity. No historical rows are
  renamed or guessed by title/time.
- The current One delivery category is **new CRM Task assignments**. Lead/Deal
  assignment history and other accessible native notices appear in Home, but
  no new One delivery categories are silently enabled. Removal notifications
  are not delivered as new assignments. Native Notification Log shadows are
  excluded from the generic platform projection.
- `crm.api.application_notifications.get_settings()` and `save_settings(...)`
  delegate to the one common subscription for `source=crm`. Save accepts enabled,
  sender, push route, expected revision, mutation ID and expected viewer. It
  never accepts a recipient, arbitrary channel, source, DocType or code. Unknown
  HTTP outcomes retain the exact mutation for retry; a stale draft requires reload.
  Home and One display this same record. No CRM mirror preference is introduced.
- One is optional. Its disabled/unavailable delivery does not remove native
  CRM history, source panel or other channel preferences. Native read state is
  independent of chat reads and task completion. Connecting does not backfill.

CRM user settings include **Notification delivery**. The direct route
`/crm/notification-settings` is also reachable from mobile Notifications. Native
read counters/settings refresh on recipient realtime, user-scoped BroadcastChannel,
focus/visibility and a visible-page 15-second poll. RU/EN labels use the existing
CRM translation mechanism. No sender administration is exposed to ordinary users.

The adapter's generic notification-list scan and real device/PWA delivery have
not been load/device certified. Existing backend retention of Messenger notices
is unchanged; this integration adds no historical cleanup or preference migration.

Home's accepted local design adds an optional text-only `presentation` to the
adapter's authorized rows: actor display name, current task title/description/status
and the permitted parent title. Task/parent field-level read and mask permissions
apply before projection. Background calls for a different session user omit these
additional private display fields. No task, notification, subscription or read-state
copy is created. Home's new GET preview rechecks the existing adapter access/head
without marking the source read. Native CRM endpoints and frontend are unchanged.

## Exolve browser calling — local pilot contract

`crm.integrations.exolve.api` exposes manager-only `get_settings`, `save_settings`
and `test_connection`, and current-mapped-user POST `get_sip_credentials` and
`sync_calls`. API keys are never returned. SIP credentials are no-store and never
persisted by the browser transport. Settings map enabled users to unique provider
SIP resource IDs; the browser cannot choose another user's account.

The additive `CRM Exolve Settings` Singleton owns the Password API key and child
`CRM Exolve Agent` mappings. `Exolve` is appended to the existing Telephony Agent
default and Call Log medium choices. The call schema adds immutable provider
application/call IDs. Existing provider identifiers and history remain unchanged.

The first client connects on explicit user action and uses a memory-only JsSIP
transport. A card click fills the dialer; Call starts the actual call. The idle
header has no Exolve launcher; a dismissed active call exposes a compact call
panel at the bottom right, while the client stays mounted across navigation. Server Call
Logs come only from authenticated terminal provider statistics for that SIP.
Reconciliation is limited to 15 minutes/100 rows, deduplicates across transactions,
retains ready recordings and has one whole-transaction snapshot-conflict retry.
Import does not trigger paid AI or register a Touch Tracking adapter. Recordings
are fetched by validated identity from the fixed provider endpoint; credentials
are dropped before CDN redirects. The Exolve browser route prepares a private
PCM WAV preview using server ffmpeg, retaining source rate/channels. Current
access is checked on cache hits as well as initial fetch; previews have 0600
permissions, bounded conversion, and normal conditional/range responses.
SIP offers may finish gathering on a public or relay candidate rather than
waiting for every interface timeout. Full contract and limits:
[Exolve](./feats/telephony/exolve.md).

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
