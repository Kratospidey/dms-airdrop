# Set up DMS AirDrop on another laptop

For registry-managed clones, use [Marketplace setup](MARKETPLACE.md): DMS clones the frontend but does not run this manual symlink installer.

## 1. Check the laptop first

You need a Linux desktop running DMS and Quickshell. This release was tested on CachyOS with Niri; Fedora, Ubuntu, Debian, other compositors and other CPU architectures are not verified.

Read [Compatibility](COMPATIBILITY.md). A normal Wi-Fi connection alone does not establish AWDL compatibility. You can install this interface before configuring AirDrop, but file transfer will remain unavailable.

## 2. Get the source and inspect dependencies

```sh
git clone https://github.com/Kratospidey/dms-airdrop.git
cd dms-airdrop
./install.sh
```

Python 3.10+ is needed to run the installer. Its report separates blocking frontend requirements from backend and picker warnings. It reads interface/chipset/driver/channel information without printing SSIDs or MAC addresses, and uses the radio helper's unprivileged prerequisite probe. It never starts the radio.

On Arch/CachyOS these are the package names corresponding to the installed, tested toolchain. Review the command and run it yourself only if needed; the installer never runs a package manager:

```sh
sudo pacman -S --needed git python base-devel cmake qt6-base qt6-declarative kio kiconthemes breeze breeze-icons kio-extras
```

DMS and Quickshell should be installed following [DMS instructions](https://danklinux.com/docs/dankmaterialshell/installation). systemd and iproute2 provide the operation manager and `ss`. Optional `iw` and `pciutils` enrich read-only hardware reporting. Omdrop/OWL dependencies belong to their upstream setup, not the package command above. The package names were checked against the development installation; this task did not reinstall packages or test a fresh OS installation.

On another distribution, use its documentation to find Qt 6 Widgets/Quick/Dialogs development files, KDE Frameworks 6 KIO/IconThemes, CMake and a C++17 toolchain. Do not run the Arch command there. This project does not yet provide tested apt/dnf recipes.

## 3. Install the interface

```sh
./install.sh --apply
```

It builds the optional native picker when dependencies are present. If dependencies are missing, file selection uses the basic picker automatically. To deliberately skip building:

```sh
./install.sh --apply --picker basic
```

In DMS Settings → Plugins, scan and enable AirDrop, then add the widget to the bar. Keep the source directory where it is: the plugin is a symlink to it. You can safely repeat the install command for this same clone.

**Send Files** opens Basic directly when the KDE helper is missing or not executable. Basic supports local multi-selection but does not promise thumbnails. Install the native dependencies and run `python3 scripts/build-picker.py` later; Auto mode detects the helper on the next selection without reloading DMS. The plugin's **File picker** setting can persistently select Basic or prefer KDE. An unexpected enhanced-picker failure automatically recovers once to Basic.

## 4. Configure AirDrop separately

If Omdrop already works, preserve it. Otherwise review:

- [Omdrop CLI and receiver](https://github.com/brentkearney/omdrop-plugin): this frontend currently requires **0.14.1** and its upstream source/service layout.
- [omdrop-owl](https://github.com/t4t5/omdrop-owl): non-Apple Wi-Fi backend with a narrow tested hardware list.
- [omdrop-awdl](https://github.com/brentkearney/omdrop-awdl): specific Apple Broadcom hardware; untested with this frontend.

Upstream Omdrop instructions target Omarchy and may offer driver installation. Do not blindly run that setup on unrelated hardware. Configure the appropriate stack deliberately, including the existing receiver service and identity, then run `./install.sh check` again. DMS AirDrop will not provision certificates or rewrite a receiver service on your behalf.

An OWL probe with no missing prerequisites is encouraging but does not prove a successful transfer. Other adapters may require experimental opt-in; do not opt in without understanding the upstream hardware notes. Never send keys, certificates or identity records in a bug report.

## 5. Try a small transfer

When your backend is configured and you choose to test it, open AirDrop on your phone. Select **Send Files**, pick a harmless small file, choose the phone and send. Accept on the phone and verify its contents. Check that the plugin-owned temporary window closes. For receiving, choose a short Receive window and share a harmless file from the phone. Turn Off after testing and check ordinary Wi-Fi still works.

See [Troubleshooting](TROUBLESHOOTING.md) if any stage fails. Hardware tests are manual, never part of installation or CI.

## Install from a release archive

Download `dms-airdrop-0.2.1.tar.gz` and its `.sha256` from the [v0.2.1 release](https://github.com/Kratospidey/dms-airdrop/releases/tag/v0.2.1). In the download directory:

```sh
sha256sum -c dms-airdrop-0.2.1.tar.gz.sha256
tar -xzf dms-airdrop-0.2.1.tar.gz
cd dms-airdrop-0.2.1
./install.sh
./install.sh --apply
```

The archive is source only. It includes neither a radio driver nor a helper compiled for someone else's laptop. Extract it into a permanent location before installing. For a later archive update, finish operations, disable the plugin, uninstall the old clone's symlink, install from the new permanent directory, then enable it again. Keep the old source until the update is verified.

## Remove the interface

Finish transfers, turn temporary receiving off, and disable the plugin in DMS:

```sh
./install.sh uninstall
./install.sh uninstall --apply --disabled
```

The clone and all backend software/data remain. See the README for optional, guarded restoration of plugin-edited name/visibility settings.
