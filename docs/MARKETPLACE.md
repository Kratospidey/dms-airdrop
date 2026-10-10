# DMS marketplace installation

This page describes the registry installation path for DMS 1.6.2. See [submission status](REGISTRY_READINESS.md); marketplace availability requires the registry PR to be merged. Until then use the [manual installation guide](FRIEND_SETUP.md).

## Three separate readiness levels

| Level | What is available |
| --- | --- |
| Frontend installed | DMS has the repository, reads the root plugin.json and can load the AirDrop widget/controller when its normal Qt/Quickshell runtime is present |
| Enhanced picker available | You have explicitly built the optional KDE helper locally using the installed Qt/KF6 development packages |
| AirDrop operational | Omdrop 0.14.1, its existing receiver/identity and compatible radio hardware/backend are separately configured |

The registry entry initially declares Arch/Niri, based on the CachyOS/Niri development setup. It does not certify every Arch laptop or Wi-Fi adapter. Only omdrop-owl is tested by this frontend; automatic cleanup relies on its state metadata.

## What DMS installs

In DMS 1.6.2, the plugin manager clones the repository into:

```text
${XDG_CONFIG_HOME:-$HOME/.config}/DankMaterialShell/plugins/dmsAirDrop
```

This plugin uses the repository root, so no monorepo path or install-time symlink is needed. The normal Git checkout includes the full tracked repository, preserves tracked executable modes and uses the repository default branch; the manager records the installed commit in its plugin lockfile. It does not select the v0.2.1 release archive automatically.

The audited installation path does **not** run install.sh, execute a custom post-install hook, compile a native helper or install packages listed in registry dependencies. Those strings communicate prerequisites; they are not a package-manager transaction. The root QML and Python files already use relative resource paths and require no generated configuration.

Source references: [DMS v1.6.2 plugin manager](https://github.com/AvengeMedia/DankMaterialShell/blob/v1.6.2/core/internal/plugins/manager.go), [Git clone implementation](https://github.com/AvengeMedia/DankMaterialShell/blob/v1.6.2/core/internal/plugins/registry.go), [server install handler](https://github.com/AvengeMedia/DankMaterialShell/blob/v1.6.2/core/internal/server/plugins/install.go), and [plugin discovery](https://github.com/AvengeMedia/DankMaterialShell/blob/v1.6.2/quickshell/Services/PluginService.qml).

After acceptance, install AirDrop through DMS Settings → Plugins → Browse, enable it and add the widget to the bar. The manual GitHub installer remains a separate alternative. Avoid installing both copies with the same plugin ID.

## Basic picker on a fresh registry clone

No compiled helper is distributed. On the first **Send Files** attempt without a native helper, the native launch fails or reaches its six-second launch watchdog; the popout shows a recoverable picker error. Choose **Use basic file picker**. The basic picker opens a separate Qt file dialog and supports local multi-selection, cancellation and reopening. This choice lasts for the controller's lifetime; after a plugin reload, the native picker is tried again. The fallback does not promise thumbnails.

The popout provides a **Setup guide** button when the backend or picker is unavailable. No compiler, package manager or privileged command is launched by choosing the fallback.

## Enable the KDE thumbnail picker

Install build dependencies yourself using [Friend setup](FRIEND_SETUP.md), then run:

```sh
cd "${XDG_CONFIG_HOME:-$HOME/.config}/DankMaterialShell/plugins/dmsAirDrop"
./install.sh check
python3 scripts/build-picker.py
```

`check` only reports prerequisites (with temporary dependency-probe files). The build command explicitly compiles `.build/picker/dms-airdrop-picker` inside this installed clone and performs an offscreen loader check. It does not start discovery or alter the radio. Reload only the AirDrop plugin when idle if the basic picker was already selected, so the controller tries the new helper.

Do **not** run `./install.sh --apply` inside a registry-managed clone: that command is for creating the separate manual symlink installation and intentionally refuses to overwrite DMS's actual directory. `./install.sh check` and `scripts/build-picker.py` are safe to reuse as documented.

The helper can need rebuilding after Qt/KDE changes or if a DMS update replaces the checkout. A missing helper always retains the same explicit basic-picker recovery path.

## Missing Omdrop or radio backend

The QML frontend still loads. Missing Omdrop produces **Backend unavailable**, setup guidance and disabled receive/send execution. Choosing local files is possible, but backend mutations remain guarded. Failed or inconsistent radio status is displayed as unknown/error; it is never represented as a successful operational setup.

Configure [Omdrop](https://github.com/brentkearney/omdrop-plugin) 0.14.1 and a compatible [omdrop-owl](https://github.com/t4t5/omdrop-owl) installation deliberately, following their hardware guidance. This frontend does not install drivers, configure firewall rules, regenerate identities, rewrite receiver services or enable experimental hardware profiles.

## Updates and removal

Finish transfers, close temporary receiving sessions and disable the plugin before removal or replacing its source. Use DMS's own update/remove controls for a registry-managed installation. Its manager removes the installed clone and lockfile entry; the locally built helper is inside that clone and is removed with it. External Omdrop/OWL packages, identities and received files are outside that operation. DMS/plugin preference cleanup is separate from backend removal.

The manual installer's uninstall command removes only its own symlink and intentionally refuses a registry-managed directory. Do not substitute it for DMS's Remove action. Keep any independently edited files backed up before a DMS update/removal.

## Verification scope

The marketplace fixture copies the audited repository files into an isolated XDG plugin directory, without running the installer or building a helper. It loads the actual popout/controller using installed DMS components with mock session services, injects a nonexistent backend, checks mutation guards and setup text, then exercises missing-native failure followed by basic-picker selection/cancel/reopen. A separate public clone check verifies manifest paths and executable modes.

This tests frontend behavior on the development host. It does not reproduce a new user's complete OS, certify new hardware or run a live AirDrop transfer. Prior transfer evidence and exact tested versions are in [Compatibility](COMPATIBILITY.md).
