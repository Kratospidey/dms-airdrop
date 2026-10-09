# Contributing

Report reproducible interface/installer bugs in GitHub Issues with the release version, DMS/Quickshell versions, distribution/compositor and sanitized reproduction. For hardware problems include chipset and driver, never SSIDs/MACs, identity material or personal transfer files. Security reports belong in private advisories; see SECURITY.md.

Keep changes focused on the frontend. Do not add automatic driver, firewall, network, identity or receiver-service provisioning. Preserve bounded sessions, truthful unknown/error states and explicit user control. Radio/contract changes need a version-specific audit and separately approved hardware testing.

Run `python3 tests/run_checks.py --portable` for the standard-library regression suite and source audit. Desktop/native changes additionally need the checks in docs/TESTING.md. Add meaningful coverage for changed behavior. A passing mock suite is not hardware evidence.

New public files must be deliberately added to PUBLIC_FILES.txt and reviewed for privacy, licensing and portability. Never stage generated .qa/.build/dist output. Use `python3 scripts/package.py` to produce the source archive and checksum. Review every archive entry before a release.

Describe the problem, final behavior, validation and limits in pull requests. Disclose meaningful AI assistance and review the resulting code. Contributions are accepted under the project's MIT license; retain third-party notices and identify any adapted source.
