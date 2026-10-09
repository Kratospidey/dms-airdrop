# DMS AirDrop 0.2.1

First public source release of the DMS AirDrop integration, following the locally tested 0.2.0 sending workflow. This patch focuses on portable distribution and preserves the existing UI and transfer design.

- Dry-run-first, conflict-safe, idempotent per-user symlink installation and guarded uninstallation.
- Read-only dependency and hardware reporting; missing Omdrop/radio is clearly separate from frontend installation.
- Optional local KDE picker build with offscreen library/platform verification; basic Qt picker recovery remains available.
- Omdrop executable discovery in the upstream per-user location or PATH; portable DMS/Qt test-tool discovery.
- Public setup, compatibility, security, attribution, contributor and troubleshooting documentation.
- Explicit audited source inventory and reproducible archive with SHA-256 checksum. No local binary, private diagnostics or unapproved screenshot is shipped.

## Installation

```sh
git clone https://github.com/Kratospidey/dms-airdrop.git
cd dms-airdrop
./install.sh
./install.sh --apply
```

Then scan/enable AirDrop in DMS Settings → Plugins and add its bar widget. Keep the source clone in place. Read [Friend setup](FRIEND_SETUP.md) before configuring the separate backend.

## Compatibility and validation

DMS 1.6.2, Quickshell 0.3.1, CachyOS/Niri, Qt 6.11.2, KDE Frameworks 6.30.0 are the locally tested environment. Transfers previously worked with Omdrop 0.14.1, omdrop-owl 0.1.0 and RTL8852BE-VT/rtw89_8852bte on one laptop. Release preparation uses non-destructive tests and isolated installs; no new live transfer or driver operation is part of publication. See [Testing](TESTING.md).

Other hardware, distributions and Broadcom backend integration are not certified. Automatic cleanup uses OWL metadata and can preserve an unverifiable session for manual shutdown. The 60-minute hard receiving deadline still applies during a long send.

Assets are source only: `dms-airdrop-0.2.1.tar.gz` and `dms-airdrop-0.2.1.tar.gz.sha256`. Build the picker on your own machine. A checksum verifies downloaded bytes against this release, not a cryptographic publisher signature.

No DMS registry submission is included.
