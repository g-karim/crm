# Exolve browser calling — local pilot

The Exolve connector adds browser calling alongside Twilio and Exotel. It does
not buy numbers, create SIP accounts, change provider routes, send SMS, or enable
provider services. Those operations remain in the Exolve account.

## Configuration

On a **local site**, install the additive schema using the normal Frappe app
installation/migration workflow. Existing sites without the schema report Exolve
as disabled. Installation alone never enables calling.

Open **Settings → Telephony → Exolve** as a System Manager or Sales Manager.
Enter the Exolve application UUID and its API key. Add each enabled CRM user and
the numeric **SIP resource ID** from Exolve's SIP card. The resource ID is different
from the SIP username. Each user and SIP resource can appear only once.

Save, then choose **Check Saved Connection** to list the application's SIP accounts
and numbers. This action uses provider read operations only. Saving a blank API
key retains the current encrypted key. Native Frappe document revision checks and
the settings API reject a stale settings form.

The server retrieves the mapped user's SIP password on demand from Exolve. The
application key stays on the server; SIP credentials are returned only to the
authenticated, enabled, permitted, mapped user with `Cache-Control: no-store`.
There is no endpoint accepting an arbitrary user's SIP resource ID.

## Calling

Use a card's phone action to open Telephony with the number filled in. It does
not place a call until the user presses **Call**. There is no permanent Exolve
button in the application header. If an active call dialog is dismissed, a
floating button at the bottom right reopens its controls. The local Telephony
workspace is described in [the communications proposal](../communications/workspaces.md).

1. After configuration, the mapped CRM user's telephony connects automatically.
   Local readiness is checked first; there is no fallback to another user.
   Registration does not dial a number or request microphone access.
2. Enter the destination and press Call. Browser microphone permission is required.
3. Use mute/unmute, hang up and the DTMF keypad during a conversation.
4. Incoming SIP sessions show Answer/Decline. Routing the purchased number to
   the SIP account must first be configured separately in Exolve.

HTTPS or a browser-trusted localhost origin is required. The connection survives
navigation between CRM cards; disabling the integration or unmounting/logging out
destroys the client. Web Locks prevent a second tab from registering the same SIP
when the browser supports that API. A tab without Web Locks retains only its own
single-call guard.

The call screen no longer offers manual Disconnect or history-refresh controls.
An earlier paused browser preference can still be cleared by manual Connect.
Only this boolean preference is stored locally.
Normal CRM navigation keeps the same client; a page reload reconnects it. Native
JsSIP transport recovery restores registration after a connection loss. A second
tab explains that the first tab owns the SIP; focusing it after the owner closes
allows reconnection. Saving Exolve settings revalidates the running client.

On the local pilot, SIP 247407 was moved from Administrator to the actual `karim`
user on 23 October. Provider configuration and historical call ownership were not
changed. Historical recording access still follows the existing participant and
mapping checks; this fix does not grant access to another operator's recordings.

The transport uses pinned `jssip@3.11.1`, also used by the published Exolve SDK.
WSS/realm/STUN defaults match Exolve Web Voice SDK 1.4.0. The published wrapper's
SIP-password localStorage mirror is deliberately not included. Credentials live
only in the active JavaScript client's memory.

Once a public (`srflx`) or relay ICE candidate exists, the session sends its offer
without waiting for unrelated interface/STUN timeouts. Host-only gathering keeps
the normal completion path. See the [JsSIP icecandidate event](https://jssip.net/documentation/api/session/#section_icecandidate).

## Journal and recordings

After a call ends the dialer checks authenticated provider statistics three times
at five-second intervals. **Refresh Call History** performs the same check
manually. The pilot reconciles the last **15 minutes**, at most **100** provider
rows. A full page produces an explicit incomplete-history message; there is no
background history importer, public webhook or scheduler in this first slice.
Leaving CRM closed for longer than the window requires a later reconciliation
feature. Browser observations never mark a server call Completed.

Only terminal statistics for the configured application and exact current-user
SIP account are accepted. Answered, busy, no-answer, cancellation, rejection and
error remain distinct. Talk duration comes from statistics `legs[].talk_time`,
in seconds, rather than total ringing-plus-talk duration. Parallel legs are not
summed. Decimal uint64 call IDs stay strings. The deterministic CRM ID includes
application and provider call identity; Twilio/Exotel/manual identities are not
renamed or reused.

Reconciliation locks remain held until database commit/rollback and use a stable
order. One transaction retry handles MariaDB snapshot conflicts, rechecking
current settings and user access. Replays update a single Call Log, and an older
snapshot cannot remove a ready recording. Existing phone lookup links a call only
to an accessible Contact, Lead or Deal. Activity and Call Log views refresh after
successful synchronization, including a late recording.

Recordings use the existing CRM player, but the server derives the provider URL
from the validated call identity. A user-supplied recording URL cannot redirect
the API key. An HTTPS CDN redirect is fetched without Bearer credentials through
the existing SSRF-protected fetcher. Downloads require current call permission,
the current mapped participant and matching application/call identity.

The observed provider format is Microsoft ADPCM WAV, which Chrome could not
decode. The Exolve browser route uses server **ffmpeg** to produce a PCM WAV
preview, preserving source channels/sample rate. It caches only the preview in
site `private/exolve_recordings/` with 0600 files; each cache/range request still
checks current access. Werkzeug serves correct 200/206 and Content-Range for
playback/seeking. The original recording remains the source for manual AI.
Conversion uses fixed WAV input, file-only protocols, 25MiB source/100MiB output
limits, a 60s timeout and atomic publication. Missing ffmpeg gives a clear error.

Exolve-controlled Call Log fields cannot be created or changed through generic
document writes. Native note/link operations remain available. Importing a call
does not enqueue paid AI analysis or change Touch Tracking adapter acceptance.

## Verification and limits

The dedicated local test site uses mocked provider responses for unit tests.
Browser checks cover registration/disconnection, second-tab exclusion, settings
and responsive layouts. An explicitly authorized real call from CRM used a known
Russian WAV as its microphone: the user confirmed hearing it, their return speech
arrived in the browser, and both directions were present in the provider recording.
The native player decoded the 34.661s PCM preview; actual playback, seeking and
HTTP ranges passed. Current validation is 445 frontend and 27 backend tests.

Physical Mac microphone capture was checked separately; the user deferred a real
conversation through that input. Real DTMF delivery and incoming routing remain
separate acceptance steps. Evidence is local to the isolated bench, not committed.

SMS is outside this implementation.

Primary references:

- [Exolve Web SDK setup](https://docs.exolve.ru/docs/ru/sdk-instructions/setting-up-web-sdk/)
- [Statistics GetList](https://docs.exolve.ru/docs/ru/api-reference/statistics-api/call-history/)
- [SIP attributes](https://docs.exolve.ru/docs/ru/api-reference/sip-api/getting-sip-attributes/)
- [Recording download](https://docs.exolve.ru/docs/ru/api-reference/call-record-api/downloading-record/)
