# Troubleshooting

Start with `./install.sh check`. It is read-only and never starts AirDrop. Keep raw logs private until reviewed; share the minimum necessary, with identities and file paths removed.

| Symptom | Check or recovery |
| --- | --- |
| Plugin not listed | AirDrop is in the official registry; refresh a cached DMS catalog and search under Settings → Plugins → Browse. For manual installation, confirm the symlink points to the retained clone under `${XDG_CONFIG_HOME:-$HOME/.config}/DankMaterialShell/plugins/dmsAirDrop`, then Scan for Plugins. Check DMS/Quickshell versions. |
| Plugin enabled but no bar icon | Add AirDrop to your DankBar layout. Installer does not edit it. |
| Old UI after update | A plugin-only reload can retain stale QML subcomponents. Finish transfers and temporary sessions, then restart DMS yourself when convenient if the old components persist. |
| `Cannot assign to non-existent property "fallbackComponent"` after update | A stale cached picker type can conflict with the updated controller. A complete DMS restart resolved this observed local issue. Finish operations before restarting; the plugin does not restart the shell automatically. Fresh-process controller/picker compilation is covered by automated tests. |
| Backend missing | Configure Omdrop 0.14.1 separately. Its executable is discovered first in `~/.local/bin`, then PATH. No setup runs automatically. |
| Unsupported version or preservation error | Keep the audited CLI version and upstream layout. Compare your receiver setup against upstream yourself; don't bypass guards or overwrite a working service. |
| Radio helper missing | Review the correct hardware backend's upstream instructions; frontend installation is not a driver installation. |
| Native picker build fails | Basic works immediately without the helper. Build later with `python3 scripts/build-picker.py` after installing Qt6/KF6 development packages. Auto detects the new executable on the next selection. |
| Helper stopped loading after Qt/KDE upgrade | A failed enhanced session recovers once to Basic. Rebuild locally, or save Basic under File picker settings. Release binaries are not distributed. |
| Basic picker also fails | Use the basic-picker retry button after checking the Qt/Quickshell runtime. Recovery is bounded; it never launches an automatic retry loop. |
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
