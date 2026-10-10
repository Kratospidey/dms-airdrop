# Validation

## Portable checks

```sh
python3 tests/run_checks.py --portable
```

Runs the standard-library unittest suite and the explicit public-source audit. It needs Python 3.10+ on Linux; it does not require Omdrop, DMS, Qt/KDE, a compositor or Wi-Fi. Fake executables, HOME/config/runtime directories and generated fixtures are used. Assertions cover status validation, operation locks, transfer argv, preservation guards, automatic session ownership/cleanup, selection validation, installer safety, settings restoration, rollback, dependency failures and packaging boundaries.

GitHub Actions runs this tier on Python 3.10 and 3.14, then packages and checksums source. CI does not prove native GUI behavior, radio support or transfers.

## Desktop/native regression suite

```sh
python3 tests/run_checks.py
```

Requires the native build dependencies, Quickshell, Qt development tools, DMS sources and a Wayland session for the widget **compile-only** check. DMS sources are discovered under the current XDG runtime directory, or supplied via `DMS_SOURCE` pointing to the QML source directory (with DankCommon and its dependencies available). Qt tools are discovered through PATH or Qt's own installation query.

Tests build the native helper, validate application QML syntax, run QML state/selection cases, exercise the real KDE picker offscreen, and run isolated Quickshell/controller/fallback/notification/command fixtures. The controller uses fake Omdrop and systemd tools. Real installed DMS components used by tests are linked/copied into ignored local fixtures, never redistributed. No live plugin is reloaded and no real radio or transfer is started.

The widget compilation needs Wayland because DMS base classes declare PanelWindow types. It creates component factories, not a live plugin widget. `preview.py` renders actual DMS controls with mock services and a stock palette; its output is a mock preview, not a screenshot of the live application.

## Release validation scope

### v0.2.2 maintenance release

The complete `python3 tests/run_checks.py` suite and the additional release audits passed on 2026-10-10 after the final release changes:

- 102 Python tests; all application QML syntax checks; 6 QML behavioral cases (10 with setup/cleanup).
- 20 monitoring cases and 3 native UI cases, including multiple popouts, countdowns, stale status, background receiving and transfer completion.
- 20 native KDE picker cycles, 20 KDE adapter cycles and 20 Basic picker lifecycle cycles, with selection, cancellation, destruction and error recovery checks.
- Clean-source marketplace loading with no compiled helper and a missing backend: first-click Basic, Unicode selection, cancellation/reopening and unavailable/setup mutation guards.
- Picker capability/recovery coverage and saved Auto/KDE/Basic preferences across three fresh Quickshell processes.
- Controller lifecycle, notification, command, DMS widget compilation and native-control preview checks.
- Public-file/privacy auditing, manifest/resource validation and reproducible source packaging, including extraction and repackaging from the 72-file public inventory.

Installed DMS 1.6.2 components and Quickshell 0.3.1 are used for fresh-process compilation and interaction fixtures, including the real `AirDropController.qml` and `picker/FilePicker.qml`. This validates their current API together. A plugin-only reload can nevertheless retain stale QML types in an existing shell; see [the documented restart recovery](TROUBLESHOOTING.md) for the previously observed `fallbackComponent` error. No live DMS restart or plugin reload was performed for this release.

The GitHub release links the passing Python 3.10/3.14 CI run for its exact commit and provides the source checksum. No new physical-device AirDrop test was performed for v0.2.2. Earlier iPhone → Linux and Linux → iPhone results remain historical evidence on one development laptop, before the final marketplace fixes; other hardware and environments remain unverified.

### Historical v0.2.1 validation

- The Python suite includes the prior 83 tests plus 16 publication/portability cases (99 total).
- QML tests: 7 behavioral cases, 11 including setup/cleanup.
- Native picker: 20 offscreen open/cancel cycles, repeated focus, single/multiple selection with Unicode/spaces/quotes/newlines, termination and recovery.
- KDE QML adapter: 20 Process/coordinator cycles plus failed launch/destruction recovery.
- Basic Qt picker: lifecycle/reopen, parent popout closure and stale callback cases.
- Controller, command, notification and widget compile smoke harnesses exercise real QML with isolated services; no radio activity.
- Fresh source/clone validation uses a separate HOME/XDG/source path on the same development host: preview, install, repeat install, conflict refusal, disabled-confirmed uninstall, rebuild and package inspection.
- Release archives exclude .qa/.build/dist/private notes and use deterministic ownership/timestamps. SHA-256 is checked after download.

These are test scopes, not independent hardware certification. Release execution results are recorded in the GitHub release and CI runs. The older working installation had real receiving/sending and Wayland picker tests; publication does not repeat hardware tests. The new clone simulation shares the host's installed libraries and kernel.

## Optional live tests

`python3 tests/native_picker.py --wayland` opens real windows and currently uses Niri for window-manager close testing. Run it only deliberately in your own desktop session. It is not part of portable CI. File transfers, incoming/outgoing confirmation and Wi-Fi stability must be tested separately on each hardware setup, with user consent and harmless files.

Logs, fixtures, screenshots and rollback manifests stay under ignored .qa. Local historical rollback scripts require corresponding private baseline manifests; normal users should follow tagged source updates/uninstallation in the README.

## Registry submission checks after v0.2.1

v0.2.2 consolidates the post-v0.2.1 corrections, including 3 image-audit regression tests (102 Python tests total) and `tests/marketplace_smoke.py`. The latter loads an isolated source-root installation with no installer/native binary and a deliberately nonexistent backend. It checks unavailable/setup UI, blocked send/receive actions, immediate first-click Basic with no picker error, actual basic Qt selection with Unicode paths, cancellation and reopening. Its wrapper rejects every command except status and local file metadata inspection before calling the adapter.

`tests/picker_choice_smoke.py` exercises missing/non-executable/available helpers, installation after first use, enhanced process crashes, bounded fallback failure, cancellation during deferred recovery, stale callbacks, repeated opens and saved Basic/KDE/Auto preferences. Disk-backed mock DMS settings are reloaded by separate Quickshell processes. The enhanced executable in these capability tests is a protocol fixture; the existing native and KDE-adapter suites separately exercise the real helper. Capability checks run inside Qt, and the fixture asserts only expected startup status and requested enhanced-picker processes. These are offscreen tests, not live Niri focus or DMS-restart testing.

The authentic screenshot is privacy-reviewed and hash-pinned by the public audit; changed or unreviewed images are rejected. Registry schema/link validation runs using the official registry tools in an isolated virtual environment. These checks add no new live-radio or independent-machine evidence.

## Marketplace review regression checks

The full suite also runs 20 controller-monitoring cases and 3 native UI cases. These cover real popout visibility, duplicate instances, reload, stale/sample deadlines, background receiving (timed/once/forever), receiving countdowns, closed-popout job completion, external sends, pending work, temporary discovery and leftover session phases, selection expiry/cleanup, peer expiry, missing backends, native scrolling and theme-responsive rows. The monitoring suite includes one real 30-second interval; other long deadlines are asserted before fixture-only acceleration. The UI input injector uses the installed C++ compiler, pkg-config and Qt 6 development tools; it only sends synthetic events to the isolated test window.

The earlier marketplace reviews used actual five-minute before/after fixtures for both Off and background receiving to measure adapter and child-process creation, with shorter checks for open-popout cadence. Those measurements were not repeated for this documentation/version release; the monitoring regressions were rerun. The benchmark is separate from routine CI. Reproduction commands, results, native API choices and unverified live scenarios are recorded in [Marketplace review corrections](REVIEW_FIXES.md).
