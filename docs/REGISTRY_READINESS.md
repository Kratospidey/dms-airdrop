# DMS registry submission

**Submitted for review:** [Add DMS AirDrop plugin — PR #1029](https://github.com/AvengeMedia/dms-plugin-registry/pull/1029) in the [official DMS plugin registry](https://github.com/AvengeMedia/dms-plugin-registry). It is **not yet approved or available through the official marketplace**. Until acceptance, use the [manual GitHub installation](FRIEND_SETUP.md).

The submission preserves `id: dmsAirDrop`, `name: AirDrop`, daemon/dankbar-widget capabilities and the existing v0.2.1 release tag. Metadata declares only Arch/Niri, with Omdrop and omdrop-owl as separately configured transfer prerequisites. Broader distro/compositor/hardware compatibility remains unverified.

A user-supplied authentic screenshot is cropped to the complete AirDrop popout, with the top bar and unrelated desktop removed. The reviewed crop is at [assets/airdrop-popout.png](../assets/airdrop-popout.png); no UI text or controls were altered.

[Marketplace setup](MARKETPLACE.md) documents what DMS clones, automatic first-click Basic when the optional native helper is missing, persistent picker preferences, manual KDE build instructions and the difference between frontend availability and operational AirDrop.

The submission uses the current [contribution requirements](https://github.com/AvengeMedia/dms-plugin-registry/blob/master/CONTRIBUTING.md), official validators and AI-assistance disclosure. Registry acceptance remains the maintainers' decision. No independent-machine testing is claimed.

Both official validators passed locally, with link validation scoped to the changed entry as in registry CI. An anonymous public clone preserved the root manifest, resources and executable modes; the isolated QML test passed without running the installer or building the native helper. The new full regression run passed 102 Python tests, QML checks and picker/controller smoke tests. See [Testing](TESTING.md) for the scope and the PR's Checks tab for current upstream CI and review status.

The first automated review requested reduced background work and native UI conventions. [Review corrections and measurements](REVIEW_FIXES.md) document the fixes and regression coverage; the PR tracks the current re-review outcome.
