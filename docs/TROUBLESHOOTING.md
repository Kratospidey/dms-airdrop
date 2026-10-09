# Troubleshooting

Start with `./install.sh check`. It is read-only and never starts AirDrop. Keep raw logs private until reviewed; share the minimum necessary, with identities and file paths removed.

| Symptom | Check or recovery |
| --- | --- |
| Plugin not listed | Confirm the symlink points to the retained clone under `${XDG_CONFIG_HOME:-$HOME/.config}/DankMaterialShell/plugins/dmsAirDrop`. Scan in DMS Settings → Plugins. Check DMS/Quickshell versions. |
| Plugin enabled but no bar icon | Add AirDrop to your DankBar layout. Installer does not edit it. |
| Old UI after update | Finish operations, disable/re-enable the plugin. Restart DMS yourself only when convenient if component caches persist. |
| Backend missing | Configure Omdrop 0.14.1 separately. Its executable is discovered first in `~/.local/bin`, then PATH. No setup runs automatically. |
| Unsupported version or preservation error | Keep the audited CLI version and upstream layout. Compare your receiver setup against upstream yourself; don't bypass guards or overwrite a working service. |
| Radio helper missing | Review the correct hardware backend's upstream instructions; frontend installation is not a driver installation. |
| Native picker build fails | Run `python3 scripts/build-picker.py` for CMake/compiler diagnostics. Install the appropriate Qt6/KF6 development packages, or install with `--picker basic` and use the UI's basic recovery option. |
| Helper stopped loading after Qt/KDE upgrade | Rebuild locally. Release binaries are not distributed. |
| No thumbnails | Confirm native helper is used, increase icon size if needed, and check KIO thumbnail plugins for the file type (e.g. kio-extras). The basic fallback does not promise previews. |
| No nearby devices | Open AirDrop/share sheet on the recipient, confirm its visibility, move closer, refresh. Use name lookup explicitly; unnamed peers can still appear. |
| Channel error | OWL shared mode needs channel 6, 44 or 149. Read upstream guidance and decide on network changes yourself; the installer does not change channels. |
| Bluetooth wake failure | Check Bluetooth availability/permissions through your normal desktop tools; open the recipient's AirDrop screen and retry. |
| Receive fails or times out | Check receiver/radio diagnostics and upstream firewall requirements. Do not disable your firewall globally. No rules are changed by this plugin installer. |
| Send times out | Recipient may not be listening or may decline. Open its AirDrop sheet and retry a small harmless file. Backend listener timeouts still apply. |
| Temporary receiving remains on | Cleanup could not prove ownership or saw active connections. Wait for transfers, then use Turn Off. Never force-stop a transfer merely to clear the UI. |
| Wi-Fi connectivity changes | Stop new transfers; follow the radio backend's hardware-specific recovery notes. The frontend does not reload drivers, restart NetworkManager or repair radio profiles. |
| Uninstall refused | Finish active operations, disable the plugin, then pass `--disabled`. A foreign symlink/directory is intentionally preserved; inspect it manually. |

Useful read-only checks include `omdrop version`, `omdrop status --json` and `/usr/lib/omdrop/omdrop-discoverable probe --json`. Unlike the sanitized installer report, raw status can expose device name or folder paths. Omdrop's older doctor may still contain Broadcom-specific checks; interpret it alongside the actual backend probe.

Report reproducible frontend problems in [GitHub Issues](https://github.com/Kratospidey/dms-airdrop/issues). Include version numbers, distribution/compositor, chipset/driver and the exact failing step. Do not attach certificates, private keys, validation records, full receiver logs, personal files, MAC addresses or SSIDs.
