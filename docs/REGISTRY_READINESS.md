# DMS registry submission

The v0.2.1 integration is being prepared for submission to the [official DMS plugin registry](https://github.com/AvengeMedia/dms-plugin-registry). It is **not yet approved or available through the official marketplace**. Until acceptance, use the [manual GitHub installation](FRIEND_SETUP.md).

The submission preserves `id: dmsAirDrop`, `name: AirDrop`, daemon/dankbar-widget capabilities and the existing v0.2.1 release tag. Metadata declares only Arch/Niri, with Omdrop and omdrop-owl as separately configured transfer prerequisites. Broader distro/compositor/hardware compatibility remains unverified.

A user-supplied authentic screenshot is cropped to the complete AirDrop popout, with the top bar and unrelated desktop removed. The reviewed crop is at [assets/airdrop-popout.png](../assets/airdrop-popout.png); no UI text or controls were altered.

[Marketplace setup](MARKETPLACE.md) documents what DMS clones, the explicit basic-picker recovery when the optional native helper is missing, manual KDE build instructions and the difference between frontend availability and operational AirDrop.

The submission uses the current [contribution requirements](https://github.com/AvengeMedia/dms-plugin-registry/blob/master/CONTRIBUTING.md), official validators and AI-assistance disclosure. Registry acceptance remains the maintainers' decision. No independent-machine testing is claimed.
