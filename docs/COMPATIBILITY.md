# Compatibility and support boundaries

Reviewed for release 0.2.1 on 2026-10-10. A successful frontend install does not certify a radio, driver or firmware.

| Scope | Evidence | Status |
| --- | --- | --- |
| DMS 1.6.2 + Quickshell 0.3.1 | Installed runtime, QML compile and isolated interaction tests | Tested baseline |
| CachyOS, Niri, x86_64 | Existing developer laptop | Tested locally; no independent clean machine |
| Qt 6.11.2, KF6 KIO/IconThemes 6.30.0, kio-extras 26.08.1 | Native helper build, offscreen widget tests; prior Wayland picker use | Tested locally |
| Omdrop 0.14.1 | Existing receiver/source layout and command contract | Required exactly for mutations |
| omdrop-owl 0.1.0, contract 0.8.1 | Existing installation | Tested backend |
| RTL8852BE-VT + rtw89_8852bte | Incoming and outgoing transfers on one developer laptop | Experimental local result; not all Realtek adapters |
| New HOME/XDG/source paths | Isolated fixture and clone installation on same host | Portability simulation, not a fresh OS |
| Other DMS/Quickshell releases | Versions above baseline may install | Unverified |
| Other distributions, compositors, architectures | No hardware or desktop tests | Unverified |

## Upstream radio support versus this frontend

[omdrop-owl](https://github.com/t4t5/omdrop-owl#supported-hardware) lists MediaTek MT7925 (`mt7925e`) as tested. Other cards use an experimental profile and deliberate opt-in. This frontend does not add that opt-in. OWL's shared-channel mode requires Wi-Fi channel 6, 44 or 149. Driver injection behavior and teardown can affect connectivity; read upstream's known issues.

[omdrop-awdl](https://github.com/brentkearney/omdrop-awdl#hardware-compatibility) reports specific Apple machines using BCM4378, BCM4387 or BCM4388, with different amounts of receive/send evidence. This is not support for every Broadcom card. Consult the current upstream table for exact models.

The Broadcom backend is **not tested with DMS AirDrop**. Radio status follows a common helper interface, but automatic send-session ownership checks read OWL's `/run/omdrop-owl` metadata. On a backend lacking that metadata, cleanup preserves the finite receiving window and asks for manual recovery rather than claiming verified shutdown. Prefer a deliberate timed receiving window for experimentation; do not assume automatic cleanup portability.

## Omdrop installation contract

The preferred executable is `$HOME/.local/bin/omdrop`; PATH is also searched. The resolved CLI must keep its upstream `bin/` and sibling `share/` layout. Before changes, the adapter compares the rendered receiver service, checks service availability and existing self-signed identity metadata, and rejects known migrations. It does not read private key contents.

The backend retains Omdrop's documented system helper and state paths. Those are upstream contracts, not per-user paths to relocate arbitrarily. The frontend and installer use HOME/XDG for user data; the backend's own support for nondefault XDG layouts is separate. A clean HOME test of this installer does not prove Omdrop provisioning in that environment.

## Limits that matter during use

- Automatic Send-from-Off also enables receiving/discoverability temporarily.
- A five-minute abandonment timer waits behind an active plugin worker; a hard 60-minute Omdrop deadline still applies and can interrupt long transfers.
- Independent CLI users and incoming connections are not atomically locked with cleanup. Changed/unknown ownership preserves the window and shows recovery guidance.
- Omdrop contacts/identity and Apple device visibility requirements still apply.
- Qt fallback thumbnails and nonlocal/cloud file selection are not supported promises.
- Native thumbnails depend on installed KIO plugins and supported file formats.

See [Testing](TESTING.md) for the exact validation scope.
