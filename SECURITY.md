# Security and privacy

DMS plugins execute with the desktop user's permissions. This integration invokes an existing Omdrop CLI and installed libraries; it is not a sandbox for untrusted plugins or files.

## What installation changes

The default invocation checks prerequisites and previews a symlink. Applying installation can compile a helper inside the clone and creates only the DMS plugin symlink. It does not enable the plugin, change the bar layout, install system packages, invoke sudo, set experimental hardware flags, change firewall rules or configure Omdrop identities/services. A same-source symlink is safe to repeat; conflicting installations are refused.

## Runtime behavior

Selecting files while Off can open a bounded receiving/discoverability window. Ordinary operations use Omdrop's existing permissions and radio helper. The adapter blocks known implicit service migration/setup paths, but cannot atomically protect against independent CLI/configuration changes.

Selected paths briefly exist in mode-0600 request files in a mode-0700 runtime directory; workers consume them before launching the CLI. Arguments can still be visible to processes with sufficient access. Summaries contain a count and shortened destination, not selected file paths. A crash may leave private runtime data until logout. Picker preferences/recent-path caches are isolated in a temporary runtime folder; SIGKILL may leave that folder until logout. Omdrop has its own logs, history, certificates and privacy behavior.

The plugin does not read private key contents. It checks whether required identity files already exist. Transfer authentication, encryption and Apple identity behavior depend on the installed backend; this project does not claim an independent protocol security audit.

Cleanup uses ownership fingerprints and connection checks but is not an atomic compare-and-stop API. An independent incoming connection or CLI action can race. A finite Omdrop timeout may end a long transfer. Review [Architecture](docs/ARCHITECTURE.md) before changing these boundaries.

## Publication boundary

`PUBLIC_FILES.txt` is the explicit source archive inventory. `scripts/audit-public.py` checks it for excluded artifacts and recognizable credential patterns; release packaging consumes the same inventory and strips local ownership/timestamps. Initial Git staging is checked against it before publication. `.qa`, `.build`, `dist`, private baseline archives, historical machine-specific notes, unapproved images and credentials are excluded. Test device addresses and identities are synthetic fixtures.

Automated pattern checks supplement manual review; they cannot prove the absence of every secret. Never add real credentials to tests. Do not upload raw runtime state, full desktop screenshots or personal transfer files to issues.

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/Kratospidey/dms-airdrop/security/advisories/new). Include a minimal reproduction with synthetic data. Do not post working credentials or private identity material. For radio/protocol vulnerabilities, also follow the relevant upstream project's reporting policy.
