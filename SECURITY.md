# Security policy

## Supported version

Only the current `main` branch is supported. The installer intentionally fails
closed when runtime, GPTK, Steam installer, or game hashes differ from the
verified configuration.

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub Security
Advisories for this repository. Do not include Steam credentials, Apple
Developer credentials, game files, or licensed Apple binaries in a report.

## Trust model

The installer treats these as trusted inputs:

- the tracked runtime archives whose complete SHA-256 values are pinned;
- a read-only GPTK 4.0 beta 3 volume that matches the complete tracked manifests
  and whose native executables satisfy Apple's signing requirement.

Downloaded Steam setup and installed game binaries are accepted only when they
match pinned SHA-256 values. The installer refuses root execution and rejects
world-writable destination parents.

An attacker who already controls the invoking user's account can replace the
script and its trust data and is outside this local installer's threat model.
Unprivileged cross-user local attackers, malicious downloads, compromised
mutable inputs, and repository/CDN substitution are in scope. Other macOS
administrators and root are privileged principals outside this threat model;
they can replace applications and user-owned files after installation.
