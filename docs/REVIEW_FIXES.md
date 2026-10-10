# Marketplace review corrections

The [first automated review of PR #1029](https://github.com/AvengeMedia/dms-plugin-registry/pull/1029#issuecomment-6094782411) found unconditional status polling, an unnecessary one-second clock, non-native scrolling and hardcoded row dimensions; commit `9aeec67` addressed those findings. The [second review](https://github.com/AvengeMedia/dms-plugin-registry/pull/1029#issuecomment-6095267285) requested slower status checks while receiving with the popout closed. The behavior below includes that correction. Fixes are on `main` for the registry's source checkout. The v0.2.1 tag and release assets remain immutable; this work does not create another release or claim marketplace acceptance.

## Monitoring behavior

| Situation | Behavior |
| --- | --- |
| Closed and Off/unavailable, no work queued | Initial status, then one reconciliation every 300 seconds |
| First popout opens | Immediately mark checking, synchronize time and request status |
| Off with any popout open | 15 seconds by default; 10–60 configurable |
| Receiving or owned temporary discovery, closed with no pending work | 30 seconds |
| Receiving or owned temporary discovery, any popout open | 3 seconds |
| Sending, backend cleanup or queued preparation/cleanup/operation | 3 seconds, independent of visibility |
| Status fails after known receiving, no known operation | Keep receiving cadence: 30 seconds closed, 3 seconds open |
| Status fails with an unconfirmed active operation | Keep 3-second reconciliation until backend worker/send flags confirm completion |
| Controller reload | Read status immediately; reconcile existing jobs/session ownership |

DMS 1.6.2's `PluginPopout` assigns its object to `parentPopout`; `shouldBeVisible` is the lifecycle signal. Visible popouts register their object identity in the shared daemon. Closing/destroying one of several instances does not suspend the others. Opening a second instance while the shared refresh is pending does not create another process. Hidden component construction does not refresh.

The old `idleInterval` preference is ignored; the settings page now controls `openInterval` and explains closed/active behavior. External receiving changes while idle are detected by the next five-minute reconciliation or immediately on opening. A permanently running D-Bus watcher would add lifecycle/dependency complexity and would still need reconciliation with OWL radio state, so this change uses the reviewer's permitted slow-check path.

Static idle UI has no one-second timer. The clock resumes for active work, selections or a visible unexpired peer list and immediately synchronizes the timestamp. Freshness has a one-shot deadline, and actions synchronize time before dispatch. The backend still validates every mutation under its existing lock. Omdrop expiry and the independent five-minute session cleanup timer are unchanged.

### Second-review state audit

- `active` is receiver/radio availability. `lastKnownActive` preserves that fact across failed status reads. Neither implies an operation: quiet receiving uses 30 seconds closed, including timed, once and externally enabled forever windows.
- `busy` covers a pending UI action, its submitting helper, the backend worker/queue lock and external sends. `lastKnownBusy` keeps three-second checks after an unreadable/timeout result; authoritative `busy` and `external_send` flags clear it even if the receiver status probe failed. Ordinary receiving reports both flags false.
- `temporarySession` is ownership, not activity. Owned discovery uses the receiving cadence; leftover `sending`, `cleaning` or `cleanup-failed` metadata cannot pin fast polling after the worker ends. Live sends/cleanup hold the backend lock, so `busy` already supplies fast polling.
- `prepareRequested` and `cleanupRequested` represent immediate queued work and retain three seconds. Once submitted, the pending action and then backend lock take over until completion. Selection abandonment still dispatches cleanup immediately; the independent backend timer remains at 300 seconds.

Opening marks status as checking and refreshes immediately, regardless of the remaining background interval. Closing the final receiving popout returns to 30 seconds; closing one of several does not. The local one-second clock keeps the receiving countdown accurate between samples and shows **Checking window expiry** after zero. A successful response uses the same timestamp for the sample and clock, avoiding an extra displayed minute at an exact minute boundary. The clock never extends or closes a backend window. A closed popout may learn that receiving ended on its next check (up to 30 seconds, plus command latency); opening refreshes immediately. A successful background snapshot becomes stale after 45 seconds without another sample, disabling actions; a failed probe disables actions immediately. Monitoring continues and a successful sample restores availability. Known sends keep three-second checks through completion, preserving the existing result-notification window.

Peer discovery remains its existing five-second check only while files are selected in an active session. No status work was moved into that timer, another daemon or a service; quiet background receiving with no selection runs only the 30-second status checks.

## Measured process activity — first review

Measured on the development host on 2026-10-10 with `tests/polling_benchmark.py`. Both idle runs lasted 300 actual seconds after excluding the initial status. The baseline source was commit `ac6da9c` (same controller as the reviewed `1f43172`). The new run used the corrected controller copied into a frozen test tree.

The actual Quickshell controller launches the actual Python adapter with isolated executable paths. Each status check really spawns three fixture child processes representing Omdrop, systemctl and the radio helper. Measurements count those successful child launches and the adapter invocations. The fixtures never invoke real radio/systemd tools. Additional subprocesses inside a real Omdrop installation are not measured or claimed here.

| Five-minute closed/Off run | Before | After |
| --- | ---: | ---: |
| Backend status invocations | 20 | 1 |
| Child processes spawned by those calls | 60 | 3 |
| Combined adapter + child processes | 80 | 4 |
| Backend and child CPU seconds | 1.6155 | 0.0765 |
| Total isolated QS/process-tree CPU seconds, including startup | 1.9577 | 0.2652 |
| Peak child-process RSS (KiB) | 72,944 | 73,304 |
| Changes to the controller timestamp | 320 | 2 |

Process creation fell **95%**. Total fixture CPU time fell about **86%**; memory remained approximately unchanged. The two timestamp changes after the fix came from requesting/completing the slow status check, not one-second ticks. CPU values are fixture measurements, not a laptop battery-life estimate or live Omdrop benchmark.

Additional first-review runs: an open/Off popout made 3 status calls and 9 child launches in 45 seconds (about 15 seconds apart); receiving at that revision made 5 status calls and 15 child launches in 15 seconds (about 3 seconds apart). The second-review change below supersedes that closed-receiving rate. Initial/opening checks are excluded from those windows. Temporary cleanup and operation deadlines remain backend-owned.

Reproduce with an installed Qt/DMS test runtime:

```sh
python3 tests/polling_benchmark.py --source ../baseline-checkout --output .qa/before.json
python3 tests/polling_benchmark.py --output .qa/after.json
python3 tests/polling_benchmark.py --mode open --seconds 45 --output .qa/open.json
```

## Measured process activity — second review

The background-receiving comparison uses the same real controller/adapter fixture on 2026-10-10, with no popout, selected files, owned discovery session or pending operation. Both measurement windows last **300 real seconds**, excluding one initial status call. The baseline is the second review's `9aeec67`; the corrected run uses a frozen copy of the new controller. Status launches real child executables that return fixture data, never host radio/systemd commands.

| Five-minute closed/receiving run | Before (3 seconds) | After (30 seconds) |
| --- | ---: | ---: |
| Backend status invocations | 100 | 10 |
| Child processes spawned by those calls | 300 | 30 |
| Combined adapter + child processes | 400 | 40 |

This is **90% fewer process launches**, with ongoing reconciliation and a locally ticking countdown. Counts cover the adapter and its three direct fixture children; they do not estimate subprocesses inside a real Omdrop installation or an owned session's additional fingerprint checks. The earlier closed/Off reduction remains 95%. Neither figure is a battery-life claim.

Reproduce from the corrected checkout (the archive is a private baseline fixture):

```sh
mkdir -p .qa/receiving-baseline
git archive 9aeec67 | tar -x -C .qa/receiving-baseline
python3 tests/polling_benchmark.py --source .qa/receiving-baseline --mode receiving --seconds 300 --output .qa/receiving-before.json
python3 tests/polling_benchmark.py --mode receiving --seconds 300 --output .qa/receiving-after.json
python3 tests/run_checks.py
```

Full local validation passed: 102 Python tests (including existing backend expiry, cleanup-lock, long-transfer and ownership preservation cases), all QML syntax/behavior checks, 20 monitoring cases, 3 native UI cases, 20 native-picker cycles, 20 KDE-adapter cycles, and controller, marketplace, picker lifecycle, notification, command, widget compilation and preview checks. Public-file auditing also passed. No backend worker, independent timer or transfer implementation was changed.

## Native UI compatibility

The popout uses `qs.Widgets.DankFlickable`, which is the implementation available in the supported DMS 1.6.2. Current upstream retains that name as a compatibility shim for `DFlickable`; importing the newer `qs.DCommon` type directly would break 1.6.2. This is a deliberate baseline compatibility choice, not a custom scroll implementation. The native control supplies wheel/high-resolution wheel/pixel-delta touchpad handling, momentum and its themed scrollbar.

Device row height follows text/icon height plus `Theme.spacingM`; labels are anchored between icons. Icons use `Theme.iconSize`, `Theme.iconSizeLarge` and `Theme.spacingXS`; the progress track uses `Theme.spacingXS` and a radius bounded by `Theme.cornerRadius`. Action groups wrap at narrow widths/larger fonts, and the receiving-window label stacks instead of overlapping its dropdown. The busy animation stops with the actual popout visibility.

## Final picker compatibility correction

The [third automated review marked the submission ready](https://github.com/AvengeMedia/dms-plugin-registry/pull/1029#issuecomment-6095628283), while identifying the first-click native-helper failure on a fresh marketplace clone. New selections now call Qt's supported [`StandardPaths.findExecutable`](https://doc.qt.io/qt-6/qml-qtcore-standardpaths.html#findExecutable-method) with the absolute helper path before creating a dialog. Missing/non-executable helpers select Basic immediately. This is an in-process filesystem check with no subprocess, timer, watcher or cached failure result; installation or compilation is noticed on the next selection.

The supported DMS `SelectionSetting` stores `filePicker` as Auto, KDE or Basic through its normal plugin preferences. Auto and KDE prefer the enhanced helper and permit safe fallback; Basic forces the standard dialog. Failed enhanced sessions invalidate their old token, dispose the old session and make one deferred Basic attempt. Repeated clicks focus/deduplicate, cancellation cancels queued recovery, and a failed Basic attempt stops with the existing retry UI. Transient recovery never overwrites the saved preference.

`tests/marketplace_smoke.py` copies only public source into a separate XDG installation, explicitly asserts that `.build` is absent, and verifies that the first click opens an actual Basic dialog within two seconds without a picker error. Its real controller also exercises Unicode selection, cancellation/reopening and missing-backend mutation guards. `tests/picker_choice_smoke.py` adds capability/recovery fixtures for executable and non-executable helpers, helper installation after first use, real fixture-process crashes, launch watchdog recovery, fallback failure, cancellation during recovery, stale callbacks, repeated opening and persistent preferences across three fresh Quickshell processes. It asserts exactly the expected startup status calls and requested enhanced-picker launches. Real KDE widget and adapter tests remain separate from this protocol fixture.

These are offscreen tests using installed Qt/DMS libraries and isolated backend/settings fixtures; no new live Wayland focus test or DMS restart is claimed. The status-polling and native-scrolling policies above are unchanged, as are Omdrop/OWL, the receiver, backend expiry/cleanup, transfers and the v0.2.1 tag/assets. The correction is delivered on the registry's `main` source checkout; the original release archive is not rewritten.

The complete `python3 tests/run_checks.py` run passed on 2026-10-10: 102 Python tests, all QML syntax/behavior checks, 20 monitoring cases, 3 native UI cases, clean-source marketplace and picker-choice/restart fixtures, native picker/adapter cycles, controller and notification checks. Both official registry validators also passed locally; the registry entry itself is unchanged.

## Regression scope

`tests/polling_smoke.py` exercises 20 cases: closed idle/hidden construction; Off and receiving open/close/duplicate instances; timed/once/forever background receiving; countdown expiry; closed transfer completion; temporary abandonment; external activation; reload; clock resume/peer expiry; stale recovery while Off and receiving; old preference migration; transient receiving-status failures; expired selections with a missing backend; closed sending failures after a status timeout; quiet temporary discovery/leftover session phases; pending work/cleanup priority; and external-send recovery. One case waits for a real 30-second status interval and asserts the clock continues without three-second process launches. Other long timer deadlines are asserted, then shortened only inside specific fixtures; the separate five-minute benchmarks use real time and unchanged intervals.

`tests/ui_smoke.py` uses installed DMS controls with mocked session services: dark/light themes, 100%/150% fonts, 300/380px widths, small viewport/long lists, expanded receiving options, long names, keyboard focus, hover/selection, busy rendering, mouse wheel, high-resolution wheel, synthetic pixel-delta touchpad input and flicking. Its small C++ input injector is test-only and compiled privately; no test binary is distributed. Mock screenshots are private QA artifacts, not marketplace evidence.

No live shell reload, physical-device interaction, AirDrop transfer, driver change or independent-machine test was performed. Horizontal/vertical bar entrypoints retain the same popout; native widget base-type compilation and shared lifecycle fixtures cover integration, while a live vertical-bar placement check remains unperformed.
