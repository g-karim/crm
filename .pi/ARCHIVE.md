# CRM — Completed Work Archive

## Home aligned with Celio Signal — local, 2026-10-25

At the user's request, reused Celio's existing Signal palette and typography for
Home overview, notifications, modules, correspondence and existing task/AI surfaces.
Replaced the blue-grey chrome with warm neutral backgrounds, olive navigation and
the established orange accent. Main heading is 24 px/600; Inter uses the bundled
Frappe font, without editing Frappe or Celio. One subtle border per surface, quiet
shadows, a 1 px overview top separator and no double mail-selection outline.
Light/dark unread text and its black-dot indicator remain distinguishable.

Chrome checked six views, 375/667/768/1024/1440 widths, both mail themes, reply
focus, compact navigation/reload/profile menu, keyboard focus and unread-state
text contrast. The unread CSS case uses a DOM-only fixture because this mailbox
is currently read; no message state was changed to create test data. No JS/HTTP
errors or send requests. SHA comparison preserves all rows in 14 mail/business
DocTypes. Existing services remain running; generic scheduler/mail remain muted.
Private evidence: `evidence/home-celio-style-20261025` in the isolated bench.
Only local CSS and the asset version changed; no production access/deploy or
business/backend changes. Existing dirty work and original CRM assets retained.

## Complete personal mailbox history and external recipients — local, 2026-10-24

At the user's explicit request, imported all 79 provider messages from five folders:
70 INBOX, 8 Sent, 1 Drafts, empty Junk/Trash. Existing two received self-tests reused;
76 Communication records and one editable private Home draft added. All dates,
MIME digests and 23 attachment payloads verified against read-only provider fetches.
Initial read/star/folder state stays personal; all original provider flags preserved.
Folder-scoped cursors and service-only provenance make repeated import a no-op.
The existing isolated worker now receives new mail from all five configured folders.

Removed the self-recipient restriction only for the configured employee/account,
using explicit local admin config. Native Home receipts, current source permissions,
exact sender and Communication/envelope recipient equality still gate SMTP. To/CC/
BCC may be external; generic queues/scheduler remain muted. No extra live test mail
was sent. Provider drafts never enter the queue automatically.

Validation: 81 native tests; completeness/dates/attachment hashes, unchanged old
records/files/accounts/assignments/native queue and repeat import verified locally.
Chrome covers imported incoming/sent/draft, the absent self-recipient hint, active
outgoing permission and mobile. Private evidence: `evidence/home-mail-history-20261024`.
No production access, provider mutations, paid AI, commits, pushes or deployment.

## Live personal Beget mailbox — isolated acceptance, 2026-10-24

The user supplied the mailbox password and authorized reading SMTP settings from
production. Read-only SQL on the currently running production bench at
200.169.176.193 confirmed smtp.beget.com:465 with SSL (the existing notification
account; no personal account/password was exported). Official Beget IMAP settings
and both actual TLS authentications were verified. Configured only the local
g.karim@exp-verse.com account, preserving User Email assignments/global defaults;
the secret is in native encrypted password storage, never source/evidence/logs.

Generic scheduler and mail remain muted. An explicit site policy enables only
this account/user and self-recipient. Native Home send receipts authorize a bounded
queue worker; other native queues, recipients or revoked account access are skipped.
Native queue suspension and retries are retained. Receiving uses read-only INBOX,
BODY.PEEK and an internal UID cursor beginning after the existing 68 letters.
No provider flags, old messages, auto-replies or participant forwarding are changed.
The existing isolated inbox process runs the pilot; no general jobs were enabled.

Two actual self-addressed UI submissions were accepted by SMTP and received by IMAP.
The first exposed native text-MIME newline normalization. Text files now use binary
MIME, preserving original encoding/newlines. The second round trip proves TXT/PDF/
PNG attachment hashes, native queue completion, one incoming copy, ZIP download,
protected PDF preview and readable desktop/mobile Home rendering. Native email
layout wrappers are flattened without discarding authored tables; exact letters
open at the start. Original raw HTML remains unchanged.

Validation: 72 native tests, actual TLS/SMTP/IMAP and Chrome with no JS errors.
Evidence is `evidence/home-mail-live-20261024` in the isolated bench. All old business
records, native files and CRM internal-note data are preserved. Only the selected
local account, encrypted credential, explicit pilot config and own mail/cursor
metadata changed; the four new native mails and twelve private file records are
the two retained round trips. No production writes/restarts/deploys, paid AI,
commits or pushes. External-recipient use, initial history and IMAP flag sync remain
outside this acceptance.

## Everyday Home mail client — local implementation, 2026-10-24

Added mailbox-scoped address suggestions and recipient chips; keyboard selection,
validation and pending-address draft persistence; native rich-text writing, safe
links, attachment-backed inline images and personal signature management. The
canonical signature is User.email_signature with revision/content-stamp checking.
Attachments show sizes and protected PDF/image previews, support drag/drop,
upload progress/cancel/retry and ZIP download. Cancelled queued uploads are skipped.

Added page selection, atomic revisioned bulk read/archive/spam/trash actions,
previous/next navigation and sender/recipient/date/unread/attachment search.
The indexed exact-letter path selects only a page's headers and point-reads the
body. On a rollback-only 5001-letter mailbox, first/deep pages projected 31 headers
and returned 30 in 51/58 ms; a text-filtered page took 408 ms. This is a local pilot
measurement, not a provider or production performance guarantee.

Native queue status/error/retry DTOs never invent delivery or expose traceback/
credentials. Retry preserves already sent recipients. Original bytes are passed
to native MIME, avoiding generic File text decoding for small binary uploads,
native attachment copies and downloads. Shared Frappe sources are unchanged.

Validation: 61 native tests; Chrome exercises real protected preview/ZIP/upload,
rich writing/link/signature insertion, bulk/search/navigation, two independent
browser-storage contexts and explicit draft-conflict resolution. Light/dark and
1440/1024/375/667 layouts pass; the mobile composer no longer scrolls sideways.
Real uploads show progress; a cancelled queued file is never uploaded, and one
injected connection reset is recoverable through the native upload endpoint.
Loopback TCP SMTP accepts native MIME, rejects the second recipient once, then
receives only that recipient on idempotent retry. PDF/image bytes and inline CID
are preserved; native receiving deduplicates a captured incoming MIME message and
shows it in Home. No real provider or employee mailbox was contacted.

The user chose g.karim@exp-verse.com for live verification; its local account has
no IMAP/SMTP hosts/password and both transports are disabled. A settings-file path
was requested. This remaining acceptance and external-client IMAP flags are not
claimed complete. Evidence: `evidence/home-mail-client-20261024` in the isolated
bench. Production was untouched, generic scheduler/mail remain paused, no paid AI,
commits or pushes. Existing dirty work and native business records are preserved.
The final audit verifies all original business rows/fields, CRM internal notes,
14 native file blobs, all 5527 previous CRM assets, site-config bytes and the
existing two AI analyses/cost. Only own Home metadata and two own-address examples
with six native private file records were added. Transient transport contacts and
upload fixtures were removed with native deletion audit retained.

## Home mail actions — local implementation, 2026-10-24

Implemented safe clickable links in the default readable body, contextual Reply /
Reply All, always visible reply recipient summary, Forward with native private
attachments, Archive with return to Inbox, personal Trash with restore, and
revisioned draft deletion. Forward prepares a separate compose with blank To/CC/BCC,
quote/Fwd subject, source access marker and no inherited CRM reference/in_reply_to.
It preserves edited drafts on request retry and uses native sender/idempotent send.
HTML allows formatting and HTTP(S)/simple mailto links while stripping all scripts,
styles, tracking content and other URL schemes; source HTML remains unchanged.

Trash is excluded from all normal folders/counts. Restore preserves prior archive,
spam, favorite and draft state. Both native Spam/Trash defaults remain reversible
inside Home without provider writes. Draft clearing retains a revision marker:
concurrent stale saves/sends/deletes fail and stale browser caches do not resurrect
text after reload. The same marker is used after send. Exact-letter conflict
resolution and fast typing in the next compose after send were corrected; pending
unsaved edits no longer display a misleading saved status.

On phones an open letter gets the viewport; Back restores folders/navigation.
Validation: 40 native tests pass; real Chrome accepts links, recipient modes,
forward/send/download with a private file, archive/restore, trash/restore and
native two-window discard/reload. Layout checks prove reply and send controls fit
1440/1024/375/667 viewports with no horizontal overflow or JS errors; dark theme
was visually inspected. Before-state and evidence: `evidence/home-mail-actions-20261024`.
Added only one own-address incoming example, one file and one local-only sent
forward. Previous native records/config/assets are preserved. Production was not
accessed; transport remains muted, scheduler paused, no new paid AI or deployment.

## Home mail folders and own-address examples — local update, 2026-10-24

Reworked the workspace around individual letters instead of mixed incoming/
outgoing chains. Inbox is the default, followed by Favorites, Sent, Drafts, Spam,
All. The employee's own assigned mailbox is selected first. Incoming unread,
incoming read and outgoing letters have distinct fills, with a black unread dot
in every folder and explicit outgoing recipient/direction labels. Favorite stars,
personal spam/restore and mark-unread use source-checked revisioned metadata.
Exact-letter drafts/attachments and reply IDs preserve neighboring replies;
legacy thread API and internal CRM notes remain intact. Same-window metadata
writes serialize, while concurrent-window revisions still reject stale writes.

Removed preview banners and test-button wording without fabricating delivery
states. Added one disabled own-address mailbox, eight native received/sent
examples, a private draft and attachment for g.karim@exp-verse.com. Browser
acceptance adds one native local-only reply. A private admin marker, mute_emails
and disabled transports constrain this sample path. Native Email Account setup
resaved one previous mailbox assignment: its original fields were restored and
only this task's duplicate new assignment was undone. Previous mail/business
records, account settings and audit examples remain preserved.

Validation: all 29 Home native tests pass; Chrome accepts all folders, individual
reading, unread dot, three colors, favorites, spam/restore, own-address sender/
recipient, draft and native reply, four widths and dark mode with no JS errors.
Scoped Ruff F/format, JavaScript syntax and app diff checks pass. Evidence is in
`evidence/home-mail-folders-20261024` of the isolated bench. No production access,
provider send, paid AI, commits or pushes; scheduler and real mail stay paused.

## Home correspondence readability — local UI update, 2026-10-24

User-requested contrast and space revision keeps native data/permission APIs.
Stronger light surfaces, selected conversation fill and borders distinguish the
list, history, inputs and paper. Body text is 16px; the compact header and default
closed reply form increase the 1440×900 reading pane from 160px to 544px high.
The sidebar collapses to a 68px icon rail with a smaller logo, accessible labels,
reachable profile menu and per-user browser persistence. Mail content uses all
available width; replies keep recipients/subject behind an explicit control.
New mail and existing nonempty drafts open the composer. Collapse retains text;
reply all, quote and revision conflict reveal the form when needed.

Chrome acceptance covers persisted navigation/profile, actual reply draft
collapse/reload, To/CC, new compose reload, both themes, six viewport widths
375–1512px and existing Home/notifications. No JS errors or horizontal overflow.
Measured light text/metadata/primary-button contrast is 15.7/7.3/6.1:1.
JavaScript syntax and app diff checks pass. UI source snapshot, before/after
screenshots and acceptance report live in `evidence/home-correspondence-ui-20261024`
of the local bench. Backend/data schema and providers are unchanged; no real
messages, calls, paid AI, production access, commits or pushes.

## Home personal correspondence — local implementation, 2026-10-24

Implemented `/home?view=correspondence` for any enabled System User, including
production employees without CRM or Sales roles. Assigned native `User Email`
mailboxes appear automatically. Additional channels can only be selected from
already configured mailboxes/channels with existing access; selection never
creates a provider account or grants permissions. Provider setup stays with the
administrator. The existing Home overview and separate notifications remain.

Native Communication and Messenger history remain the sources of truth. Mail
read/reply/new compose, To/CC/BCC, reply all, quotes, private attachments, account
filters, unread/sent/draft views and native cursor pagination work in Home.
Configured Messenger channels use native conversation permissions and text
replies; media sending remains in the native channel panel. Owning a mailbox
does not expose linked CRM records: customer context requires separate native
read permission. No global administrator sweep of private mailboxes.

Private read cursors are shared with CRM where installed. Home drafts use a
separate field and preserve internal CRM notes; independent fallback storage
supports mail-only sites. Revisions, account/viewer binding and operation
receipts protect draft conflicts and sending retries. Stale empty browser
drafts cannot overwrite another window's newer text. Email HTML is sanitized
and sandboxed without remote trackers. Native timestamps convert from the
system zone through UTC to the viewer zone.

The pilot retains two disabled invalid-address mailboxes, a production staff
profile, three incoming sample letters and private attachments. Native mail
hooks created five sample correspondent Contacts; only these new fixture
contacts are added. Browser replies/new mail are local examples, with no real
SMTP or provider calls. Original business rows and every original field remain
unchanged, including native messages and account settings. Site configuration
bytes, 5527 original CRM asset files, two recording previews and both prior
paid analysis records/cost are preserved. Backups exist; no restore rehearsal
is claimed. The maintained Theme checkout was only read and copied into the
isolated pilot, where this implementation lives.

Validation: 709 frontend unit tests and 158 combined native tests, followed by
a focused rerun of all 22 Home tests after final compatibility guards. Real
local browser acceptance covers production staff without CRM roles, mail and
configured channel selection, CC/private uploads/downloads, new mail without a
CRM record, reload and two-window conflicts, empty-stale draft preservation,
time zones, button contrast, four viewport widths and dark mode; no JavaScript
errors. Scoped Python F checks, JavaScript syntax and all app diff checks pass.
General scheduler/jobs remain paused, real mail muted. Only the dedicated local
inbox process was restarted to include explicit Home message delivery.

Usage and boundaries: `../../exp_theme/docs/home-correspondence-2026-10-24.md`.
Private acceptance evidence: `evidence/home-correspondence-20261024` in the
isolated bench. No production access, real outbound messages, calls, new paid
AI, commits or pushes. Live IMAP/SMTP/channel acceptance and release remain
future work in PLAN.

## Messenger workspace — local implementation, 2026-10-24

Completed the four-part implementation plan for `/crm/messenger`: unified inbox
and queues; source-native replies and email threads; CRM customer context with
canonical notes/tasks; shared handling, account permissions and responsive UI.
The plan and usage are in [Messenger](./feats/communications/messenger.md), stable
contracts in SPEC. Original Lead messaging is retained; Lead and Deal both open
the shared inbox with an exact customer reference filter.

Messenger Conversation/Message and Communication remain the sources of history.
Email grouping uses native reply identities, with account/customer boundaries.
Private drafts/read cursors and shared assignment/status/context have separate
service-only storage, optimistic revisions and explicit conflict resolution.
Source/account/customer permissions apply before search/counts, native history
access, delivery and attachment download. Draft uploads remain private until
send. All UI writes bind the expected viewer; switching accounts cannot save
another user's captured draft or action. Email HTML is sanitized, inert and
sandboxed without remote trackers. No fake typing/provider-delivery state.

Local examples use two isolated demo Leads, one Deal, two Messenger conversations
and two email threads, with private attachment samples. Browser acceptance saves
real native notes/tasks only in that demo Deal and local-only replies in those
sources. Working channel/email accounts are not configured. Real email stays
muted; general scheduler/jobs remain paused. A dedicated local process processes
only explicitly submitted `crm-inbox-` messages through native delivery and
rechecks their author; it does not consume the legacy general queue.

Validation: 709 frontend tests, 28 native inbox tests and 108 telephony/Exolve
regressions; scoped Ruff/ESLint/Prettier, production build and diff checks.
Browser checks cover native note/task context, source replies and CC, draft
reload and two-window conflicts, assignment/close/reopen/snooze, native Lead/Deal
links and settings, five viewport sizes and dark mode. Every original business
row/field, 5527 original hashed assets and two recording previews is preserved.
Existing AI credentials/configuration and two paid analysis records/cost remain
unchanged. Backups and acceptance: `evidence/messenger-workspace-20261023` in the
isolated bench. No production access, real outbound messages, calls, new paid AI,
commits or pushes. Live-channel acceptance and release remain separate work.

## CRM AI connected locally from existing production key, 2026-10-23

User explicitly authorized reading the CRM call-analysis key from production and
using it on the local Exolve pilot. The currently serving bench was verified on
200.169.176.193 through nginx roots, at
/home/frappe/deployments/exp-unified-prod-20261023/production-bench. The exact
crm_call_analysis_api_key was transported in-process over SSH into the local
site configuration, mode 0600, without printing or committing the secret.
Production config and provider key limits remained unchanged.

The existing inference key is shared and has no dedicated daily cap. Added explicit
server-side shared-key opt-in with local serialized reservations, current price and
bounded whole-request quotes, available credit/key checks and the existing
unknown-charge stop. Default dedicated-key behavior remains. The local site uses
$1/day and $0.25/run reserve. Native local HTTP proxy works without adding SOCKS
packages; generic queues/scheduler remain paused and emails muted.

An old Administrator recording was denied before paid I/O; recording permissions
are now checked before queue admission and reflected in the UI. Another own-caller
recording had the old default Lead type with no customer name. Journal, recording
and analysis reads now recognize that exact unlinked shape, while retaining stored
provider fields and all real customer/mapping/participant checks.

The existing 22.2s call completed real ASR and summary: 59 raw characters, 2 segments,
no suggested tasks, actual total USD 0.0024055. Browser acceptance verified real
result rendering, seek in original audio and the enabled shared-key budget UI.
All original fields of 12 calls, 9 deals, 14 leads, 6 tasks, 9 contacts, 6 notes and
30 ToDo remain unchanged; original recording preview preserved. No new calls/SMS,
production writes, user tasks or notes. Validation: 702 frontend and 147 backend
tests, build/lint/diff checks. Evidence: evidence/ai-connection-20261023.


## Telephony Stage 4 — local call insights and analytics, 2026-10-23

Implemented immutable raw ASR, bounded segment timestamps/seek on the existing
recording player, separate summary/agreements, transcript search and explicit
native CRM Task confirmation. Analysis versions retain original customer/source
identity and recheck their permissions after call relinking. A replaced recording
can receive a new version; old timestamps never seek the replacement. Legacy
results remain readable with explicit provenance limits. Manager notes, original
audio and provider call facts are preserved.

AI is opt-in and disabled by default. Service-only runs/control, daily admission
reservations, actual usage costs, explicit reconciliation and durable pre-request
intent replace the old automatic/unbudgeted path. Old queued worker entrypoints
cannot send audio. Each paid step checks current user/customer/call, key daily
limit and spending state. STT catalog price checks, actual duration/size limits,
bounded summary output and provider chat price caps constrain requests. Unknown
responses/costs hold reservations and suspend processing. Known summary errors
reuse raw ASR on explicit retry. Native author/call/run locking and task receipts
prevent a second task on a lost-response retry or a second edited confirmation.

The analytics view uses the journal's permission/filter query over all matching
server rows, with distinct authorized native task counts and manager outcomes.
Callback speed is explicitly scoped to manager-confirmed missed→outgoing attempts,
with readable coverage, rather than inferred phone/time or task completion.
Shared view tabs and filters remain visible; mobile header controls fit 375px.

Validation: 702 frontend tests in 64 files, 142 native backend tests, build,
scoped ESLint/Ruff and diff checks passed. Browser acceptance verified lazy
recording seek, transcript search, real native task creation after explicit
confirmation, committed lost-response retry, journal-equivalent counts, callback
proof and fresh mobile layouts with no JS errors. Stage 3 browser regression
passed on the same final build. Two synchronized native database processes proved
one remaining reserve admits only one call and concurrent requests for one call
return a single run. A real local ffprobe verified generated audio duration.

The isolated site now has its own AI queue worker; general jobs/scheduler remain
paused and email muted. Repeated native QA reached the paused general queue's
550-job admission threshold during fixture cleanup. Only this local site's
max_queued_jobs was raised to 5000; queued jobs were preserved, no generic worker
was enabled, exact owned cleanup was completed and regression rerun passed.
The key/password/SIP mapping and every other site configuration field were retained.

Final preservation audit: all original fields of 12 calls, 9 deals, 14 leads,
6 tasks, 9 contacts, 6 notes and 30 ToDo are identical to backup. All 4771 original
asset paths/hashes and the original recording preview were retained. QA fixtures
were removed. Source/database/config/files backups and candidate asset retention
are under evidence/telephony-stage4-20261023. Production was not accessed, and no
live calls/SMS/paid AI requests occurred. A separate AI key is absent on the pilot;
live AI quality/cost acceptance and the previously deferred physical-mic/DTMF test
remain explicit future checks in PLAN. Usage: [Stage 4](./feats/telephony/stage4.md).

## Telephony Stage 3 — local work queue and outcomes, 2026-10-23

Added manager outcomes independently of provider facts, atomic native callback
tasks, the Needs attention queue, employee/line/outcome filters and canonical
notes/tasks in the call sidebar. Callback tasks use the existing source task API,
assignment and operation receipts; exact retries create one task. Call and UUID
both participate in the task-operation identity. Review storage has no ordinary
role CRUD grants and uses the guarded internal-write controller.

Writes serialize author/call/review, recheck fresh call/customer permissions and
use revision CAS. Native task completion/cancellation checks the linked task's
permissions and modified value. Another open callback cannot be silently replaced.
Completed/canceled tasks and missed calls remain in history. Attention filters
authorized tasks before pagination and uses their assignee; call age never hides
due work. Restricted review context/materials are excluded independently of the
call. Private drafts are never exposed through the shared sidebar.

The same outcome block appears in an explicitly linked finished conversation.
Unlinked browser attempts retain the Stage 2 exact-call selection requirement.
Unknown responses retry frozen input; concurrent outcome changes require an
explicit reload/resave while retaining local input. Quiet journal refresh keeps
the player and form mounted, so playback/input are preserved. The player supports
0.75–2x playback and bounded +/-10 second seeking.

Validation: 699 frontend tests and 90 native backend tests, scoped ESLint/Ruff and
the frontend build passed. Browser scenarios used actual local CRM writes with
mocked SIP/media: explicit Deal choice, a committed save with lost response and
exact retry, native completion, retained missed-call history, two-tab outcome CAS,
future/overdue callbacks on old calls, user/site deadline roundtrips, canonical
material customers distinct from the call primary reference, filters, speed/seek and uninterrupted
playback during refresh. Mobile acceptance uses a fresh 375px page load, matching
the app's existing initial-layout selection; resizing an already mounted desktop
page is not evidence of a native mobile layout. Stage 2 browser regression also
passed, including draft privacy, conflicts, exact links and recording states.

Full local source/database/config/files and old asset backups preceded the
single targeted DocType installation. Exact owned QA fixtures were removed;
preexisting business data, IDs, recordings and original asset paths were retained.
Production was not accessed; no live calls, SMS, AI, new incoming routes or Stage 4
work started. The shared scheduler remains paused. Evidence and runner:
`evidence/telephony-stage3-20261023/`, `config/check_telephony_stage3.py`.
Usage: [Stage 3](./feats/telephony/stage3.md).

## Telephony Stage 2 — local implementation, 2026-10-23

Implemented private server autosave/recovery, revision-conflict handling, explicit
call/material associations and bounded server-side Exolve history. Private tables
have no native CRUD grants and validate service-only writes. Recovery checks the
current customer and native item permissions, never another user's drafts. Native
Save persists its exact pending operation before creating/updating the original
CRM Note/Task. The server draft and the canonical CRM save have separate statuses.

Two tabs cannot silently overwrite the same private version. Before loading the
server's conflicting version, the local changes are made durable as another private
conversation, retaining their customer and native IDs. Restored conversations do
not reconnect media or get reused as a later incoming attempt. Clean canonical
records refresh on opening; unsaved text remains untouched.

Provider statistics expose a stable call ID but no accepted proof of equality with
the browser SIP dialog in this integration. Linking therefore requires explicit
selection of the exact accessible call; phone/time matching only narrows candidates.
Native Dynamic Links reference existing Note/Task IDs, including later saves.
A call belongs to at most one conversation; existing participants and customer
references are preserved. A default Lead DocType without a record name was found
to hide newly imported unlinked calls; new imports explicitly keep both empty.
Old calls are not retargeted by this fix.

The opt-in background importer checkpoints bounded date windows/pages, overlaps
recent history, repeats historical sweeps and backs off after errors. Browser
closure does not stop it. Existing historical participant/owner/line are retained
when the current SIP assignment differs, without opening recording access to the
new employee. Provider snapshots do not erase an available recording or start AI.
UI distinguishes preparation, availability, absence and playback failure/retry.

Validation: 689 frontend tests, 75 native backend tests, scoped ESLint/Ruff and a
local production frontend build passed. Browser acceptance exercised actual local
private autosaves and canonical writes, reload, another user, two-tab conflicts,
closed-CRM recovery of older calls, deduplication, explicit ambiguous selection,
existing native IDs, later attachments, recording states and mobile layout. SIP,
audio and provider statistics were mocked in these scenarios, with no real calls
or JavaScript errors. Exact owned fixtures were removed; audits were retained.
The preservation audit caught a three-hour shift of three earlier calls caused
by a changed local site timezone. Their original timestamps and modification
metadata were restored from the before snapshot; background refresh now preserves
existing timestamps and caller numbers. The regression test covers that shift.
The separate local history process also reads the actual configured Exolve account;
it recovered two previously missing calls, completed the 30-day backfill and
passed repeated synchronization without duplicates or errors. The final audit
verified all original business fields, 3,397 original asset files and the original
recording preview. One native modification timestamp from adding the new ready
recording state was retained; the audit does not conceal that legitimate update.
Its cursor/status and preservation checks are in the result evidence.

The local scheduler remains paused; only the dedicated history loop is running.
Full local DB/config/file and recording-preview backups precede the additive schema
installation. Production was not accessed. Physical-mic/DTMF acceptance remains
deferred by the user; stages 3–4 and SMS were not started. Runner and evidence:
bench `config/check_telephony_stage2.py`, `evidence/telephony-stage2-20261023/`.

## Telephony Stage 1 — local implementation, 2026-10-23

Exolve now uses one recipient/conversation screen from cards, journal and the
workspace header. Search and number entry sit directly in call controls; customer
search selection never dials. Existing explicit, permission-checked context
resolution and ambiguity handling are preserved. Legacy provider preparation is
retained using the same preferred-provider selection as the global call UI.

Minimize exposes customer, state, timer, mute and hangup in a compact panel;
incoming answer/decline and autoplay recovery are available there too. Reopening
and SPA navigation retain the SIP session, chosen card and note/task drafts.

Audio controls use a view of the same Dialog rather than stacked sibling dialogs:
the local native dialog implementation hid sibling modal content from accessibility
while it was visible. Input/output fields also receive explicit accessible labels.
Microphone/speaker device IDs are remembered per browser user. Exact microphone
constraints are read on each dial/answer; speaker routing is applied before the
call action and blocks it on failure. Unsupported output selection uses the system
output with an explanation. Live call tracks are not swapped mid-conversation.

Explicit audio checks use a local RMS meter and generated WAV; neither captures
a recording nor contacts a provider. Cleanup covers close/back, incoming call,
device change, unmount, denied/late permission and the twenty-second timeout.

Validation: 679 frontend tests, scoped ESLint, production frontend build (local
assets only), and browser acceptance with real local Note/Task writes and mocked
SIP/audio devices. Four synthetic outgoing calls plus an incoming fixture tested
compact answer/mute/hangup, selected constraints, unavailable output, actual local
meter and WAV playback, stale searches/contexts, retries, ambiguous customers,
mobile/landscape/large text and drafts across navigation. No browser JS errors,
provider connections or real calls. Owned fixtures were removed; existing business
rows and old asset paths were preserved. Runner: bench
`config/check_telephony_stage1.py`; evidence: `evidence/telephony-stage1-20261023/`.

Physical-mic two-way speech, recording and delivered DTMF remain live acceptance,
deferred by the user on 23 October. Production was not accessed; stages 2–4,
SMS, server drafts and automatic Call Log correlation were not implemented here.

## Conversation-focused local telephony interface, 2026-10-23

Replaced the vertical dialer/sidebar and large CRM form with one persistent call
control strip, compact customer context and parallel note/task areas. Call actions
stay above scrolling work on all widths. Desktop places the note in the main pane
and tasks in a narrower pane; mobile buttons switch between them without unmounting
or losing input. The primary action says Call customer; caller line and customer
number are distinct. Routine provider/balance explanations are removed.

Note titles remain automatic and editable through a pencil action. Task creation
shows title/deadline first and discloses description, assignee, priority and status
through Task details. Confirmed, clean saves collapse tasks to summaries; Edit task
updates the same canonical record. Drafts, conflicts, pending requests and later
typing keep the task editor open. Conversation history is an explicit action while
inactive. The DTMF keypad is a dismissible popover; timer ticks are excluded from
live status announcements. Context choice, native permissions and save contracts
are unchanged; no automatic customer choice or automatic persistence was added.

Validation: build, scoped ESLint, 671 frontend tests and browser acceptance passed.
Actual local HTTP writes exercised notes, several tasks, update of the same task,
optional note title, lost responses and concurrent retries; mocked SIP exercised
call controls, DTMF/Escape, navigation/hangup, mobile switching, landscape/large
text and delayed context resolution. No JavaScript errors, real calls or provider
connections. Owned fixtures were removed. Original business records, SIP settings
and older asset paths were preserved; production was not accessed.
Runner: bench `config/check_telephony_conversation.py`; evidence:
`evidence/telephony-conversation-20261023/`.

## Local telephony layout cleanup, 2026-10-23

Removed settings and connection-state actions from the Telephony workspace header;
List view and Dial a number remain. Removed the call dialog's manual history
refresh, reconciliation messages, Disconnect action and auto-connect explanation.
Automatic registration and post-call reconciliation remain active. The dialog and
all Russian UI wording now use Telephony instead of dialer; technical identifiers
and legacy translation keys remain compatible.

Expanded the customer-work dialog from 4xl to 7xl and to the available viewport
height. Desktop controls and customer work scroll independently; mobile call
controls remain above the editor. Explicit candidate cards are shown first, with
search for another card collapsed behind a button. Unknown callers still get
immediate search. No save, context ownership or provider contract changed.

Validation: production frontend build, scoped ESLint and all 671 frontend tests
passed. Browser acceptance verified actual native CRM saves with mocked SIP,
removed controls/terminology, viewport fit, independent scrolling, compact
candidate selection, mobile/large text/landscape, retries and draft retention.
Owned fixtures were removed and original business records preserved. No real
provider connection, call, message, backend migration or production access occurred.
Runner: bench `config/check_telephony_layout.py`; evidence:
`evidence/telephony-layout-20261023/`.

## Local in-call notes and tasks, 2026-10-23

Implemented the explicitly approved local slice from call-work-notes.md. Exolve's
persistent dialog now has call controls and a customer-work pane. Lead/Deal card
and list actions and Contact actions pass an explicit context through the existing
global helpers; old number-only calls remain compatible. Contact resolution uses
explicit links and permissions; multiple deals require selection. A manually
entered number begins without a target. Editing a prepared number invalidates
its context, and late resolver responses cannot restore it.

Notes are ordinary FCRM Note records; tasks are ordinary CRM Task records with
native assignment ToDo/notifications, deadline, priority and status. They save
immediately in the selected Lead/Deal, before provider history exists. Task writes
reuse the existing source-owned task operation service. Note writes use a new
private CRM Note Operation receipt table; only that additive DocType was installed
on the isolated local site. Receipts contain no note text and have no client CRUD.
Both writes recheck author/account, native record/context access, revision and
assignee permissions. Repeated unknown requests keep their exact operation ID and
payload; later input remains dirty. Conflicts keep drafts, permit loading the
current version and restoring the user's prior text for explicit reconciliation.
Native record/list permission hooks also check customer access for operation-managed
notes/tasks. Legacy records without receipts retain their existing access;
Frappe's explicit document-sharing semantics are unchanged. The call workspace
always requires access to the selected customer, including on retries.

Separate in-memory work items survive hangup, modal dismissal, SPA navigation and
selection of unrelated historical calls. Saved/pending work locks its target;
old drafts remain available when another conversation is prepared. The phone
layout keeps call controls above the scrolling editor. Drafts do not go into
localStorage; reload warns when unsaved work exists. Saved records are visible
through the normal customer activities and general Notes/Tasks. The customer
activity view refreshes on successful workspace saves.

Database/config/source backups and prior hashed frontend assets were preserved.
Validation: 671 frontend tests in 60 files; 60 backend tests (20 call-work,
10 telephony,25 Exolve,5 recording). Native fixtures were rolled back with commits
and external HTTP blocked. Browser acceptance uses actual CRM HTTP writes with
mocked SIP: Lead/Deal routing, several tasks, lost create/update responses, later
typing, concurrent HTTP create/replay, navigation/hangup, unknown numbers and a
Contact with two deals. Owned test records are removed afterward. Evidence and
the reproducible browser runner live in the dedicated bench under
`evidence/in-call-work-20261023/` and `config/check_in_call_work.py`.

Production, provider configuration and original call/recording data are unchanged.
No real calls or messages were sent. Automatic Call Log attachment is deferred
until SIP/provider correlation is verified; timestamp/phone matching is not used
as proof. Server drafts across reloads and physical microphone acceptance remain
separate stages. See [the user workflow](./feats/telephony/call-work-notes.md).

## Telephony connection and navigation refinement, 2026-10-23

The reported connection failure was a local user mismatch: SIP 247407 was mapped
to Administrator while the browser used karim. Reassigned that existing local
mapping to karim through the native settings controller; API key and provider
configuration were retained. Historical Call Log participants were not rewritten,
and historical recording access is not widened by the new mapping.

Added a local-only current-user readiness endpoint (available/reason), then
automatic app-level SIP registration for mapped users. No fallback to another
operator, credential persistence, microphone request or outgoing call is involved.
Manual Disconnect stores a user-specific browser opt-out; manual Connect clears
it. Navigation keeps the client; reload restores it. Native transport recovery
keeps tab ownership, and a second tab can retry after the owner closes. Settings
saves revalidate configuration. Missing mappings now have an actionable message
and a settings action for managers instead of a generic API-key error.

Changed the old journal entry from Table view to List view, removed the separate
recorded filter tab, and retained inline recording indicators and playback.
The backend recorded filter is retained for API compatibility.

Notes/tasks received read-only analysis only. The current helpers require an
existing Call Log and create a linked note/task without its own CRM reference;
Exolve's Call Log appears after the conversation. The proposed design preserves
explicit Lead/Deal context through dialing, saves canonical Note/Task records in
that context during the call, and attaches the same records to a validated call
later. SIP/provider-ID correlation remains unverified. See
[the proposed workflow](./feats/telephony/call-work-notes.md).

Validation: 662 frontend tests,40 backend tests, scoped ESLint and production
build. Browser checks use karim's separate native local session (no password reset
or clearing of existing sessions): auto-connect without a click or microphone,
navigation/reload, transport recovery, tab exclusion/recovery, persisted manual
pause/resume, precise unmapped state, mobile layout and actual Exolve SIP
registration. Zero real calls/messages or note/task writes. Evidence lives in
`evidence/telephony-refinement-20261023/` in the dedicated bench. Production and
the old shared source are unchanged.

## Local Telephony workspace, 2026-10-23

Added `/crm/telephony` over the existing CRM Call Log. The sidebar now opens this
workspace; legacy table routes, saved views, modal deep links and card calls are
preserved. A dated call list has normalized customer/phone search, period, own
calls and incoming/outgoing/missed/recorded filters. The adjacent pane shows a
recording player, call metadata, explicit CRM context and callback controls.
The dialer supports readable customer search and numeric entry. Old note/task
actions remain available through the native call-details modal.

The new read-only API applies native call and primary customer permissions in
SQL before paging/search, checks detail links again, and never returns provider
recording URLs. Deal contact names are resolved only through explicit links and
independent Contact read permissions. The recording proxy rechecks primary
customer permission before provider/cache access. No schema migration or data
rewrite was needed. Existing producer/recording/AI logic remains independent.

Workspace call preparation always opens controls first. Existing card behavior
is retained. Exolve/Twilio/Exotel publish non-secret UI activity state so record
players pause while a call is active, including in the legacy details/timeline.
The persistent app-level dialer survives navigation. Telephony alone keeps its
page instance across query-string selection, preserving filters and mobile pane
state; all other route keys retain their previous behavior.

Validation: 661 frontend tests in59 files;37 backend tests (10 workspace access/
filter/pagination/revocation/contact-privacy cases,22 Exolve,5 recording download),
scoped ESLint and production build. Native fixture writes were rolled back with
commits and provider requests blocked. Local browser checks exercised actual
search/filter responses, legacy deep links, real cached recording playback and
seeking, live-call playback exclusion and navigation with a mocked SIP session,
375px list/details/dialer/back, landscape and larger text. No JavaScript errors
or unexpected HTTP failures. No real calls, registrations or messages were sent.

Source/local diffs, old catalogs and all hashed frontend assets were preserved
before changes. Missing prior/intermediate hashes were restored after builds for
older tabs. Evidence: `/Users/g-karim/frappe/crm-exolve-20261022/evidence/telephony-workspace-20261023/`.
Production and the old shared source were not changed. Callback task queues,
line/team analytics, incoming routing, SMS and the unified Inbox remain future
work; installing this view does not improve provider-history completeness.

## EXP Theme installed and Russian labels restored locally, 2026-10-23

Read-only Git inspection on the user-designated production host confirmed clean,
detached EXP Theme `79dad3a7d4e870006719c7c72a7b980bbcd107e4`. Installed a separate
clean checkout of that commit in the isolated bench and its private Python env.
Neither the shared dirty theme checkout nor production was changed. No local
notification-service experiments were copied into this production theme version.

The normal theme setup would delete extra Language/Gender entries and rewrite
all user languages. The one-time installer substitutes only that setup function
with branding plus the system ru default, preserving all 82 languages, seven
Gender entries and all six users' language/theme settings. It still uses the
native installer for schema, hooks and translation registration. Full future
theme migration needs the same preservation review. SQL/public/private/config
and previous compiled catalogs were backed up before installation.

Loaded the theme's Russian translation map and compiled native Frappe/CRM ru MO
files inside this bench only. Browser labels now include «Журнал звонков»,
«Настройки пользователя», «Воронки продаж», «Иерархия продаж», «Шаблоны писем»
and «Политика SLA». Eight missing Web Forms list/dialog messages were added to
the local CRM ru PO and compiled; no frontend build was needed.

Detected and reproduced an optional-integration incompatibility: CRM's local
notification on_update hook imported the new shared-service module whenever
any exp_theme was installed. The production theme has no such module. The hook
now also requires the service's subscription schema, matching the settings API.
Four regression tests cover older/absent/ready themes and missing recipients;
four existing translation tests also pass. Native notification insert/save/read
state changes passed with commits blocked and a complete rollback.

Authenticated browser checks passed for the three main lists, both demo Lead
message tabs and pipeline/hierarchy/channel/form settings, plus theme asset URLs.
No JavaScript errors or failed local HTTP responses. All protected business,
credential and dictionary rows match before/after; scheduler/email remain off,
Messenger remains disabled and empty. Evidence and private backup:
`/Users/g-karim/frappe/crm-exolve-20261022/evidence/install-theme-20261023/`.
No real calls/messages, commits, pushes or production writes occurred.

## Messenger installed on the local test site, 2026-10-23

Installed the already downloaded `crm_messenger` at commit
`eb4af567072df2ba9dc0360561e42cab24aeea19` with the native Frappe app installer
on `crm-exolve.localhost` / `_crm_exolve_20261022` only. Registered the app in
this bench's `sites/apps.txt`; all nine DocTypes are present. No full-site
migration, frontend build, provider connection or production operation was needed.
Messaging and automatic Lead creation remain disabled; channels, conversations,
messages and webhook logs are empty. Scheduler remains paused, email muted.

Before installation, verified a full native SQL/public/private/config backup.
The demo HTTP listener was stopped and restarted using its verified owned PID;
other local benches were not restarted. Installer HTTP requests were blocked.
All original Lead, Deal, Contact, Dynamic Link, Call Log, Exolve Agent, Task,
ToDo, Notification, Email Queue, Exolve Settings and encrypted credential rows
match both immediately after installation and after browser acceptance.

Authenticated Chrome verified the installed-app API, safe settings API,
«Переписка» empty states on both demo Leads with sending unavailable, and
«Настройки» → «Каналы сообщений». No JavaScript errors or failed local HTTP
responses; no messages or calls sent. Screenshots, digests and private backup:
`/Users/g-karim/frappe/crm-exolve-20261022/evidence/install-messenger-20261023/`.
The unified Inbox remains a separate future feature. Production, source commits
and external accounts were not changed.

## Local CRM updated to production base, 2026-10-22

Read-only SSH to the user-provided `200.169.176.193` confirmed clean production
CRM `7dfa800f90fb7cf63cc08911d419fc5fb906f426` (codex/tatkardan-touch-stage7),
Messenger `eb4af567072df2ba9dc0360561e42cab24aeea19` and Frappe16.51.0
`6b450a166e076dd842e4db7ea0843f62881e62ac`. The pilot now uses a separate CRM
checkout inside `/Users/g-karim/frappe/crm-exolve-20261022/apps/crm`, based on that
exact production CRM commit, with local Exolve/task/notification changes applied.
The old shared `/Users/g-karim/projects/crm` and its dirty files remain unchanged.

Three-way conflicts retained the production Lead visibility/invalidation fixes,
fetch-from helpers and Touch Tracking hooks alongside local notification guards,
task callbacks, Exolve and translations. The old ignored migration guide that
collided with the production tracked guide is preserved in the evidence directory.
The production guide stays in the active checkout. Existing hashed assets remain
available to older browser tabs. No commit or push was made.

The pilot has its own Python environment. Editable imports no longer redirect
other benches; dependencies match the active app declarations (`uv pip check`
passes). FRAPPE_BENCH_ROOT is explicit for web/CLI resource isolation. The CRM ru
catalog is compiled only for this bench. Messenger source/package are present,
but no Messenger schema, channel or account was installed or enabled.

Before updating the local site, saved SQL/public/private files/configuration and
1,145 source-file hashes/archive plus the complete working diff. Full migration
ran only on crm-exolve.localhost with HTTP requests blocked and search indexing
skipped. Before/after comparisons matched all original business row values and
Exolve settings; Touch Tracking stays disabled and scheduler/email stay off.

Validation:654 frontend tests in58 files, frontend build and scoped ESLint;
35 backend Exolve/notification regressions plus5 recording-download tests passed.
A transactional real-permission probe verified visible owner notifications,
revoked Lead filtering in both native lists, frozen mark-all access checks and
reference-free realtime invalidation, committing no fixture rows. Browser
acceptance evidence is kept with the update report.

Evidence: `/Users/g-karim/frappe/crm-exolve-20261022/evidence/update-to-production-20261022/`.
Source/runtime rollback pointers are retained inside the bench. Physical-mic
conversation acceptance, incoming routing, SMS and new workspaces remain future
stages. Production was not modified and no real calls/messages were sent.


## Exolve — remove idle header launcher, 2026-10-22

Removed the permanent Exolve button from the shared app header. The dialer still
opens through card phone actions, fills the destination without calling, and
retains its mounted client. Dismissing an active call reveals a neutral floating
button at the bottom right; reopening it restores the call controls. It disappears
when the call ends. No provider credentials, routing or call transport changed.

Validation: 445 frontend tests in 42 files, frontend build and scoped ESLint.
Local authenticated browser checks passed for an absent idle header button,
opening from the seeded Lead, no automatic dialing, reopening a minimised call,
SPA navigation to Deals with the same call, hangup cleanup and a 390px viewport.
SIP/session were mocked: zero provider connections and zero real phone calls.
Existing hashed assets were preserved across the local build.

Competitor research and proposed Telephony/Inbox workspaces remain a design
proposal, not implemented CRM sections: [communications](./feats/communications/workspaces.md).
An illustrative HTML concept with theme/section switching lives on the isolated
demo under `/assets/communications-concept-20261022.html`.
Evidence: `/Users/g-karim/frappe/crm-exolve-20261022/evidence/communications-20261022/`.
Production, provider accounts, schema, commits and pushes were not changed.

## Exolve — real local call and recording acceptance, 2026-10-22

User explicitly authorized a real local CRM call to their confirmed personal
phone. One short first attempt was cancelled by the test harness too soon: ICE
gathering delayed the actual INVITE by roughly 40 seconds. An answered retry
used the real CRM UI, SIP/WebRTC and carrier with a known Russian WAV as its
browser microphone. The user confirmed hearing the phrase normally. Their
return speech was captured in the browser and in the provider's separate phone
channel (waveform correlation 0.903 after alignment). Speech recognition was
performed locally on cached MLX Whisper; no paid AI or external ASR was used.

The accepted call is Completed with 34.48 seconds talk time; the provider's
34.661-second original is 8kHz stereo Microsoft ADPCM WAV. Chrome could not
decode it. The Exolve-only recording route now creates a private PCM WAV preview,
preserving original rate/channels. It authenticates the participant/application
on every request, including cache hits, and serves actual byte ranges. Real
HTTP 200/206, metadata, playback and seeking passed. The native CRM modal shows
the recording without an error; original provider bytes remain separate.

The preview needs server ffmpeg, fixed WAV input/local-file protocol, bounded
source/output sizes and timeout; the cache is site-private with 0600 files.
The original download for future manual AI remains unchanged. SIP offers now
stop gathering once a public or relay candidate exists. A browser probe measured
0.479s preparation with all INVITEs blocked before transmission; cancellation
also cleared the UI. This probe did not place an additional phone call.

Physical Mac microphone capture independently returned live input and nonzero
levels. At the user's request, a real conversation through that physical input
is deferred. No further phone calls were placed after that request. DTMF delivery,
incoming routing and SMS remain future checks. No provider routes/services,
production, migrations of existing sites, commits or pushes changed.

Validation: 445 frontend tests/build/ESLint, 22 Exolve backend tests plus 5
recording regressions, Ruff and diff checks. Local evidence and launch helpers:
`/Users/g-karim/frappe/crm-exolve-20261022/evidence/real-call-20261022/`, `config/`.

## Exolve — first local browser dialer, 2026-10-22

Added a third calling provider, manager configuration and per-user SIP mappings,
explicit connection/call UI with incoming controls, mute/timer/DTMF, a memory-only
JsSIP transport, terminal provider-statistics Call Logs and protected recordings.
The published wrapper's localStorage password storage is not used. Concurrent
tabs cannot register the same SIP when Web Locks are available. Reconciliation
handles duplicate requests, late recordings and MariaDB 1020 snapshot retry.

Runs on a new Frappe16.51 site/DB at
`/Users/g-karim/frappe/crm-exolve-20261022`; existing Frappe17-dev and working local
sites were not migrated. The actual API key is encrypted in this site's settings.
No provider route/service changes, phone calls, SMS, AI requests, production,
commits or pushes are included. Real SIP registration/disconnection succeeded;
captured outbound SIP methods contained REGISTER and no INVITE. Two concurrent
DB imports returned the same single CRM row after snapshot retry.

Validation: 444 frontend tests in 42 files, production frontend build, 21 Exolve
backend tests and 5 recording regressions passed; changed-source ESLint/Ruff and
diff whitespace checks passed. Real Chrome checks cover settings save with key
retention, provider read access, registration/disconnection, second-tab exclusion
and the 390px dialer. Evidence and local launch instructions are in the isolated
bench's `README.md`, `config/` and `evidence/` directories.

Real audio/call/recording and incoming-route acceptance remain in PLAN. There is
no public webhook or background importer in this first slice. Contract:
[Exolve local pilot](./feats/telephony/exolve.md).

## CRM Task retry correction — local, 2026-10-19

The source serializes same-author saves before receipt lookup and retries up to
three complete top-level save RPC transactions on database snapshot/deadlock or
timeout conflicts. A retry clears actor permission caches; embedded calls outside
those RPCs leave transaction recovery to their caller. Both Celio and native CRM
retain the original mutation after transient/unknown responses. No schema change,
explicit commit, mirrored task, role grant or historical-data repair was added.

Validation:147 targeted backend,452 Celio and438 CRM frontend tests, both builds,
ESLint/Ruff/Frappe Semgrep; real2/4/8 HTTP creates, repeated edits, CAS/hash rejection,
lost responses and retained drafts. Real role revocation while waiting returns403
and creates no Task/receipt. Final full Celio871/871 in1120.125s with1240 backend
files unchanged. All work remains local and uncommitted; working data preserved.
Technical record: `/Users/g-karim/frappe/celio/bench-v16/apps/celio/docs/crm-task-retry-fix-2026-10-19.md`.

## CRM Task in Celio — local integration, 2026-10-19

A later explicit authorization adds one canonical CRM Task in both UIs. The source
API checks Task and customer context permissions, six agreed fields, eligible
assignee, current viewer, modified/CAS and durable exact-request replay. It uses
native save/ToDo/notification hooks, including correct assignment removal. There
are no ERP copies, role grants or automatic Celio project features. Customer
creation choices are permitted Lead/Deal. A private CRM Task Operation holds only
request identity/hash and source task reference.

Native CRM forms protect live input (including commit-on-blur fields) during
cross-tab reads. Agreed field saves use the source CAS/replay path; custom field
changes retain native behavior and scripting callbacks. Unknown outcomes keep the
same request and remain retryable after background reads. Old schema reads still
work; the new writer is unavailable until its own isolated schema is installed.
No existing working site was migrated.

Current local evidence: frontend433 tests/build/ESLint, native Task10, CRM shared
notifications14, Celio integration23, actual CRM UI→Celio→CRM, native draft/CAS,
lost-response creation/edit replay, RU/EN/mobile/themes. Full Celio repeat passed867/867 on a separate test database. Concurrent Theme
changes were followed by123/123 final coupled regressions with no source drift;
exact evidence and scope belong to Celio HANDOFF.
Frappe16.28/ERP16.29 compatibility was tested without upgrading the working bench.

Technical record: `/Users/g-karim/frappe/celio/bench-v16/apps/celio/docs/crm-work-and-shared-notifications-2026-10-19.md`.
Demonstration: `/Users/g-karim/frappe/celio-exp-integration-20261019`.
All dirty trees and fictional data preserved; no commit/push/deploy/PR/Wiki or
production connections, real mail/device push or paid AI.


## Shared EXP notifications — local CRM stage, 2026-10-19

Later authorized Home design stage: added optional display metadata to the shared
source adapter using the existing recipient/task/parent checks and native field-level
read/mask filtering. The shared GET preview has no write effects; source navigation
still uses the existing head-protected read path. Local shared-notification suite16/16
and real browser Home→CRM source navigation/read/task-status separation passed.
Native CRM frontend, saved preferences, historical identities and Celio are unchanged.
See `/Users/g-karim/projects/exp_theme/docs/notifications-live-design-2026-10-19.md`.

User authorized continuing CRM, EXP One and `/home` while another chat works on
Celio. This is a local implementation and acceptance stage, with no release,
commit, push, PR, production access, real email/device push or paid AI.

Implemented native CRM Notification adapter, current reference permission checks
for ordinary assignments as well as Messenger, shared weighted counts/read state,
head-protected reads and frozen bounded mark-all, atomic ToDo event identities,
optional durable One bot delivery and a CRM UI for the same common subscription.
Source panel remains CRM-only; One's own panel keeps its native events. No copied
task storage, copied read receipts or second CRM preference was introduced.

The original dirty PLAN/SPEC/ARCHIVE and edited source files were backed up before
changes. Original code and all prior hashed CRM build assets are preserved in the
private sandbox backup. Frappe's install-generated Desktop Icon export was also
preserved there, outside the change. Existing global/source channel settings and
historical notification IDs were not rewritten. Early One preferences/receipts
remain saved and do not grant consent for bot messages.

Validation on `exp-notifications.localhost`, Frappe 16.51, installed apps only
frappe/exp_theme/raven/crm (no Celio):

- 14 new CRM integration tests; 10 native notification-link regressions;
  7 native recipient-permission tests; 3 native notification unit tests.
- 24 common-service DB tests rerun with CRM installed, including real One messages.
- 423 CRM frontend tests in 40 files; production frontend build passed.
- Browser: real CRM Task/ToDo assignment, one message per event through the private
  worker, settings in all three directions, read state in both directions,
  stale draft rejection, history after disable, mobile RU/EN, no overflow,
  unknown committed HTTP response followed by exact replay, visible GET failure/retry.
- Ruff F and diff whitespace checks passed. Frappe Semgrep has no new findings;
  the pre-existing `override-doctype-class` finding in CRM hooks is reproduced
  from the exact baseline backup and is unrelated to these hooks.

Local standard CRM fixtures generated 29 email queues despite mute;
they were never sent and are preserved as Error alongside the earlier 28 fixture
queues. The sandbox-only CLI now disables welcome mail and native email notifications
for the standard CRM fixture users when loading them.
Browser task creation leaves the queue unchanged; Sent and pending email are zero,
Raven Push Delivery is zero. TCP/UDP outbound remains blocked and scheduler off.

Evidence and reproduction: `/Users/g-karim/frappe/exp-notifications-20261019/README.md`,
`evidence/browser-crm*.json`, `evidence/crm-validation.json`, `logs/crm-*.log`.
No live Messenger provider or real phone push was exercised. Celio adapter,
early Celio receipt migration, team routes, sender creation, task actions, Meet
and AI remain separate stages in the shared handoff plan.

> **This file**: Completed phases only — decision rationale, what was built, implementation detail. Completed analysis stages are marked explicitly.
> **Current API contracts**: [SPEC.md](./SPEC.md)  
> **Upcoming work**: [PLAN.md](./PLAN.md)

---

## Phase 1 — setFieldProperty & Meta Refactor

> **Completed.** Implemented `setFieldProperty`, `setFieldProperties`, `removeFieldProperty`, `getField` for fields, sections, tabs, and child table rows.

### New pure utility files

| File | Purpose |
|---|---|
| `src/utils/expressions.js` | `_eval`, `evaluateDependsOnValue`, `evaluateExpression` — extracted from `utils/index.js` to allow import without pulling in Vue components |
| `src/utils/fieldTransforms.js` | `processField()`, `findMissingMandatory()`, `parseLinkFilters()` — pure functions, independently testable |
| `src/utils/scriptHelpers.js` | `getClassNames()`, `createDocProxy()` — extracted from `script.js` closure |

### Mutation fixes

Every place that previously mutated shared field objects now clones first:
- `Field.vue` computed: `let field = { ...props.field }`
- `SidePanelLayout.vue` `parsedField()`: `field = { ...field }`
- `Grid.vue` `getFieldObj()`: `field = { ...field }`

`JSON.parse(field.link_filters)` (6 call sites, would throw when `link_filters` was already an object) replaced everywhere with `parseLinkFilters(field.link_filters)`.

### `fieldPropertyOverrides` map structure

Added to the document cache entry alongside `fieldHtmlMap`:

```js
fieldPropertyOverrides = {
  // parent/side-panel fields
  'annual_revenue': { hidden: true },
  'status': { options: 'New\nIn Progress' },

  // sections and tabs (by name)
  'financial_section': { hidden: true },
  'advanced_tab': { hidden: true, label: 'Expert' },

  // child table columns (dot notation)
  'products.qty': { read_only: true },
  'products.discount': { hidden: true },

  // child table per-row (dot notation + colon + row.name)
  'products.rate:row_abc123': { read_only: false },
}
```

### `checkMandatory` rewritten

Old: called `getFields()` which filtered out hidden fields and only checked `mandatory_depends_on`.  
New: `findMissingMandatory()` from `fieldTransforms.js` which:
- Uses raw `doctypesMeta[doctype].fields` (all fields including hidden)
- Checks both `reqd: 1` and `mandatory_depends_on` expressions
- Respects `hidden` and `reqd` from `fieldPropertyOverrides` (script overrides win)
- Hidden fields are always skipped regardless of `reqd`

### Rendering flow (still accurate as of Phase 2)

```
script.js setFieldProperty()
  └─► ctx.fieldPropertyOverrides[target][property] = value
          │
          ├─ SidePanelLayout.vue
          │    parsedField() → Object.assign(field, overrides)
          │    parsedSection() → Object.assign(section, overrides)
          │
          ├─ FieldLayout.vue
          │    processedTabs computed → tab/section overrides merged → hidden tabs filtered
          │    │
          │    └─ Field.vue (non-grid)
          │         computed field → getFieldOverrides(fieldname) → Object.assign(field, overrides)
          │         provide('fieldPropertyOverrides', ...) → Grid.vue injects it
          │
          └─ Field.vue (isGridRow=true, inside GridRowModal)
               inject fieldPropertyOverrides from Grid.vue
               resolves: col key (products.qty) + row key (products.qty:rowName)

Grid.vue
  getFieldObj(field)
    → colKey = `${parentFieldname}.${field.fieldname}`
    → Object.assign(field, overrides[colKey])     ← column-level
    → hidden columns filtered → gridTemplateColumns recalculated

  getRowFieldObj(field, row)
    → rowKey = `${colKey}:${row.name}`
    → merged = { ...colOverrides, ...rowOverrides }  ← row wins over column
    → per-row hidden → empty cell (preserves grid alignment)
```

### Known remaining issues (as of Phase 1 completion)

| Issue | Status |
|---|---|
| `getFields()` still mutates `doctypesMeta` field objects (Select options, Link→User) | Deferred — rendering components clone first now, acceptable until Phase 4 |
| Layout APIs return redundant full field meta | Deferred — full getMeta refactor (Phase 4) |
| `getMeta` `getFields()` filters hidden fields | Intentional for now; raw `doctypesMeta` used where hidden fields needed |

---

## Phase 3A — FieldLayout Standalone Mode

> **Completed.** Added `context` prop to FieldLayout enabling standalone rendering without `useDocument`.

### Problem solved

`FieldLayout.vue` always called `useDocument(props.doctype, props.data?.name)` to get `fieldPropertyOverrides`. For a dialog with inline fields (no doctype), this called `useDocument('', undefined)` creating a garbage entry in `documentsCache`. For a dialog with a real doctype like `'CRM Lost Reason'`, it would trigger script loading unintentionally.

### Decision: Option B — `context` prop

The `context` prop carries the externally managed context object (`{ fieldPropertyOverrides, fieldHtmlMap }`). When provided, `useDocument` is skipped entirely.

**Not chosen: Option A** (`standalone` boolean) — `context` is more extensible, can carry more in future (triggerOnChange, triggerButton, etc.) without adding more props.

### What was built

**`FieldLayout.vue`**:
- Added `context: { type: Object, default: null }` prop
- When `context` is present: uses `context.fieldPropertyOverrides` for tab/section overrides instead of calling `useDocument`
- Provides `fieldLayoutContext` via inject for child Field components

**`Field.vue`**:
- Injects `fieldLayoutContext`. When present: skips `useDocument` entirely, field changes update data directly, scripting triggers are no-ops
- Guards `getMeta(doctype)` — only called when doctype is truthy. Inline mode uses `formatNumber`/`formatCurrency` fallback formatters directly

---

## Phase 2 — formDialog()

> **Completed.** Script authors can open a FieldLayout-based dialog, collect data, and act on it.

### Decision: Option C — Promise + onSubmit callback + custom actions (all three work)

Three patterns were considered:
- **Option A** (callbacks only, consistent with `createDialog`) — too verbose for simple cases
- **Option B** (`onSubmit` only) — doesn't support sequential multi-step workflows
- **Option C** (all three, Promise always resolves) — chosen. Most flexible. Promise for sequential, callback for fire-and-forget, actions for full control.

**Dialog fields are NOT scriptable (intentional).** The dialog is a data collector only. `setFieldProperty` called inside a dialog action affects the **page** fields, not the dialog's fields. Full isolation would require a separate `fieldPropertyOverrides` scope per dialog — deferred.

### What was built

| File | Description |
|---|---|
| `frontend/src/components/Modals/FieldLayoutDialog.vue` | Dialog shell + standalone FieldLayout + local reactive doc. Validates before resolving. |
| `frontend/src/components/Modals/FieldLayoutDialogContainer.vue` | Renders entries from the `fieldLayoutDialogs` reactive array |
| `frontend/src/utils/renderFieldLayoutDialog.js` | Pushes config to array, returns Promise. Internal `onResolve` is distinct from user's `onSubmit`. |
| `frontend/src/components/Modals/GlobalModals.vue` | Mounts `<FieldLayoutDialogContainer />` |
| `frontend/src/data/script.js` | `helpers.formDialog = renderFieldLayoutDialog` — bare helper in script scope |

### Key fixes during implementation

- **Buttons stuck in loading**: `_loading` was a `ref()` inside `computed()`. Vue doesn't auto-unwrap refs nested inside plain objects in templates. Fixed with `reactive({})` `actionLoadingMap` outside the computed.
- **Double-event bug**: `v-bind="dialog.props"` passed `onResolve` as a `@resolve` listener AND `@resolve` explicitly added it again. Fixed by stripping `onResolve` from the spread in `FieldLayoutDialogContainer`.
- **`getMeta('')` console error**: `Field.vue` called `getMeta(doctype)` unconditionally. When doctype is empty (inline mode) this triggers an API call that fails. Fixed with doctype guard.
- **`v-bind="action"` spreading internals**: Template was spreading entire action objects including `_loading` ref, wrapped `onClick`, etc. onto Button. Fixed with explicit prop bindings.

### Layout priority

1. `tabs` — full custom layout (highest)
2. `fields` — flat list, auto-wrapped
3. `doctype` + `fieldnames` — specific fields from doctype meta
4. `doctype` alone — full Quick Entry layout

> Current stable API: [SPEC.md — formDialog API](./SPEC.md#formdialog-api)  
> Full guide with examples: [feats/form-scripting/form-dialog.md](./feats/form-scripting/form-dialog.md)

---

## Touch Tracking — Stage 1

> **Выполнен этап определения правил, 2026-10-08.** Это спецификация будущего поведения, а не описание реализованной функции. Код, схема БД и настройки работающих сайтов на этом этапе не изменялись.
> Следующие этапы: [Touch Tracking в PLAN.md](./PLAN.md).

### Цель и границы

Дать каждому сайту возможность определить, какие события считаются касанием лида или сделки и влияют на их порядок в списке. Первое применение — Таткардан: старые карточки не должны подниматься от любого технического сохранения или переноса задачи, если соответствующее правило не включено.

- Одно дополнительное поле Datetime «Последнее касание» на `CRM Lead` и `CRM Deal`. Отдельную вторую дату «последнего контакта с клиентом» этот этап не вводит.
- `modified`, `modified_by`, защита от одновременного редактирования, штатные уведомления и поведение оригинальных обработчиков сохраняются.
- Правила хранятся в БД сайта, отдельно для Lead и Deal. Установка кода в общем bench не включает функцию на других сайтах.
- Переключатель функции по умолчанию выключен. В выключенном состоянии новые обработчики не меняют касания, представления или штатную сортировку.
- Начальный профиль при первом включении на Таткардане: создание карточки и реальная смена поля `status`. Все дополнительные события и поля выключены. «Новые лиды всегда раньше остальных статусов» — отдельная группировка, в эту функцию не входит.
- Новая дата применяется только к представлениям, отсортированным по касанию. Выбранная пользователем другая сортировка остаётся действующей.

### Что считается событием

Изменение поля — успешное сохранение, в котором нормализованное значение выбранного поля отличается от прежнего. Повторное сохранение того же значения, пустой ввод без реального изменения, открытие карточки или неудачная операция касания не создают.

Возврат статуса к ранее использованному значению считается новым касанием: значение отличается от состояния непосредственно перед сохранением. Несколько выбранных полей в одном сохранении создают одно касание с перечнем причин, а не отдельное касание на каждое поле.

Дата создания служит исходной точкой сортировки. Для нового обычного документа используется его `creation`; для исторического импорта дата и порядок задаются проверенной миграцией, а не массово текущим временем.

### Поля карточки

| Группа | Lead | Deal | Начальный профиль |
|---|---|---|---|
| Статус | `status` | `status` | Включён |
| Ответственный и источник | `lead_owner`, `source` | `deal_owner`, `source` | Выключены |
| Контактные данные | Имя, `mobile_no`, `phone`, `email` | Имя, `mobile_no`, `phone`, `email` | Выключены |
| Организация и описание | Организация, сайт, описание и другие доступные поля | Организация, сайт, описание и другие доступные поля | Выключены |
| Планирование и условия сделки | Доступные бизнес-поля | `next_step`, `expected_closure_date`, `closed_date`, `pipeline`, стоимость и вероятность | Выключены |
| Пользовательские поля | Доступные редактируемые поля из метаданных сайта | Доступные редактируемые поля из метаданных сайта | Выключены |

Настройки строятся по реальным метаданным установленного сайта. Это не жёсткий список обязательных полей. Запрещены служебные даты, само поле касания, журналы статусов, `_assign`, вычисляемые значения, SLA-метрики и поля интеграционных идентификаторов. Автоматически производное поле не считается вторым действием пользователя.

Изменение дочерних таблиц контактов/товаров нельзя подменять сравнением технических строк или `idx`. Поддержка таких правил требует отдельной семантики и приёмочных сценариев; в первом выпуске они недоступны.

Прямая смена ответственного и штатное назначение через ToDo должны давать одинаковый результат, если включено правило ответственного. Все обходные пути записи нужно выявить на этапе реализации; одного браузерного обработчика недостаточно.

### Внутренние события CRM

Каждая строка ниже — отдельное правило, по умолчанию выключенное.

| Событие | Условие касания | Что не учитывается этим правилом |
|---|---|---|
| Новый комментарий к карточке | Успешно создан пользовательский `Comment` типа `Comment`, явно связанный с Lead/Deal | Служебные комментарии о системных действиях |
| Редактирование комментария | Действительно изменено содержимое существующего пользовательского комментария | Сохранение прежнего текста |
| Новая заметка | Создана связанная `FCRM Note` | Открытие заметки |
| Редактирование заметки | Изменены её название или содержимое | Сохранение без изменения |
| Создание задачи | Создана `CRM Task`, связанная с карточкой | Побочные ToDo и уведомления о назначении |
| Завершение задачи | Переход из любого другого статуса в `Done` | Повторное сохранение `Done` |
| Другие изменения статуса задачи | Реальный переход между статусами, включая отмену и повторное открытие; переход в `Done` относится только к правилу завершения | Повторное сохранение статуса |
| Перенос срока | Изменение `due_date`, включая установку и очистку | Наступление срока само по себе |
| Дата начала | Изменение `start_date`, включая установку и очистку | Наступление даты само по себе |
| Приоритет | Изменение `priority` | Сохранение прежнего значения |
| Исполнитель | Изменение `assigned_to` | Техническая синхронизация того же назначения |
| Название/описание задачи | Реальное изменение выбранного поля; название и описание выбираются независимо | Открытие задачи |
| Комментарий к задаче | Новый пользовательский комментарий к задаче, явно связанной с карточкой | Не считается автоматически комментарием к Lead/Deal |

Смена ссылки задачи на другую карточку сама по себе не создаёт касания. Реальное выбранное изменение применяется только к новой явно связанной карточке, не к прежней. Удаление комментария, заметки, задачи или файла не поднимает карточку и не отматывает дату назад. Правила вложений и календарных событий вне первого выпуска и не могут быть включены без отдельного определения поведения.

Если сотрудник сегодня в 10:00 переносит срок задачи на следующую неделю, касание при включённом правиле равно сегодняшним 10:00. Новое значение срока не используется как дата касания. Проверяются оба входа: вкладка задач карточки и общий список задач.

### Мессенджер

| Правило | Условие | Дата события |
|---|---|---|
| Входящее сообщение | Новое реальное сообщение получено от внешнего участника и сохранено с однозначной связью с карточкой | Проверенное время сообщения |
| Исходящее сообщение | Отправка успешно подтверждена каналом; создание локальной записи или нажатие кнопки недостаточны | Время успешной отправки, подтверждённое интеграцией |
| Автоматические исходящие | Дополнительное разрешение для исходящих бота/рассылки; требует также включённого исходящего правила | То же подтверждённое время отправки |

Входящие и исходящие включаются независимо. Черновик, очередь, ошибка отправки, открытие переписки, индикатор набора, доставка, прочтение, редактирование метаданных и повторная синхронизация истории касаний не создают. Отметка «доставлено» может впервые подтвердить ранее неизвестную успешную отправку, но не должна добавлять второе касание или использовать время доставки вместо времени отправки.

Изменение или удаление уже полученного/отправленного сообщения не создаёт повторного касания в первом выпуске. Автоматические исходящие по умолчанию исключены. Если канал не позволяет достоверно определить успешную отправку, автора или автоматическое происхождение, соответствующее правило остаётся недоступным до проверки адаптера; недостающие данные не угадываются.

### Телефония

| Правило | Условие | Дата события |
|---|---|---|
| Состоявшийся входящий разговор | Итог звонка подтверждает соединение с сотрудником, направление Incoming | Подтверждённое время начала разговора; при отсутствии — проверенный `start_time` звонка |
| Состоявшийся исходящий разговор | Итог звонка подтверждает соединение с внешним абонентом, направление Outgoing | Такое же правило времени |
| Входящий пропущенный | Терминальный итог подтверждает входящий звонок без ответа | Проверенное время начала звонка |
| Безуспешная исходящая попытка | Терминальный итог подтверждает реальную попытку дозвона без соединения | Проверенное время начала попытки |
| Ручная фиксация | Пользователь успешно создал связанный ручной `CRM Call Log` | Время действия пользователя; исправление старой даты не является новым разговором |

Правила независимы и первоначально выключены. Запись звонка, AI-расшифровка/анализ, изменение URL записи, промежуточные состояния Ringing/In Progress, заметка о звонке и сохранение технических полей не являются новым разговором. Комментарий или заметка могут учитываться только своим отдельным правилом.

Нельзя универсально считать любой `Completed` доказательством разговора или любой `Failed` попыткой дозвона. Для каждого провайдера на Stage 5 проверяются итоговый статус, ответ, направление, времена и при необходимости длительность. Неподтверждённая или ещё не начавшаяся отменённая попытка не учитывается. Неоднозначный результат не классифицируется автоматически.

Итог одного звонка обрабатывается один раз; повторный callback и последующая загрузка записи не создают новых касаний. Ручной звонок не должен одновременно учитываться как ручной и как провайдерский. Уточнение противоречивого итога провайдера требует диагностического сценария адаптера, а не нового события на каждое изменение статуса.

### Почта

| Правило | Условие | Дата события |
|---|---|---|
| Входящее письмо | Новое внешнее письмо фактически получено системой, сохранено и однозначно связано с карточкой | Проверенное время получения почтовой интеграцией |
| Исходящее письмо | Почтовый транспорт подтвердил успешную отправку | Подтверждённое время отправки |
| Автоматические исходящие | Дополнительное разрешение для автоматических писем; требует включённого исходящего правила | Такое же правило времени |

Запись `Communication` с направлением Sent сама по себе не доказывает отправку. Черновик, постановка в Email Queue, повтор отправки после ошибки и техническое сохранение `Communication` касаний не создают. Повторное получение одного письма, обновление заголовков/метаданных, прочтение и уведомления транспорта о доставке/недоставке не являются новым письмом клиента.

Первый успешный повтор ранее неудачной отправки учитывается один раз. Пересылка или ответ с новым идентификатором — новое письмо, если подтверждена его отправка. Системные уведомления доставки исключены; классификация автоматических ответов и отправителей должна опираться на реальные признаки интеграции, а не только догадку по адресу. Правила автоматических исходящих выключены по умолчанию; распознавание входящих автоответов уточняется при подключении почтового адаптера.

### Источник события и связь с карточкой

- У правил есть источник: действие пользователя, автоматизация/импорт или внешняя интеграция. Это фактическое происхождение операции, а не только `modified_by`. Настройка источников не должна пропускать штатное создание нового лида из формы или входящего канала.
- В исходном профиле новые карточки получают дату создания независимо от источника; реальная смена `status` учитывается через штатные пути. Другие изменения автоматизаций учитываются только при разрешении соответствующего правила и источника.
- Для каналов отдельно управляются входящие, исходящие и разрешение автоматических исходящих. Возможности адаптера должны быть видны администратору до включения.
- Событие применяется к одной явно связанной карточке `reference_doctype + reference_name/docname` либо к единственной подтверждённой основной связи интеграции. Существующие вспомогательные ссылки не означают «обновить все связанные документы».
- Один контакт может быть связан с несколькими сделками. Номер/почта сами по себе не дают права выбрать случайную сделку; при неоднозначности дата не меняется, фиксируется диагностическая причина.
- Поиск по последним четырём цифрам предназначен для пользователя, не для автоматической привязки событий.
- Конверсия создаёт новую сделку с её собственной датой создания. Последующие события сделки автоматически не поднимают исходный лид. Перенос истории при миграции/конверсии не равен новому сообщению.
- Поздняя ручная привязка старого сообщения сама по себе не является касанием; исторический пересчёт — отдельная операция. Отложенная обычная обработка уже связанного события сохраняет исходное время события.

### Время, повторы и успешность

1. Внутреннее изменение учитывается после успешного сохранения в той же транзакции либо надёжно после её фиксации. Откат или ошибка не оставляют касания. Внешнее исходящее учитывается после подтверждения успеха, а не при создании задания.
2. Все даты нормализуются по соглашениям Frappe/сайта. Некорректное, неправдоподобное или будущее время провайдера не должно ставить карточку наверх навсегда: событие диагностируется до применения. Для доступного подтверждённого события без времени используется время первого надёжного наблюдения успеха; причина такого выбора сохраняется, повторы эту дату не обновляют.
3. Новая дата равна максимуму текущей даты и времени подходящего события. Поздний звонок в 10:00, обработанный после сообщения в 10:05, не уменьшает 10:05. Причина возле поля всегда относится к событию, определяющему показанную дату, а не просто к последнему обработанному callback.
4. Ключ повторов включает стабильную идентичность источника/события, вид бизнес-события и целевую карточку. Для повторных реальных правок одного документа нужна версия изменения. Версия настроек сохраняется для объяснения решения, но её изменение не превращает старое событие в новое.
5. Выключение и повторное включение правила не воспроизводят прошлые события. Настройки применяются к новым событиям; история не пересчитывается автоматически. У фонового повтора уже принятого события сохраняются его исходные время, идентичность и решение по правилам.
6. Для событий с одинаковым временем причина выбирается устойчиво по идентичности события. Несколько правил одного сохранения группируются в одно касание; записи соседних задач не склеиваются только по совпадению времени.
7. Фоновая ошибка должна быть наблюдаема и допускать идемпотентный повтор. Сбой дополнительной обработки касания не превращает успешное сохранение комментария, задачи или карточки в ошибку интерфейса или вечную загрузку; потребуется проверенный механизм восстановления. Обновление касания не запускает собственное новое касание, не меняет бизнес-статус и не отправляет сообщения клиенту.
8. Обычный save карточки со старым загруженным значением касания не может затереть более свежую фоновую дату. Это отдельное обязательное условие реализации, а не предположение, что readonly-поля или `update_modified=False` автоматически решают проблему.

### Настройки, права и объяснение

Страница «Касания и взаимодействия»: включение функции для сайта, вкладки Lead/Deal, выбранные поля, внутренние события и каналы. Неподдерживаемые правила не сохраняются как работающие. Валидация выполняется на сервере; удалённое пользовательское поле или неподключённый канал показывают причину недоступности.

Менять правила смогут System Manager и Sales Manager с правом записи настроек; обычный Sales User применяет их при работе. Изменение настроек аудируется с автором и версией. Само изменение правил не меняет даты всех карточек.

Дата касания служебная и не редактируется пользователем напрямую. Минимальная информация о причине содержит вид события, исходный документ/идентификатор, время события, известного автора/канал и применённое правило. Текст переписки, письма, комментария, запись и расшифровка звонка не дублируются.

Доступ к причинам и ссылкам соблюдает права исходной карточки и записи. Если сотрудник видит лид, но не имеет доступа к приватному письму, объяснение не раскрывает его текст, адреса или закрытые метаданные. Само касание не расширяет права на исходную запись.

Сортировка: `coalesce(последнее_касание, creation) desc`, затем `creation desc`, затем `name desc`. Это полный устойчивый порядок, включая равные времена. Он не означает случайную перестановку карточек или жёсткую группировку по статусам.

### Данные и переход со временной сортировки

- У Таткардана уже есть временное поле Lead `custom_crm_status_sort_date`. На Stage 6 его данные переносятся в новое поле без изменения исходных `creation`/`modified`; временный обработчик отключается. После проверки стабильности старое поле удаляется. Два постоянных механизма даты касания не оставляем.
- Исходную дату Deal берём из создания и достоверной истории статусов, не из текущего `modified`, который мог меняться по другим причинам.
- Исторический импорт не делает все карточки «затронутыми сейчас». Неизвестные даты и причины не выдумываются и помечаются как начальное заполнение.
- Стандартные представления меняются по согласованному списку. Сохранённые пользовательские представления, фильтры и другая выбранная сортировка не переписываются массово.
- Откат снимает новые настройки/сортировку и код обработки, сохраняя записи, созданные после выпуска. Полное восстановление старого дампа не является обычным способом отката этой функции.

### Основания и ограничения исследования

Спецификация опирается на read-only аудит Таткардана от 2026-10-08 и 38 локальных сценариев для Lead/Deal. Это снимок исследования, не новая проверка production при записи документа. Бизнес-записи локальных сценариев откатывались, фоновые задания и realtime были подменены; версия локального Frappe отличалась от production.

- В проверенном CRM 2.0-dev новые комментарии и обновления `Communication` могут менять родительский `modified` при включённом `FCRM Settings.update_timestamp_on_new_communication`.
- Обычные изменения `CRM Task`, заметки и ручной Call Log в проверенных сценариях не меняли родительский `modified`. Поэтому нельзя выводить касание из любой даты дочернего документа без отдельного обработчика.
- Телефонная интеграция и мессенджер используют собственные пути обновления дат/связей, в том числе прямые записи в БД. Только `Document.on_update` не покрывает все каналы.
- `CRM Task.track_changes=0` в исследованном сайте; история конкретных переносов сроков не восстанавливается достоверно из одного текущего `modified`.
- Реальная успешная отправка/получение сообщений и завершение звонков для новой функции ещё не проверялись. Stage 5 обязан подтвердить события и время на подключённых каналах.
- Текущий локальный bench `apps/crm` разрешается в `/Users/g-karim/projects/crm`, HEAD `691699d9b`; он отстаёт от проверенного снимка production `df556e380`. Эти документы не разрешают выпуск старой локальной базы. Перед Stage 2 нужна свежая проверка базы и сохранение всех предыдущих исправлений.

### Приёмочные сценарии для следующих этапов

| № | Сценарий | Ожидаемое поведение |
|---|---|---|
| 1 | Сайт с выключенной функцией: save, комментарий, задача, сообщение | Штатное поведение и представления не меняются новой функцией |
| 2 | Новый Lead/Deal; затем реальная смена `status` | Дата создания, затем время смены статуса; касания независимы для двух DocType |
| 3 | Сохранение прежнего статуса и выбранного поля | Нового касания нет |
| 4 | Комментарий и изменение сайта при базовом профиле | Не поднимают карточку по касанию, даже если штатный `modified` изменился |
| 5 | Перенос задачи из карточки и общего списка | Одинаковый результат: выключенное правило не влияет; включённое использует время правки |
| 6 | Задача переходит в Done при включённом завершении | Одно касание; повторный save Done не даёт нового |
| 7 | В одном save меняются два выбранных поля | Одно касание с двумя причинами |
| 8 | Входящее сообщение; затем прочтение, доставка и повторный webhook | Одно касание с исходным временем сообщения |
| 9 | Исходящий черновик/очередь/ошибка; затем успешная отправка и повтор callback | Касание только после успеха, один раз |
| 10 | Бот/рассылка при выключенных автоматических исходящих | Касания нет; включение требует также исходящего правила |
| 11 | Отвеченный звонок, пропущенный входящий и неудачный исходящий | Каждый зависит от своего правила; результат подтверждён адаптером |
| 12 | После звонка загружается запись и завершается AI-анализ | Новых касаний нет |
| 13 | Входящее письмо, повтор получения, служебная правка Communication | Учитывается только первое реальное получение |
| 14 | Email Queue ошибается, повтор затем успешно отправляет | До успеха касания нет; после — одно касание |
| 15 | Позднее событие старше последнего касания | Дата и показанная причина не откатываются |
| 16 | Два одновременных события и save ранее открытой карточки | Сохраняется самая поздняя дата; штатная защита от конфликтов не обходится |
| 17 | Операция откатилась; фоновая обработка упала и повторилась | Нет касания от отката; подтверждённое событие восстанавливается без дубля |
| 18 | У контакта несколько сделок, основной связи нет | Ничего не выбирается случайно; есть диагностическая причина |
| 19 | Пользователь не видит исходное приватное письмо | Причина не раскрывает закрытые сведения и ссылка не обходит права |
| 20 | Включение/выключение правила, перезапуск и повтор старого события | История автоматически не пересчитывается и не поднимается |
| 21 | У нескольких карточек одинаковые времена | Повторная загрузка/пагинация дают устойчивый порядок по creation/name |
| 22 | Миграция временного поля и повторный запуск миграции | Значения и исходные даты сохраняются; повтор не создаёт новых касаний |
| 23 | После успешной бизнес-операции обработчик касания недоступен | Операция и интерфейс работают штатно; ошибка наблюдаема, касание можно восстановить без повторной отправки сообщения или повторного создания комментария |

### Итог первого этапа

Определены базовый профиль, отдельные правила полей/задач/комментариев/заметок, события переписки/телефонии/почты, источники, связь с карточкой, время, повторы, права и критерии совместимости. Конкретные имена новых технических полей/DocType, схема хранения событий и адаптеры провайдеров выбираются и проверяются на следующих этапах. В `SPEC.md` не добавлены ещё не реализованные API-контракты.


---

## Touch Tracking — Stage 2

> **Выполнен серверный этап, 2026-10-08.** Реализация находится в `/Users/g-karim/projects/crm-touch-tracking-stage2-20261008`, ветка `codex/crm-touch-tracking-stage2`, база `df556e380`. Основной локальный bench не переключался, production не изменялся. Изменения пока не закоммичены; выпуск и PR остаются Stage 7.

### Что реализовано

- Одно стандартное служебное поле `last_touch_at` на Lead и Deal: Datetime, индекс, readonly, hidden, no_copy. На этом этапе список и интерфейс CRM не переключаются на новую сортировку.
- Отдельный Singleton `CRM Touch Settings` в БД каждого сайта: `enabled=0`, включение Lead/Deal независимо, отдельный учёт смены статуса каждого типа. Создание — базовое событие включённого типа.
- Неизменяемые снимки правил `CRM Touch Policy`. Изменение настроек записывает новую ревизию в той же транзакции; повторный save без изменения правил ревизию не меняет. Новые правила не применяются к прошлым действиям.
- Служебный журнал `CRM Touch Event`: вид события, целевая карточка, исходная запись, фактическое время, известный автор и ревизия правил. Текст сообщений/комментариев, файлы и записи звонков не копируются. Прямые создание/редактирование журнала пользователями закрыты.
- Штатные `doc_events` на создание и реальную смену `status`, без замены контроллеров. Неизменённый статус и другие поля дату не двигают. Обработчики оригинального CRM продолжают работать.
- Идемпотентное применение даты: она только увеличивается. Повтор одного источника не создаёт второй записи; запоздавшее событие не откатывает последнее касание. Имя события — SHA-256 идентичности источника, вида события и карточки, без ревизии настроек или времени повтора.
- Обновление даты через `update_modified=False`; родительские `modified` и `modified_by` дополнительно не меняются. `before_validate` восстанавливает служебную дату из актуальной строки, уже прочитанной/заблокированной Frappe, чтобы старый save не затёр результат фоновой обработки. Штатная проверка конфликтов Frappe сохраняется.
- Ошибки дополнительной обработки изолируются savepoint. Принятое событие остаётся Pending с количеством попыток, типом ошибки и временем следующей попытки; повтор не пересохраняет карточку и не воспроизводит бизнес-операцию.
- Пропущенная запись события восстанавливается из собственного `creation` карточки или новой строки штатного `CRM Status Change Log`, с правилами, действовавшими в тот момент. Не используется произвольный `modified` или недостоверная история задач. У статуса берётся серверное `creation` новой строки, а не legacy `from_date`.
- Отдельное задание `crm.touch_tracking.maintenance` каждые 5 минут: повторы Pending и восстановление пропущенных источников. Уже принятые события завершаются по исходной ревизии даже после выключения; новые действия в выключенный период не учитываются и не воспроизводятся после повторного включения.
- Удаление карточки не блокируется ссылкой из служебного журнала; её Pending-событие становится Ignored и карточку не восстанавливает.

### Конкуренция и ошибки MariaDB

Обычный save и обработчик события используют порядок блокировок «карточка, затем событие». Локальная MariaDB 11.8.8 показала конфликт снимка транзакции (1020), который Frappe 16 оборачивает в `QueryDeadlockError`. В проверенном Frappe 16.28 механизм рекурсивного повтора задания также может потерять `local.job` после повторного выполнения.

Оригинальный код Frappe не менялся. В собственном задании maintenance реализованы до трёх попыток всей его транзакции при конфликте снимка/дедлоке. Повтор разрешён только в контексте именно этого задания, не внутри чужого задания или HTTP-сохранения. Полный откат транзакции, потеря соединения или недействительный savepoint не маскируются как успешное сохранение: такие ошибки передаются штатной обработке Frappe. После исчерпания попыток журнал остаётся источником следующего запуска.

### Проверки

- Отдельно создан сайт `crm-touch-stage2.localhost` с Frappe **16.28.0** и только Frappe/CRM. База `_crm_touch_stage2_20261008` и файлы расположены в отдельном test bench; существующие локальные сайты не мигрировали и не переключали.
- 24 новых теста правил/реальной БД и 10 регрессий прежнего поиска/сортировки: всего **34**. Проверяются создание/статус Lead/Deal, отключённый профиль, no-op, отказ записи журнала, отказ применения, повторы, откат, смена правил, старое открытое окно, конфликт обычных изменений и права Sales User.
- Отдельная проверка двух одновременных соединений через настоящий `frappe.utils.background_jobs.execute_job` для Lead и Deal: оба события применены, максимальная дата сохранена, родительский modified не изменился; save старой открытой карточки сохранил дату. В каждом случае один обработчик пережил конфликт снимка и успешно повторил собственную транзакцию.
- Все **619 frontend-тестов в 54 файлах** прошли. Интерфейс и сборка frontend не менялись.
- Ruff check/format, проверка JSON схем и `git diff --check`.
- Бизнес-записи тестов откатывались; временные записи параллельной проверки удалены только в отдельной тестовой БД. Настройки этого тестового сайта по завершении выключены.

### Ограничения и следующий этап

На этом этапе поддержана MariaDB; включение функции на другой СУБД отклоняется валидацией настроек. Нет новой CRM-страницы, новой сортировки, обработчиков задач/комментариев/каналов и миграции временного поля Таткардана — они остаются Stage 3–7. Нет новых whitelisted HTTP-методов и изменений Form Script API.

База совпадает с последним проверенным снимком Таткардана и подтверждённой remote-веткой PR #15. Свежая проверка production HEAD через SSH в этой работе не удалась из-за тайм-аута подключения; выпуск на сервер не выполнялся. Перед Stage 7 нужны новый preflight, миграция на целевой версии Frappe, полная резервная копия и проверка восстановления.

---

## Touch Tracking — Stage 3

> **Выполнен серверный этап, 2026-10-08.** Продолжение в `/Users/g-karim/projects/crm-touch-tracking-stage2-20261008`, ветка `codex/crm-touch-tracking-stage2`. Код основного bench и production не менялся; изменения пока не закоммичены. Интерфейс настроек и сортировка остаются Stage 4, каналы — Stage 5, выпуск — Stage 7.

### Закрытые пункты плана

- [x] Выбор реальных изменений доступных полей Lead/Deal, включая редактируемые пользовательские поля сайта; технические поля, дочерние таблицы, секреты и производные значения исключены.
- [x] Создание и реальное редактирование пользовательских комментариев и заметок — независимые правила.
- [x] Создание задачи, завершение, остальные переходы статуса, срок, дата начала, приоритет, исполнитель, название и описание — отдельные правила.
- [x] Новый комментарий к связанной задаче — отдельное правило; перенос срока использует время правки, а не будущий срок.
- [x] Серверные обработчики покрывают пути карточки/списка через Document.save и штатный frappe.client.set_value, а также разрешённые автоматизации. No-op не создаёт касания.

### Реализация

- `crm.touch_tracking_internal`: выбор полей по метаданным сайта, нормализация сравнения, проверка настроек и обработчики внутренних событий. Списки `lead_fields`/`deal_fields`, `lead_events`/`deal_events` и разрешение автоматизаций сохраняются в Singleton сайта и неизменяемых ревизиях.
- Все дополнительные правила по умолчанию выключены. Начальный профиль создания/реальных статусов из Stage 2 сохранён. Порядок JSON-списка и повторные элементы не создают новую ревизию настроек.
- Несколько выбранных полей одного сохранения, включая включённый статус, группируются. Изменения, появившиеся только внутри native validate, не становятся отдельным пользовательским касанием. Текстовые пробелы/HTML не упрощаются произвольно; эквивалентные пустые, числовые, логические и временные значения не считаются новой правкой.
- Штатное назначение ответственного через ToDo наблюдается после его настоящей записи в БД. Вложенное назначение из сохранения Lead/Deal не создаёт дубль. При вставке уже отменённого назначения проверяется итоговый владелец, а не промежуточная запись.
- `CRM Touch Change` — короткий неизменяемый источник выбранного изменения в той же бизнес-транзакции: целевая карточка, исходная запись и ревизия, причины, время, автор, происхождение и политика. Значения полей и содержимое не копируются. Это нужно для восстановления нескольких правок задачи, у которой `track_changes=0`.
- `CRM Touch Event` дополнен ревизией источника, списком причин и происхождением. Идентичности Stage 2 сохранены; номер задачи в виде числа и строки означает один источник. Повторный callback той же ревизии не создаёт дубль; новая реальная правка создаёт новую ревизию.
- Задача/комментарий/заметка не блокируют родителя дополнительным синхронным обновлением: после commit запускается прежний частный maintenance worker, каждые 5 минут остаётся резервный повтор. Отказ отправки в Redis после commit не возвращает сотруднику ошибку уже сохранённой записи.
- Пропущенные Event восстанавливаются из Change по принятым причинам и исходной политике, даже после выключения. Восстановление сгруппированного события идёт перед native status recovery, чтобы не потерять дополнительные причины.
- Смена связи сама по себе не касание; выбранная правка относится только к новой явно связанной карточке. Удаление не отматывает дату. Служебные комментарии и редактирование комментария к задаче не подменяют отдельные правила.
- Frappe framework, родные проверки прав/конкурентности, `modified`, прежний поиск и временная сортировка не заменялись. Единственное место наблюдения прямой бизнес-записи — существующий CRM ToDo mirror; общий monkeypatch БД не используется.

### Проверки

- **58 серверных тестов**, без пропусков: Stage 2, новые правила и регрессии поиска/сортировки. Реальный пользовательский Check-field проверен в отдельном тестовом сайте. Покрыты обе сущности, нормализация/no-op, повторные правки, группировка, статусы задач, установка/очистка дат, назначение, комментарии, заметки, relink, политики и автоматизации.
- Инъекции отказов: Event insert, применение даты и отправка в очередь; проверены восстановление нескольких ревизий по старой политике, откат вместе с бизнес-транзакцией, неизменяемость журнала и проброс настоящего отказа транзакции MariaDB.
- Два настоящих соединения MariaDB: сохранение задачи при заблокированном родителе завершилось до снятия блокировки и для Lead, и для Deal. Затем два настоящих `execute_job` обработали Pending; один пережил конфликт снимка и повторил свою транзакцию. Касание применилось один раз, parent modified сохранился.
- **619 frontend-тестов в 54 файлах** прошли; изменений frontend в этом этапе нет. Ruff check/format, JSON-схемы и `git diff --check` проверены.
- Использован только существующий disposable bench `crm-touch-stage2-validation-20261008`: Frappe **16.28.0**, MariaDB **11.8.8**, сайт `crm-touch-stage2.localhost`. Все тестовые Lead/Deal/Task/Note/Event/Change удалены или откатились; настройки сайта выключены. Тестовый custom-field оставлен как fixture.
- Отчёты и воспроизводимый параллельный probe: `stage3-backend-results.json`, `stage3-concurrency-results.json`, `stage3_concurrency.py` в test bench.

### Границы проверки

Проверены серверные пути, которыми пользуются карточка и список; новое управление в браузере ещё не создано. Реальные мессенджер/телефония/почта и целевая версия Frappe production в этом этапе не проверялись. Их подключение и выпуск остаются отдельными этапами.

Session-запросы считаются пользовательскими; jobs/import/patch/migrate/safe-exec, Guest/token API и Python без запроса считаются автоматизациями. Другие интеграции с прямыми SQL-записями требуют отдельного адаптера. Если не удалось записать сам минимальный источник, ошибка диагностируется без отмены бизнес-save; достоверно восстановить такую правку задачи из одного её текущего modified нельзя, история не выдумывается.


---

## Touch Tracking — Stage 4

> **Выполнен локальный этап, 2026-10-08.** Та же ветка `codex/crm-touch-tracking-stage2`, checkout `/Users/g-karim/projects/crm-touch-tracking-stage2-20261008`. Код основного bench и production не менялся; коммиты и выпуск остаются Stage 7. Stage 5 — проверяемые события переписки, звонков и почты.

### Stage 4 — Интерфейс настроек и сортировка

- [x] Добавить страницу «Касания и взаимодействия» с вкладками «Лиды» и «Сделки», выбором полей, событий и допустимых источников.
- [x] Показывать доступность интеграций и причину недоступности неподключённых правил; объяснять, какое событие подтверждает успешную отправку или разговор.
- [x] Добавить сортировку и колонку «Последнее касание», показ причины с разрешённой ссылкой на исходную запись.
- [x] Использовать устойчивый порядок: дата касания по убыванию, затем `creation` и `name` по убыванию; при отсутствии даты брать `creation`.
- [x] Сохранять пользовательские фильтры, права и явно выбранную сортировку; менять только согласованные стандартные представления.

### Реализация

- Страница «Касания и взаимодействия» в настройках CRM доступна System Manager и Sales Manager. Для каждого сайта: общий переключатель, независимые вкладки лидов/сделок, поиск выбираемых полей, 14 внутренних правил, отдельное разрешение автоматизаций. Удалённые/недоступные поля показаны с возможностью убрать их из выбора даже при выключенном учёте.
- Переписка, звонки и письма показываются с будущими правилами и объяснениями успеха. Отсутствующий messenger app отмечается отдельно; все правила каналов в Stage 4 отключены, потому что адаптеры ещё не проверены. Наличие штатных call/email функций не означает проверенного подключения провайдера.
- `crm.touch_tracking_ui`: ограниченный API настроек и причины касания. Сохранение блокирует Singleton, проверяет версию, валидирует только разрешённые ключи и использует штатный Document.save. Два открытых окна не могут незаметно перезаписать настройки друг друга.
- «Последнее касание» добавлено в стандартные списки, выбор колонок и сортировку. Пустая дата использует creation; равные даты разрешаются creation и name по убыванию. Явные пользовательские направления и состав сортировки сохраняются, недостающие tie-breaker добавляются. SQL строится выражениями query builder с правами Frappe, без конкатенации пользовательского SQL.
- Сохранённые колонки, фильтры и сортировка остаются выбранными сотрудником; массового изменения CRM View Settings нет. Новый default применяется к новым/несортированным стандартным представлениям включённого типа. Clear Sort явно возвращает default сайта. Ручной порядок Kanban сохранён.
- Нажатие даты в списке открывает краткую причину и разрешённую ссылку. Проверяются права на карточку, источник и его текущую связанную карточку; закрытые поля исключаются. Удалённый/закрытый источник возвращает общее пояснение. Значения полей, тексты и автор не раскрываются. Причина соответствует текущей дате, а не порядку прихода callback.
- UI не запрашивает причины для всех строк заранее; кэш сбрасывается при изменении настоящей даты. Ошибка/таймаут заканчивают загрузку и позволяют повтор. Лимит UI-запроса — 20 секунд; серверная транзакция при таймауте не отменяется, повтор настройки защищён версией.
- Добавлены русские строки интерфейса и причин; каталог проверен Babel. `modified` и Form Script API не заменялись.

### Проверки

- **80 серверных тестов**, без пропусков/ошибок: предыдущие Stages 2–3, поиск/списки, 18 новых проверок UI API. Проверены оба типа, реальные права Sales User, закрытый/удалённый источник, скрытые причины полей, fresh Singleton, устаревшее сохранение, валидация, creation-fallback выбранной Kanban-колонки, стабильный порядок с NULL/равными датами, фильтры/лимит, сохранённые представления и выключенная функция.
- **626 frontend-тестов в 55 файлах**; 7 новых проверок утилит охватывают выбор default, независимые изменения настроек, нормализацию наборов, успех/отказ/таймаут запроса и удаление таймера.
- Полная production-сборка frontend прошла (3014 модулей). Для изолированного checkout использован wrapper Vite: существующий framework UI из bench подключён только для сборки, output — в test bench; основной Vite config и HTML приложения не менялись. Сборка сохранила штатные предупреждения о размере chunks/Browserslist.
- Chrome + Playwright, с настоящими компонентами Vue/frappe-ui и контролируемыми HTTP-ответами: загрузка и сохранение независимых правил, запрет каналов, ошибка/Retry причины, разрешённая ссылка, сброс кэша при смене даты, отсутствие ссылки на закрытый источник, ошибка/Retry страницы настроек. Ошибок JavaScript нет. Русские экраны просмотрены; проверена ширина 980 px без горизонтального переполнения.
- Ruff и ESLint новых файлов без ошибок; JSON/PO и `git diff --check` проверены. Все тестовые бизнес-записи откатились, disposable сайт остаётся с выключенной функцией.
- Отчёты: `stage4-backend-results.json`, `stage4-frontend-tests.log`, `stage4-build.log`, `stage4-ui-results.json`; воспроизводимые wrapper/harness и скриншоты `stage4-settings-ru.png`, `stage4-channels-ru.png` в `crm-touch-stage2-validation-20261008`.

### Границы проверки

Браузерные сценарии проверяют новые компоненты с контролируемыми ответами; это не полный HTTP end-to-end запуск CRM на production. Серверный API независимо проверен на настоящем disposable Frappe 16.28.0 + MariaDB 11.8.8. Целевая версия production, реальные каналы и перенос старой даты не проверялись в Stage 4. Group/Kanban показывают дату штатным renderer, popup причины реализован в таблицах Lead/Deal. Паритет fallback-сортировки при экспорте и совместимость целевой версии остаются Stage 6.


## Touch Tracking — Stage 5 implementation snapshot

**2026-10-08. Local implementation; Stage 5 live acceptance remains pending; native Novofon producer is implemented locally.** Existing isolated branch `codex/crm-touch-tracking-stage2`, base `df556e380cf95042562b9198aa0f09bb3d165bcd`. No commit, PR, deployment, production settings change, real call or message was made.

### Implemented

- Independent Lead/Deal channel rules and per-channel outgoing automation permissions, included in immutable policy snapshots; the manager UI saves them with its existing version check. Provider rules are gated on site acceptance; manual call logging is separate.
- Minimal durable source/card/origin binding and first confirmation receipt; native identities are hashed. Acceptance uses original event time/policy, not callback arrival or a later setting. Unknown outbound origin cannot be treated as a human/bot or reserve a duplicate identity ahead of a known CRM send.
- Messenger hooks observe new inbound webhook messages and the first persistent successful outbound send. Queue/failure/retry, history, edit/delete, delivery/read, attachment and provider metadata updates do not create a new touch. Relinking cannot move an existing dispatch to another card.
- Cooperative native Frappe 16 Email Account/Queue mixins preserve native methods and commits. Actual inbound process provides MIME headers; verified receive time is independent of sender Date. Successful SMTP recipient writes plus final transport queue confirmation establish outbound success. Direct Communication Sent, draft/queue/failure and service notifications do not qualify. No global framework patch was made.
- Recovery repairs a missing event from confirmed receipts, including after disabling settings; pending bound sent emails/messages use durable native confirmation, without scanning/importing historical conversations. Original source links survive Email Queue cleanup. Batch selection avoids starvation by older unfinished queues.
- Authenticated manual call creation is connected; recording/date/AI edits are excluded. Private normalized provider-call contract rejects generic Completed, uncertain outcome, missing employee/identity/authentication and secondary-link fanout. Novofon now has a native producer in separate branch `codex/novofon-touch-stage5`, base `3f9da381a039f14e3f18cbf5931a9de8fa8d3c59`; other native fcrm providers are not wired.

### Novofon producer

The user confirmed Novofon as the active telephony provider. The isolated fcrm worktree adds optional transactional binding, after-commit statistics jobs and bounded pending-receipt cron recovery. Webhook outcome alone is not trusted. The job uses the existing signed legacy REST client against `/v1/statistics/pbx/` version 2; checks PBX ID, single matching leg, mapped enabled employee, full phone fingerprint and verified account clock, and confirms explicit answered/missed/unsuccessful rules through CRM's receipt/outbox. Failure/unknown/ambiguous/truncated statistics do not produce a touch. Relinks keep the original card; callbacks, recording/AI updates and retries do not count again.

Provider availability now requires installed readiness hooks, site acceptance and an explicitly verified Novofon timezone; no flag was set in production. Retry metadata is server-only and does not copy payloads, numbers or recordings. Details and live acceptance boundaries are documented in the fcrm worktree's `docs/touch-tracking.md`.

### Verified locally

Disposable `crm-touch-stage2.localhost`, Frappe 16.28.0 / MariaDB 11.8.8, source `crm_messenger` c4d0925678958d0a7793b0026f1b71e1482ee3af installed only in this test bench; the isolated fcrm_telephony source was also installed here for native producer tests. Real native mail receive/send/document paths ran with controlled transport responses and no network messages. Tests include failed first send/retry, duplicate callbacks/native IDs, unknown echo ahead of known send, relink, per-type automation, late/future timestamps, source-header classification, recording/AI exclusions, outbox recovery after disable, and minimal audit content.

119 backend tests passed (23 channel tests, 16 Novofon tests and prior 80), 626 frontend tests passed; production frontend build succeeded. Chrome/Playwright exercised independent selections, outgoing automation prerequisites, versioned saves, unavailable provider gates and the Russian screen. These browser scenarios use controlled API responses, not a production browser session. Tests and source checks are recorded in `crm-touch-stage2-validation-20261008/stage5-*`.

### Remaining evidence

SSH banner/connection attempts to target directly, via configured jump host, and to the old host timed out. Current production app versions, accounts and live channel behavior were not verified. Novofon usage is confirmed by the user; its actual account/API protocol and timezone are still unknown. In local `fcrm_telephony` 3f9da381a039f14e3f18cbf5931a9de8fa8d3c59, `create_call_log` unconditionally writes Completed and updates modified across linked cards. Novofon process consumes END callbacks but drops disposition, falls back to now on invalid call_start and does not enforce signature validation; Beeline imports `/records`, losing the evidence needed for missed/unsuccessful attempts. Those records must not be retroactively called real conversations. The Novofon observer is wired after reading the persisted native Call Log, including on duplicate callback. It does not replace original call creation or recording handling. Deadlock/lost-connection failures propagate for native job rollback; ordinary ancillary errors remain isolated.

Primary source check also confirms why status-only interpretation is unsafe: [Twilio Call resource](https://www.twilio.com/docs/voice/api/call-resource) allows answered IVR/voicemail in Completed, and a completion callback may contain a terminal busy/failed/no-answer status. [Zadarma legacy webhook reference](https://zadarma.com/en/support/api/) documents disposition separately; it is not proof of current Novofon account/API semantics. No provider has been enabled from these documents alone. The current Novofon account must support the existing legacy client protocol; provider completion, transfer/IVR behavior and the bounded statistics window require live acceptance before deployment.

The remaining Stage 5 checks stay in PLAN; Stages 6/7 remain unchanged. Initial Tatkardan profile is still creation plus actual status only.

---

## Touch Tracking — Stage 6

> **Выполнена локальная совместимость и подготовка миграции, 2026-10-09.** Рабочая ветка `codex/crm-touch-tracking-stage2` в `/Users/g-karim/projects/crm-touch-tracking-stage2-20261008`; код не закоммичен и не опубликован. На production выполнялось только чтение. Миграция, включение, перезапуски и изменения production-конфигурации не выполнялись. Stage 5 live acceptance и Stage 7 остаются в PLAN.

### Закрытые пункты

- [x] Целевая версия Frappe, Group/Kanban и CSV/Excel с creation fallback, ручным порядком Kanban и правами сотрудника.
- [x] Приёмочные сценарии Stage 1: конкурирующие записи/воркеры, ошибки БД и savepoint, повторы, старое открытое окно и права.
- [x] Штатное поведение/сортировка выключенного сайта и сохранённые явные пользовательские настройки.
- [x] Явный перенос прежней даты Lead, отключение старого writer без двух параллельных механизмов.
- [x] Seed Deal по созданию/достоверной цепочке статусов, без произвольного modified.
- [x] Сохранение ID, creation, modified, других business-столбцов, связей, прав и истории; отсутствующая история задач не выдумывается.
- [x] Повторный запуск, функциональный откат и проверка прежнего кода без удаления новых business-данных.

### Production evidence и изоляция

Обходной SSH к `147.45.96.231` через `5.42.98.10` позволил получить read-only снимок bench `/home/frappe/frappe-bench`, сайта `tatkardan.exp-verse.com`. Позднее отдельные SSH-соединения вновь тайм-аутятся; ни одной записи или перезапуска на сервере не было. Supervisor-сервисы в снимке работают. Подтверждены Frappe **16.25.0**, Python **3.14.4**, MariaDB **10.6.23**. Рабочие Git checkout чистые: CRM `df556e380cf95042562b9198aa0f09bb3d165bcd` совпадает с базой реализации, fcrm_telephony `3f9da381a039f14e3f18cbf5931a9de8fa8d3c59` совпадает с Stage 5 базой, messenger — более новый `eb4af567072df2ba9dc0360561e42cab24aeea19`.

Novofon выключен/ключи отсутствуют; все 6 Email Account имеют выключенные incoming/outgoing; Messenger Channel — 0. Это текущее состояние проверенного сайта, при этом пользователь сообщил использование Novofon. Никакой адаптер автоматически не включён; живой аккаунт/провайдер и PBX-сценарии остаются Stage 5.

Создан отдельный `crm-touch-stage6.localhost`, БД `_crm_touch_stage6_20261009`, bench `crm-touch-stage6-validation-20261009`. Точный код Frappe **16.25** получен по подтверждённому production SHA `9a8daf343db69a0127f470bad8be0af192cd80c8`; code/schema messenger также соответствуют production SHA. Fixture schema клонирована из пустого локального validation bench; локальная MariaDB **11.8.8**, Python **3.14.6**. На production MariaDB 10.6 read-only проверены базовые выражения дат. Полное восстановление production-БД/файлов и полный прогон на MariaDB 10.6 в Stage 6 не выполнялись: это обязательная проверка выпуска.

### Изменения

- CRM-only export route использует эффективную серверную сортировку и ту же permission-aware COALESCE-сортировку, что список. Значение CSV/Excel для пустой даты совпадает с видимой датой создания. Сохранены native export/field/owner permissions, форматы и Access Log; выбор строк пересекается с фильтрами. Остальные экспорты остаются native.
- `touch_tracking_migration.py` предоставляет явные private CLI prepare/apply/rollback без implicit commit. Site-bound manifest хранит исходные значения и проверенный seed; устаревший источник/повреждённый manifest отклоняется. Новые значения не уменьшаются, бизнес-документы не пересохраняются.
- Миграция переименовывает только ссылки на прежнее поле в Lead-представлениях. Ручной Kanban и explicit user choices не заменяются. Стартовый профиль ограничен созданием/статусом.
- Скрытые серверные migration controls защищены от обычного settings save/API. Старый writer замораживается после cutover даже при последующем disable; возвращается только при явном rollback.
- Откат восстанавливает прежние status-only даты с учётом реальных новых переходов; сохраняет новые карточки, действия, даты, аудит и изменённые представления. Текущая история/представления читаются с блокировкой, а не из старого SQL-снимка. Полный abort передаётся вызывающей стороне для rollback/retry всей транзакции.
- Составлена [инструкция подготовки, применения и отката кода](./feats/touch-tracking/migration.md). Возврат старого кода требует сохранённой добавленной схемы, очищенных hooks/cache и native schedule sync; старый migrate не запускается.

### Проверки и репетиция

- **141 backend test, 0 failures/errors/skips** на target-коде Frappe 16.25: прежние 119 плюс 22 migration/export/group/Kanban/permission сценария. Нативные почтовые пути проверены с mock transport; учтено отсутствие метода redaction в 16.25. Исходный framework не менялся.
- **627 frontend tests, 55 files**; production frontend build **3014 modules**. Использован прежний isolated wrapper Vite с существующим framework UI dependency; output в отдельный test bench. Git-tracked generated auto-imports возвращён к исходному состоянию. Prettier/ESLint, Ruff и diff/schema checks прошли.
- Снимок **3 806 Lead, 3 Deal, 4 507 status rows, 28 views** восстановлен как fixture ID/дат/цепочек/представлений, без полного набора бизнес-значений и файлов. Все даты и полный прежний порядок лидов совпали после переноса. Изменились ровно 3 представления с прежним sort key; остальные настройки и manual Kanban сохранены. Protected hashes других столбцов, связей/прав/истории на fixture БД совпали; синтетических событий нет.
- Проверены повтор apply, нативные новые lead/status/task/comment после cutover, отсутствие касания от выключенных deadline/comment правил, повтор rollback и сохранность более новой сортировки пользователя. Прежние CRM/fcrm source HEAD после rollback с сохранённой схемой выполняют native list/create/status и прежний writer; sync_jobs удаляет tracking schedule после clear-cache.
- Повторён реальный concurrency probe для Lead и Deal: задача сохраняется при удерживаемой блокировке карточки, два native execute_job воркера применяют событие один раз после SQL-конфликтов; modified карточки остаётся business modified.
- Отдельный stale-snapshot rollback probe доказал сохранность статуса и представления, записанных другим соединением. На MariaDB 11.8 locking read дал 1020/QueryDeadlockError: выполнен полный rollback и повтор операции в новой транзакции; не было частичного успешного отката.
- Все временные business fixtures удалены только в отдельной тестовой БД; tracking/providers/allowlist выключены, scheduler paused. Реальных звонков/писем/сообщений не отправлялось.

Отчёты и воспроизводимые scripts: `/Users/g-karim/Documents/Codex/2026-09-22/new-chat/work/crm-touch-stage6-validation-20261009` — `stage6-backend-results.json`, `frontend-tests.log`, `stage6-build.log`, `rehearsal-results.json`, `stage6-concurrency-results.json`, `rollback-concurrency-results.json`, `old-code-results.json`. Snapshot/manifest содержат представления и защищены chmod 600; не предназначены для Git/публичных отчётов.


---

## Touch Tracking — Stage 7

> **Выпуск на Таткардане выполнен 2026-10-09, 11:37:58–11:38:24 Europe/Moscow.** Проверка в обычной работе и последующее удаление прежнего поля остаются в PLAN; проверка живых каналов остаётся Stage 5.

### Выпущено

CRM runtime `1cf733aec46b8693fa45c31cb1f8390d5e557c43`, fcrm_telephony `f36781fe2624b96b60283cb2aecbeb30c6b1490d`. Frappe `9a8daf343db69a0127f470bad8be0af192cd80c8` / 16.25.0, MariaDB 10.6.23 и Python 3.14.4 не обновлялись. CRM разделён на логические commits для tracking, migration, UI и документации. PR: [CRM #16](https://github.com/g-karim/crm/pull/16), основан на уже выпущенном #15; [Novofon producer #1](https://github.com/g-karim/fcrm-telephony/pull/1). PR не объединялись автоматически.

- На `tatkardan.exp-verse.com` включены отдельное поле «Последнее касание», настройки каждого типа карточки и базовый профиль: создание/фактическая смена статуса Lead/Deal. Обычный `modified` не изменён. Комментарии, заметки, задачи/их даты, дополнительные поля и каналы выключены.
- Все прежние Lead dates и полный порядок **3807 лидов** сохранены точно. **3 сделки** получили seed из создания и достоверной нативной истории статусов. Синтетических исторических событий не создано.
- Миграция переименовала только ссылки на старое поле в трёх представлениях: 19, 20, 22. По отдельному прямому ответу пользователя стандартный Lead list Усмана (18) переключён с modified на последнее касание; все остальные настройки этого списка сохранены, другие представления не переопределены.
- Старый `custom_crm_status_sort_date` заморожен для отката; параллельного writer нет. Схема/профиль установлены только на Таткардане. Shared source обновлён на bench: list API остальных **10 CRM-сайтов** работают без новой схемы/включения, их конфигурации сохранились.
- Novofon выключен, credentials не настроены; incoming/outgoing всех шести Email Account выключены; Messenger Channel отсутствуют. Verified adapter allowlist не включался. Live provider acceptance пока не выполнен.

### Полная копия, репетиция и откат

Полный native backup БД, public/private files, site/common config и encryption key проверен и сохранён вне сервера. Восстановление выполнено отдельно на целевой MariaDB 10.6 с точными app sources, независимыми Redis, без scheduler/workers и исходящих каналов. Preserve: оригинальные ID, все бизнес-значения, 4509 status rows, 64 задачи, 756 заметок, 15620 комментариев, связи, роли/права и credentials; 11 локальных файлов проверены по SHA-256. Единственный remote File — внешняя Gravatar-аватарка.

Полная репетиция `bench migrate` обнаружила переписывание служебных Has Role и очистку orphan desktop metadata; поэтому выпуск использовал штатный узкий импорт семи CRM DocType, без миграций остальных приложений. При узком импорте и apply все 19 защищённых наборов/бизнес-столбцов, роли, права и credentials совпали по полным digest. Оригинальные DocPerm/Custom DocPerm отдельно сравнивались с dump.

Проверены создание/смена статуса, комментарий и изменение due_date задачи, поиск телефона, точные даты/порядок, повтор apply, сохранность новых карточек и пользовательских предпочтений после rollback. Функциональный откат и прежние CRM/fcrm sources с добавленной схемой выполняют нативные операции. Native schedule sync на rollback добавляет два системных audit-комментария удаления tracking jobs; доказано, что все исходные 15620 комментариев сохранились неизменными.

Финальная копия `20261009_113804` также полностью восстановлена в отдельный site/БД. Все 19 защищённых наборов совпали с production-before snapshot, файлы и encryption key проверены. Во время production cutover scheduler/workers завершены плавно, общие очереди не очищались. Сохранены старые sources/assets и private migration/override manifests. Maintenance/pause восстановлены; все Supervisor-сервисы работают.

### Проверки

- **142 backend tests**, без failures/errors/skips; **627 frontend tests в 55 файлах**, production build **3014 modules**. CRM Ruff / изменённые frontend ESLint и Prettier прошли. Novofon tests входят в общий backend suite; в прежних файлах fcrm остаются исходные lint-замечания без новых.
- Реальный Chrome/Playwright через HTTP на полной копии: Administrator и существующий Sales User, оба списка с last touch, окно настроек, отдельные вкладки Lead/Deal, дополнительные события выключены; 0 page errors/ошибочных HTTP. Clone socketio не запускался, его недоступность не относится к production.
- На production выполнены read-only проверки существующего сотрудника: порядок Lead/Deal, поиск по последним четырём цифрам реальных номеров, сохранность остальных slots списка Усмана. Проверены list API всех 11 сайтов; новые schema/settings активны только у Таткардана. HTTPS login origin возвращает 200. На production не создавались тестовые лиды, комментарии, звонки или сообщения и не сбрасывались пароли.

Private artifacts и scripts: `/Users/g-karim/Documents/Codex/2026-09-22/new-chat/work/crm-touch-stage7-release-20261009` и `/home/frappe/validation/crm-touch-stage7-20261009`. SQL/config/auth/manifest не публикуются в Git. Изолированные проверки/checkout сохраняются; preview и validation Redis останавливаются после проверок.


### Финальная проверка Nginx

После основного cutover GET нового JavaScript выявил 404: `copytree` перенёс `0700` private build/staging каталогов на публичные frontend-каталоги. Clone HTTP/браузер работали от пользователя frappe и не обнаружили ограничение пользователя www-data. Изменены права только app frontend assets: каталоги 0755, обычные файлы 0644; код, БД и пользовательские файлы не изменялись. Через production Nginx проверены все 26 entry/preload JavaScript/CSS ресурсов — 200 с корректными content types. В release helper/runbook добавлено явное выставление режимов и требование проверки через реальный Nginx перед окончанием maintenance.

После выпуска Error Log Таткардана не содержит новых ошибок, ошибок touch tracking или подключения MariaDB; pending Touch Event — 0, maintenance и pause_scheduler выключены. Isolated preview и два validation Redis остановлены, исходные/финальные restore sites, базы, checkout и backup сохранены для восстановления.

### Русский интерфейс касаний

Исправлен 2026-10-09 после сообщения пользователя об английских настройках. Production MO от 2026-10-07 не содержал новых переводов из уже выпущенного PO: исходник и frontend сами по себе не обновляют словарь boot. Дополнены семь сообщений/кнопок и исправлены подписи «Эл. почта» и «Причина потери». Использован стандартный русский каталог Frappe, без изменения английских ключей или логики касаний.

На полной копии с Frappe 16.25.0 выполнена штатная компиляция только `crm/ru`. Native boot/API проверяют все 82 сообщения и динамические labels; русский и английский языки разделены. Реальный Chrome под существующим профилем Усмана: вкладки «Лиды»/«Сделки», поиск русских названий полей, правила задач и каналов, 0 page errors/ошибочных HTTP; переключение вкладок не меняет настройки. Четыре translation tests проходят на локальном и целевом Frappe; новый regression test проверяет сообщения из исходников после нативной компиляции MO и сохранность параметров `{0}`.

На production PO/MO заменены атомарно после сохранения старых файлов вне сервера. Добавлено 77 ключей относительно старого MO, удалённых ключей нет; изменены только две прежние подписи. Переводные caches очищены у всех 11 CRM-сайтов, native русский boot и английский fallback проверены. Снимки политик/версии настроек, представления Усмана, ролей и полных дат/числа карточек совпали до/после: 3809 лидов, 3 сделки, 3 Touch Event на момент проверки. Все подключения к БД были read-only; схема, настройки и сервисы не изменялись. Private evidence: `work/crm-touch-ru-20261009` локально и `/home/frappe/validation/crm-touch-ru-20261009` на сервере. В инструкции выпуска добавлена обязательная проверка скомпилированного перевода.
