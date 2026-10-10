# Marketplace review corrections

The [first automated review of PR #1029](https://github.com/AvengeMedia/dms-plugin-registry/pull/1029#issuecomment-6094782411) found unconditional status polling, an unnecessary one-second clock, non-native scrolling and hardcoded row dimensions. These fixes are on `main` for the registry's source checkout. The v0.2.1 tag and release assets remain immutable; this work does not create another release or claim marketplace acceptance.

## Monitoring behavior

| Situation | Behavior |
| --- | --- |
| Closed and Off/unavailable, no work queued | Initial status, then one reconciliation every 300 seconds |
| First popout opens | Immediately mark checking, synchronize time and request status |
| Off with any popout open | 15 seconds by default; 10–60 configurable |
| Receiving, sending, temporary discovery or queued session work | 3 seconds, independent of visibility |
| Status fails after known receiving | Keep 3-second reconciliation until a valid snapshot confirms Off |
| Controller reload | Read status immediately; reconcile existing jobs/session ownership |

DMS 1.6.2's `PluginPopout` assigns its object to `parentPopout`; `shouldBeVisible` is the lifecycle signal. Visible popouts register their object identity in the shared daemon. Closing/destroying one of several instances does not suspend the others. Opening a second instance while the shared refresh is pending does not create another process. Hidden component construction does not refresh.

The old `idleInterval` preference is ignored; the settings page now controls `openInterval` and explains closed/active behavior. External receiving changes while idle are detected by the next five-minute reconciliation or immediately on opening. A permanently running D-Bus watcher would add lifecycle/dependency complexity and would still need reconciliation with OWL radio state, so this change uses the reviewer's permitted slow-check path.

Static idle UI has no one-second timer. The clock resumes for active work, selections or a visible unexpired peer list and immediately synchronizes the timestamp. Freshness has a one-shot deadline, and actions synchronize time before dispatch. The backend still validates every mutation under its existing lock. Omdrop expiry and the independent five-minute session cleanup timer are unchanged.

## Measured process activity

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

Additional measured runs: an open/Off popout made 3 status calls and 9 child launches in 45 seconds (about 15 seconds apart); receiving made 5 status calls and 15 child launches in 15 seconds (about 3 seconds apart). Initial/opening checks are excluded from those windows. Temporary cleanup and operation deadlines remain backend-owned.

Reproduce with an installed Qt/DMS test runtime:

```sh
python3 tests/polling_benchmark.py --source ../baseline-checkout --output .qa/before.json
python3 tests/polling_benchmark.py --output .qa/after.json
python3 tests/polling_benchmark.py --mode open --seconds 45 --output .qa/open.json
python3 tests/polling_benchmark.py --mode receiving --seconds 15 --output .qa/receiving.json
```

## Native UI compatibility

The popout uses `qs.Widgets.DankFlickable`, which is the implementation available in the supported DMS 1.6.2. Current upstream retains that name as a compatibility shim for `DFlickable`; importing the newer `qs.DCommon` type directly would break 1.6.2. This is a deliberate baseline compatibility choice, not a custom scroll implementation. The native control supplies wheel/high-resolution wheel/pixel-delta touchpad handling, momentum and its themed scrollbar.

Device row height follows text/icon height plus `Theme.spacingM`; labels are anchored between icons. Icons use `Theme.iconSize`, `Theme.iconSizeLarge` and `Theme.spacingXS`; the progress track uses `Theme.spacingXS` and a radius bounded by `Theme.cornerRadius`. Action groups wrap at narrow widths/larger fonts, and the receiving-window label stacks instead of overlapping its dropdown. The busy animation stops with the actual popout visibility.

## Regression scope

`tests/polling_smoke.py` exercises 14 cases: closed idle/hidden construction, open/close/duplicate instances, timed receiving, countdown expiry, closed transfer completion, temporary abandonment, external activation, reload, clock resume/peer expiry, stale recovery, old preference migration, transient receiving-status failures and expired selections with a missing backend, and closed sending failures after a status timeout. Long timer deadlines are asserted, then shortened only inside specific fixtures; the separate five-minute benchmark uses real time and unchanged intervals.

`tests/ui_smoke.py` uses installed DMS controls with mocked session services: dark/light themes, 100%/150% fonts, 300/380px widths, small viewport/long lists, expanded receiving options, long names, keyboard focus, hover/selection, busy rendering, mouse wheel, high-resolution wheel, synthetic pixel-delta touchpad input and flicking. Its small C++ input injector is test-only and compiled privately; no test binary is distributed. Mock screenshots are private QA artifacts, not marketplace evidence.

No live shell reload, physical-device interaction, AirDrop transfer, driver change or independent-machine test was performed. Horizontal/vertical bar entrypoints retain the same popout; native widget base-type compilation and shared lifecycle fixtures cover integration, while a live vertical-bar placement check remains unperformed.
