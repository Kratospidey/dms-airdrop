# Future DMS registry submission

No registry submission is part of release 0.2.1. Follow the current [official contribution guide](https://github.com/AvengeMedia/dms-plugin-registry/blob/master/CONTRIBUTING.md) when ready.

Remaining work:

1. Capture and approve a clean, authentic screenshot of the actual plugin; remove private device/file information. The registry requires a reachable screenshot URL. Mock previews are not a substitute for verified UI evidence.
2. Decide how registry users are directed through the optional native helper build and separate Omdrop/radio setup. A registry clone alone does not build the helper or provision AirDrop.
3. Verify on an independent compatible machine and document only the distributions/compositors actually tested. Audit any newer DMS/Omdrop contract before claiming support.
4. Create `plugins/kratospidey-dms-airdrop.json` in a registry fork with matching `id: dmsAirDrop`, `name: AirDrop`, repository URL, author, daemon/dankbar-widget capabilities, category, explicit dependencies, conservative distro/compositor claims and the approved screenshot URL.
5. Run the registry's schema and link validators, review its then-current policies, and submit a separately authorized PR with test evidence and AI-assistance disclosure.

The public repository already provides a root plugin.json, license, versioned source release, installation guide, dependency information and reversible installation.
