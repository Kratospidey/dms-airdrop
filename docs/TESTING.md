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

For 0.2.1:

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

The immutable release above remains the baseline. Main additionally includes 3 image-audit regression tests (102 Python tests total) and `tests/marketplace_smoke.py`. The latter loads an isolated source-root installation with no installer/native binary and a deliberately nonexistent backend. It checks unavailable/setup UI, blocked send/receive actions, native failure recovery, actual basic Qt selection with Unicode paths, cancellation and reopening. Its wrapper rejects every command except status and local file metadata inspection before calling the adapter.

The authentic screenshot is privacy-reviewed and hash-pinned by the public audit; changed or unreviewed images are rejected. Registry schema/link validation runs using the official registry tools in an isolated virtual environment. These checks add no new live-radio or independent-machine evidence.

## Marketplace review regression checks

The full suite also runs 14 controller-monitoring cases and 3 native UI cases. These cover real popout visibility, duplicate instances, reload, stale/sample deadlines, receiving and closed-popout job completion, selection expiry/cleanup, peer expiry, missing backends, native scrolling and theme-responsive rows. The UI input injector uses the installed C++ compiler, pkg-config and Qt 6 development tools; it only sends synthetic events to the isolated test window.

Two actual five-minute idle runs and shorter open/receiving runs measure adapter and child-process creation. The benchmark is separate from routine CI so it does not add ten minutes to every test run. Reproduction commands, results, native API choices and unverified live scenarios are recorded in [Marketplace review corrections](REVIEW_FIXES.md).
