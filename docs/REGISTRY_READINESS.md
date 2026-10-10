# Official DMS registry status

**Accepted:** maintainer `hthienloc` merged [Add DMS AirDrop plugin — PR #1029](https://github.com/AvengeMedia/dms-plugin-registry/pull/1029) into the [official DMS plugin registry](https://github.com/AvengeMedia/dms-plugin-registry) on 2026-10-10 as [commit 444f343](https://github.com/AvengeMedia/dms-plugin-registry/commit/444f3439c915643235aee7caf45279f55fda05a8). The entry is [plugins/kratospidey-dms-airdrop.json](https://github.com/AvengeMedia/dms-plugin-registry/blob/master/plugins/kratospidey-dms-airdrop.json). Install through **DMS Settings → Plugins → Browse → AirDrop**; refresh a cached catalog if needed. [Manual GitHub installation](FRIEND_SETUP.md) remains available.

The entry preserves `id: dmsAirDrop`, `name: AirDrop` and daemon/dankbar-widget capabilities. Metadata still declares only Arch/Niri, with Omdrop and omdrop-owl as separately configured transfer prerequisites. Registry acceptance is not hardware certification or proof of an operational backend. Broader distro/compositor/hardware compatibility remains unverified. [v0.2.2](RELEASE_0.2.2.md) consolidates the reviewed source fixes; the v0.2.1 tag and assets remain immutable. This routine source release does not change registry metadata or require another registry PR.

A user-supplied authentic screenshot is cropped to the complete AirDrop popout, with the top bar and unrelated desktop removed. The reviewed crop is at [assets/airdrop-popout.png](../assets/airdrop-popout.png); no UI text or controls were altered.

[Marketplace setup](MARKETPLACE.md) documents what DMS clones, automatic first-click Basic when the optional native helper is missing, persistent picker preferences, manual KDE build instructions and the difference between frontend availability and operational AirDrop.

The submission followed the [contribution requirements](https://github.com/AvengeMedia/dms-plugin-registry/blob/master/CONTRIBUTING.md), official validators and AI-assistance disclosure. The [final automated review reported ready with no issues](https://github.com/AvengeMedia/dms-plugin-registry/pull/1029#issuecomment-6096327356), followed by the maintainer merge. No independent-machine testing or Apple endorsement is claimed.

During submission, both official validators passed locally, with link validation scoped to the entry as in registry CI. An anonymous public clone preserved the root manifest, resources and executable modes; the isolated QML test passed without running the installer or building the native helper. See [Testing](TESTING.md) and [v0.2.2 notes](RELEASE_0.2.2.md) for current automated release validation, including 102 Python tests and the clean-source marketplace fixture.

The automated reviews requested reduced background work, native UI conventions and first-click picker compatibility. [Review corrections and measurements](REVIEW_FIXES.md) document the completed fixes and regression coverage; the merged PR preserves the review history.
