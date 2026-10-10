# Architecture

## Ownership

`plugin.json` declares a DMS composite: one `AirDropController.qml` daemon and
one `AirDropWidget.qml` per bar placement. The daemon is a QML Item, not a new
system daemon. It publishes its reference through the documented plugin global
variable API. Widgets use PluginGlobalVar; settings observe the same global map.
The controller's destruction clears the reference, never radio state.

`AirDropPopout.qml` and native settings only send intents to the controller.
Two popouts cannot own competing subprocesses. A disconnected screen, closed
popout, or bar recreation has no backend lifecycle effect.

## Commands

`components/Command.qml` owns one Quickshell Process for each short helper lane:
status, passive peers, submission, selected-file metadata, and diagnostics. A lane rejects overlapping
requests; each invocation creates a separate Process/timer so late signals cannot
corrupt a newer request. It waits for exit and both streams before decoding a
response, checks exit-code agreement, then destroys the invocation and its
argv/output. Its 45-second watchdog applies
only to read/submission helpers. It never owns a live transfer.

`scripts/backend.py` uses Python's standard library, argv lists and no shell.
Each read has a bounded timeout; stdout and stderr are drained concurrently and
capped at 256 KiB. All CLI stderr is mapped into non-sensitive user messages.
There are no log-dump or verbose-identity modes.

An explicit mutation is submitted with `systemd-run --user --collect
--service-type=exec` to **dms-airdrop-operation-<request-id>.service**. A private
request reservation and a submission flock reject duplicates across the launch
gap and DMS restarts. The worker waits for the submitter to release that lock,
then holds it through completion. A separate operation flock is inherited by
the child CLI. Abandoned requests are reconciled against systemd before a new
submission; a delayed worker cannot claim a removed request. A failed launch
never queues an automatic retry.

The service uses `UMask=0022`: OWL's existing polkit helper inherits it when
publishing non-secret radio PID/deadline files used by unprivileged status reads.
Plugin request/job files independently use mode 0600 inside a 0700 directory.
`KillMode=process` preserves OWL's independently timed root-owned processes
after the start command returns. Such a completed transient unit may remain
listed as inactive until Omdrop stops those processes; unique operation names
allow Stop and subsequent commands to run. No unit is enabled at login.

Requests live briefly in mode-0600 files inside mode-0700
`$XDG_RUNTIME_DIR/dms-airdrop`. The worker consumes/unlinks its request before
calling Omdrop. One atomic `job.json` holds action ID, state, phase, exit code,
count and shortened destination; selected paths are never written to it.
The worker writes no journal output. A request stranded by a launch crash may
remain private until logout; review that directory if diagnosing a launch failure.

Start/stop have a 180-second helper limit, name lookup 90 seconds, settings 20
seconds. **Sending has no added helper deadline.** Omdrop still applies its own
listener and request timeouts. On interruption the helper sends TERM to its
child group, allowing Omdrop's cancellation trap to clean its sender group;
the helper explicitly owns its command process group. There is no ordinary
"force off" or cancel-send control that could truncate the recipient's file.

## Reconciliation and races

`components/State.js` derives UI state from a validated Omdrop snapshot and
operation state. Unknown/malformed/inconsistent status never becomes Off.
The adapter independently reads the receiver's systemd LoadState/ActiveState
and the radio helper's JSON status because Omdrop suppresses errors from those
probes. Failed/unavailable probes or disagreement produce an unknown state;
a failed receiver produces an error. When both clocks are reported, the smaller
radio/receiver remaining time is used.
An in-flight mutation wins over intermediate status. A generation counter
discards polls and peer lists started before a newly submitted mutation.

Closed, idle popouts reconcile status every five minutes. The first open popout
refreshes immediately and uses a 15-second interval (10–60 configurable under
`openInterval`). The former `idleInterval` setting no longer controls background
activity. Active windows, jobs and temporary-session work retain three-second
polls, even when every popout is closed. A failed probe after known receiving
or a job keeps the fast reconciliation cadence until a valid snapshot confirms
the session/job has ended.

Only one controller polls, regardless of monitors. Each popout registers its
identity using DMS `parentPopout.shouldBeVisible`, unregistering on close,
destruction or controller replacement. Component existence alone is not
visibility. Opening marks the sample as checking until the shared status request
finishes; overlapping opens share that request. A one-shot freshness deadline
invalidates a sample if reconciliation stalls, without a permanent idle clock.

The one-second clock runs for active sessions/jobs, selected files or a visible
unexpired peer list. It synchronizes immediately when resumed or when the
popout opens. Peers are polled every five seconds only while files are selected
and a session is active. Name resolution remains explicit. The clock only
interpolates backend-reported seconds; after zero it says Checking window expiry.
The countdown never changes backend state. A separate finite backend timer
handles abandonment of plugin-owned sending sessions. Stale snapshots disable actions.

The worker rechecks status, external Omdrop send markers, file readability,
duration and the target's presence under the operation lock. Stop never uses
`--force` and requires a post-command snapshot with BOTH receiver and radio off.
Start similarly requires receiver and discoverability on. Partial success is
an error, even with exit code zero.

The plugin cannot atomically lock independent CLI users or incoming requests;
Omdrop's own identity/stop guards remain essential. Its timer and receive-once
watcher can force the radio off during a transfer. Sending in once mode, an
expired window or with <120 seconds reported is refused. Longer windows can
still expire during large sends; no unrequested extension occurs.

## Reload, crash and disable

- Popout close/monitor removal: no command cancellation.
- Plugin reload/DMS crash or restart: transient operation unit keeps running;
  next controller reconciles runtime summary, flock and Omdrop state.
- Plugin disable: stops QML polls and short read helpers. An operation already
  requested intentionally completes in its finite service. A receiving window
  remains owned by Omdrop. No automatic radio stop or future startup occurs.
- Logout, user-service manager shutdown, or killing the operation unit: may
  interrupt a transfer. A stale running summary with no operation lock is shown
  as Interrupted, never Complete. Normal timed receiving remains Omdrop's concern.
- A failed launch with no operation result is reported as unconfirmed after
  reconciliation; the plugin does not blindly resubmit it.

## Preservation boundaries

Before on/off, verify the audited CLI version, exact rendered service template,
absence of a legacy drop-in rewrite, the service manager's ability to locate the
receiver, and existing self-signed pair metadata.
This prevents known Omdrop implicit setup/migration paths; concurrent external
configuration edits between checks and execution cannot be made atomic by a UI.
The plugin never reads private keys or invokes setup, identity management,
driver installation, firewall modification, NetworkManager or privileged tools.
The normal Omdrop CLI owns existing polkit radio operations when the user asks.

Name and Everyone changes are explicit, off-only, backed up first and verified
afterwards. Rollback compares a last-applied hash to avoid overwriting later
independent edits. Folder changes are excluded because their CLI path modifies
the protected receiver service.

## Automatic sending (0.2.0)

Accepted files pass the existing read-only metadata lane. Only then does the
controller submit `prepare-send`. Existing receiving is reused; Off starts a
finite normal Omdrop window. A private token/fingerprint records ownership.
The window has a 60-minute hard cap and a five-minute abandonment timer, so no
receiver watcher restart or deadline extension is needed at send time.

The abandonment command waits on the existing submission/operation locks.
A send keeps those locks until it finishes, then cleans its own matching
session. Cleanup checks exact systemd invocation/deadline and OWL/window
metadata, external sends and incoming connections before ordinary `off`.
Changes, unreadable state or active connections preserve receiving and expose
a manual recovery message. No atomic Omdrop compare-and-stop API exists;
external CLI/incoming races remain a documented limitation.

Manual Receive relinquishes temporary ownership. A resumed controller cleans
an idle owned discovery session whose in-memory selection was lost, while
running operations survive. Plugin disable does not interrupt operations; the
finite abandonment timer and Omdrop expiry remain. No permanent or privileged
plugin service is installed.

## Notifications and privacy

Only new terminal outgoing results and errors notify. Initial reconciliation
is silent. Completed jobs never render a persistent result card; failures and
interrupted jobs do. The installed DMS ToastService provides category dismissal
and timer control. Controller-owned QML timers give its own success category
3.5 seconds without affecting unrelated notifications; destruction removes its
own queued/current toasts. Incoming success remains Omdrop's existing journal
watcher's responsibility (native eight-second notification, no duplicate).

Selection exists in controller memory for five minutes and clears on submission.
The brief private request is consumed before CLI execution. No selected paths
are written to job summaries, preferences or session ownership records.

## Picker lifecycle

`picker/FilePicker.qml` retains the 0.1.1 serial/token coordinator: one session,
launch watchdog, deferred disposal and centralized accept/cancel/failure cleanup.
It belongs to the shared controller, never a popout or monitor widget.

`workflow/KdePickerSession.qml` owns a short-lived native Qt Widgets process.
`native/picker.cpp` embeds KDE KFileWidget, with icon view and inline previews
enabled. KDE owns directory browsing, sorting, zoom, thumbnail generation and
selection. DMS palette colors are passed as one JSON argv value. The helper
returns fully encoded URLs as JSON, never newline-delimited filenames. It
accepts only local files; the existing JS conversion and backend validation
remain independent checks.

Stdin carries focus/cancel requests and serves as a parent lifeline. Parent
termination and EOF close the dialog. The process isolates KDE config/state,
recent-path and thumbnail-cache writes in a private temporary runtime folder;
normal exit removes it. A SIGKILL can leave that folder until logout. The QML
watchdog and destruction callbacks allow immediate retry after failure.

The tested independent Qt Quick dialog remains as a basic recovery option.
Session and popout component URLs are cache-busted when their owner is
recreated. The native session and state helper use a fresh workflow module to
avoid an already-cached implicit-module inventory. The widget Loader forwards
controller, height and close properties. A plugin-only reload therefore updates
the visible popout and chooser without restarting the shell.

See [compatibility](COMPATIBILITY.md), [testing](TESTING.md) and
[release notes](RELEASE_0.2.1.md) for the public support boundaries.
