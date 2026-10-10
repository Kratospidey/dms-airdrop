# DMS AirDrop 0.2.2

First maintenance release following acceptance into the official DankMaterialShell plugin registry. Maintainer `hthienloc` merged [registry PR #1029](https://github.com/AvengeMedia/dms-plugin-registry/pull/1029) on 2026-10-10 as [commit 444f343](https://github.com/AvengeMedia/dms-plugin-registry/commit/444f3439c915643235aee7caf45279f55fda05a8), after the final automated review reported ready with no issues. This release consolidates the existing marketplace fixes and updates version metadata and documentation.

## Improvements since v0.2.1

- Reduced idle background activity: closed/Off status reconciliation every five minutes, immediate status refresh on opening, and a one-second clock only when needed.
- Reduced background receiving checks to every 30 seconds while the popout is closed. Receiving with the popout open, active sends, pending operations and immediate cleanup retain three-second monitoring. Backend expiry, cleanup deadlines and transfer-completion handling are preserved.
- Native DMS-themed scrolling, theme-based dimensions, responsive action groups and shared-controller lifecycle handling for multiple popouts.
- Marketplace picker compatibility: missing or non-executable KDE helpers open the basic Qt picker immediately on the first selection. Enhanced-picker failures recover once to Basic, with bounded error handling and safe cancellation.
- Persistent Auto/KDE/Basic preferences. Helper detection happens inside Qt on each new selection, without additional capability subprocesses or background polling.

The prior five-minute review fixtures measured 95% fewer process launches while closed/Off and 90% fewer during quiet background receiving. These are process-count measurements, not battery-life claims or new hardware results; see [review fixes and reproduction details](REVIEW_FIXES.md). The implementation was already on `main` in commits [9aeec67](https://github.com/Kratospidey/dms-airdrop/commit/9aeec67), [97e3ad7](https://github.com/Kratospidey/dms-airdrop/commit/97e3ad7) and [3064478](https://github.com/Kratospidey/dms-airdrop/commit/3064478).

## Installation and compatibility

Open **DMS Settings → Plugins → Browse → AirDrop**, install and enable the plugin, then add its widget to your DankBar. Refresh a cached catalog if needed. Read [Marketplace setup](MARKETPLACE.md) for prerequisites, optional KDE enhancement and update/removal instructions. [Friend setup](FRIEND_SETUP.md) covers the alternative manual clone/archive installation.

The marketplace installs the frontend. It does not install Omdrop, OWL, drivers, KDE build dependencies or the optional native picker. The basic Qt picker works without a compiled helper; transfers still require a separately configured backend.

DMS 1.6.2 and Quickshell 0.3.1 are the tested baseline on CachyOS/Arch with Niri, using Qt 6.11.2 and KDE Frameworks 6.30.0. Transfers require Omdrop 0.14.1, an existing receiver/identity and compatible radio hardware; omdrop-owl 0.1.0 is the previously tested backend. Registry metadata remains limited to Arch/Niri. Other hardware, distributions, compositors and the Broadcom backend remain unverified with this frontend. See [Compatibility](COMPATIBILITY.md).

## Automated validation

The complete `python3 tests/run_checks.py` suite and the additional release audits passed after the final release changes:

- 102 Python tests and all QML syntax checks; 6 QML behavioral cases (10 including setup/cleanup).
- 20 monitoring cases and 3 native UI cases covering timing, multiple popouts, native scrolling, themes and responsive layouts.
- 20 native picker cycles, 20 KDE adapter cycles and 20 Basic picker lifecycle cycles, including selection, cancellation and failure recovery.
- Clean-source marketplace installation fixture with no compiled helper and a missing backend: immediate first-click Basic, Unicode selection, cancellation/reopening and guarded unavailable/setup behavior.
- Picker capability/fallback fixtures, including persisted preferences across three fresh Quickshell processes; controller, notification, command, DMS widget compilation and native-control preview checks.
- Public-file/privacy and manifest/resource audits, reproducible source packaging, extraction and repackaging checks.

The published GitHub release links the passing Python 3.10/3.14 CI run for its exact commit. Native/QML validation uses the development host's installed libraries and isolated fixtures; it is not a fresh OS or independent-machine test. See [Testing](TESTING.md) for scope and reproduction.

**No new physical-device transfer tests were performed for v0.2.2.** iPhone → Linux receiving and Linux → iPhone sending were previously confirmed on one development laptop before the final marketplace corrections. Those historical results are not new validation of this release. No radio activation, live receiving session, driver/network/service change or DMS restart was part of this release task.

## Upgrade notes

Finish transfers and temporary sessions before updating. Registry-managed users use DMS's plugin update controls, which obtain the repository's default branch. Manual symlink users follow the [README update instructions](../README.md#update-and-uninstall); do not run the symlink installer inside a registry-managed clone. Rebuild the optional KDE helper locally if required by Qt/KDE changes.

A plugin-only reload may retain stale QML subcomponents after a source update. If an old UI persists or loading reports `Cannot assign to non-existent property "fallbackComponent"`, finish operations and restart DMS yourself when convenient. A complete restart resolved this previously observed local cache issue. Fresh-process controller/picker compilation passes; the plugin does not restart DMS automatically. See [Troubleshooting](TROUBLESHOOTING.md).

Assets are source only: `dms-airdrop-0.2.2.tar.gz` and `dms-airdrop-0.2.2.tar.gz.sha256`. No locally compiled helper or radio binary is shipped. A checksum verifies downloaded bytes against this release, not a cryptographic publisher signature. The existing v0.2.1 tag, notes and release assets remain unchanged.

MIT licensed integration code; dependencies retain their own licenses. AirDrop is a trademark of Apple Inc. This independent integration is not affiliated with or endorsed by Apple, KDE or the DMS maintainers. Registry acceptance does not imply Apple certification or universal Linux AirDrop support.
