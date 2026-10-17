# Pioneers of Pagonia on macOS

## New modular installer (unreleased)

The new implementation of [INSTALLER-SPEC.md](INSTALLER-SPEC.md) has a separate entry point:

    ./scripts/install-pagonia-new.sh

It uses distinct Wine 11.17 **downloader** and pinned Wine 10 **gameplay** prefixes.
It supports managed Fresh/Resume/Delete, verified Steam and depot inputs, allowlisted
session/client snapshots, and publication with rollback. The legacy installer is not
invoked by the new entry point and remains available pending full acceptance.

The new entry accepts `--fresh`, `--resume PATH`, `--delete`, `--yes`, and
`--gptk-lib PATH`. Fresh/Delete use one global confirmation before removing
verified managed state; ambiguous name matches remain untouched.

**Release gate:** A real interactive Apple Silicon Fresh run must complete Steam login,
depot acquisition, Wine 10 online session validation, D3D12 device/swapchain creation,
and visibly rendered terrain. Unit tests do not replace this final compatibility gate.

This project installs the Windows Steam version of **Pioneers of Pagonia** as a
standalone macOS Wineskin application using Apple Game Porting Toolkit 4.0 beta
3.

The installer uses a hash-pinned Wine/Wineskin runtime bundled in `scripts/`.
It does not require Porting Kit, another installed game, or another local
Wineskin application.

## Verified configuration

- Pioneers of Pagonia: Steam App `2155180`, build `25784167`
- Game Porting Toolkit: `4.0 beta 3`
- D3DMetal: `4.0b3`
- Wine: historical Sikarugir Wine 10.0 revision 2 build
- Wineskin wrapper: `3.0.6_2`

The verified launch produced:

```text
Created D3D12Device
Created D3D12 Swapchain
```

Wine 11.16 and Wine 11.17 were also evaluated with GPTK 4.0 beta 3. Both
reached Pagonia's visible startup phase but remained stuck and never produced
the required D3D12 success markers. Wine 11.17 nevertheless runs the current
Steam client successfully when Steam/CEF is routed through pinned DXVK and a
native Wine DXGI DLL; this is why it remains useful as the downloader runtime. The recent hanging runs were manually
stopped and must not be described as automatic crashes. The historical
Sikarugir Wine 10.0 build therefore remains the intentionally pinned gameplay
runtime. The sanitized technical record is available in
[`analysis/whisky-wine-11.16-pagonia-test-2026-10-16.md`](analysis/whisky-wine-11.16-pagonia-test-2026-10-16.md)
so others can review the evidence and investigate the compatibility boundary.

Fresh installation now uses a split-runtime design. A private Wine 11.17 prefix
runs Steam only for login and the depot download. After its wineserver stops,
the installer validates all 856 files against the pinned build manifest and
copies only those files and reconstructs a minimal sanitized appmanifest in a
distinct Wine 10 gameplay prefix. After the authenticated downloader stops, a second isolated
Wine 11 prefix backed by a fresh extraction of the pinned runtime runs
SteamSetup without login or depot access and
builds a clean Steam client snapshot exclusively from Valve's installed-package
inventory. That snapshot is immediately copied into the final prefix after
Wine 10 initializes it; SteamSetup is never run under Wine 10. The installer
then transfers a narrowly scoped, SHA-256-inventoried Steam login session:
`config.vdf`, `loginusers.vdf`, optional `SteamAppData.vdf`, the active
account's `localconfig.vdf`, and any `ssfn` machine-authorization files. It
verifies that Wine 10 accepts the transferred account before publication.
Registry, caches, logs, package downloads, unrelated `userdata`, and depot
state remain excluded, and two Wine versions never open one prefix.

## Prerequisites

1. An Apple Silicon Mac with Rosetta 2.
2. A Steam account that owns Pioneers of Pagonia.
3. Apple's **Game Porting Toolkit 4.0 beta 3** DMG, downloaded from the Apple
   Developer website after accepting Apple's license.
4. Git LFS when cloning this repository, because the pinned runtime archives
   are stored as LFS objects.
5. Screen Recording permission for the terminal that runs the installer. This
   lets the installer confirm that Steam's login window is visibly rendered
   rather than black. Grant it under **System Settings → Privacy & Security →
   Screen Recording** before starting; no captured image is retained.

GPTK and D3DMetal are not included in this repository.

## Installation

Clone the repository with Git LFS enabled:

```bash
git lfs install
git clone https://github.com/dmuiX/pagonia-portingkit-macos.git
cd pagonia-portingkit-macos
```

Mount the GPTK 4.0 beta 3 DMG or leave it in `~/Downloads`, then run:

```bash
./scripts/install-pagonia-gptk4b3.sh
```

Fresh installation is the default. The script installs the Steam Client
Service inside the private Wine 11.17 prefix, opens Steam, and waits for the
single interactive sign-in. It then sends `steam://install/2155180`
automatically; confirm Steam's preselected installation dialog once. It uses
normal operating-system DNS without changing resolver settings or
hardcoding an address. A LANCache therefore works when your existing DNS maps
Steam content hosts to it; the installer neither discovers nor configures the
cache. LANCache is optional and is not inherently faster than Steam's CDN. A
real cache-hit test on an encrypted Btrfs volume backed by a 5400-RPM SMR disk
saturated that disk at roughly 17 MB/s with 40–46 ms read latency, making the
cache slower than a 400-Mbit/s Internet connection. Use direct DNS unless the
cache storage has adequate random-read performance, preferably SSD/NVMe.

After validation and selective import, the final Wine 10 application has its
own Steam installation and receives the authenticated session from the stopped
downloader, so no second Wine 10 login is required. Apart from confirming the
preselected install dialog, only the Wine 11 login is interactive. The final prefix contains
no local game saves; the transferred account metadata lets Steam retrieve the
remote Cloud state rather than presenting a second-login workflow. A local
Pagonia prefix is reused only when explicitly supplied with `--source-prefix`;
only use a prefix you created and trust. `--source-prefix` retains its existing
trusted full-prefix behavior and is never used internally for split transfer. The Wine 11.17 downloader
uses pinned DXVK-macOS and native Wine DXGI routing so the current Steam CEF
login window renders correctly. Its CEF sandbox is disabled because that
sandbox crashes under these Wine builds, so this downloader remains isolated
in a private disposable prefix. Earlier attempts produced a black login window
even though Steam logged `BrowserReady`; that marker is not accepted as visual
success. Launching through `open` also triggered Gatekeeper verification and
Wineskin lock failures, while ad-hoc signing changed a pinned launcher and was
correctly rejected. The working path launches Wine directly with Steam's
`-vgui` compatibility switch, keeps CEF GPU rendering enabled, verifies the
DXVK/DXGI payload, and checks that the actual
login window contains rendered pixels. If interrupted, a normal invocation
automatically resumes the single valid active or dormant private staging
prefix. No staging starts a fresh deployment; multiple candidates fail closed
and require `--resume PATH`, while `--fresh` deliberately ignores them. Resume
still validates the completed depot and performs a selective import—it
does not convert the downloader into a source-prefix installation.

The completed application is installed as:

```text
/Applications/Pioneers of Pagonia.app
```

## Removing an installation

Deletion mode broadly lists Pagonia-named paths plus verified applications and
Wine prefixes in `/Applications`, `~/Applications`, and `~/Games`, including
their sizes. Select one entry (`1`), several (`1,2`), or every listed entry
(`all`):

```bash
./scripts/install-pagonia-gptk4b3.sh --delete
```

For non-interactive removal, provide one exact path from that list:

```bash
./scripts/install-pagonia-gptk4b3.sh --delete --yes \
  --destination '/Applications/Pioneers of Pagonia.app'
```

Only explicitly selected entries are deleted. Review broad name matches
carefully. The operation includes contained Wine prefixes, local Steam sessions,
and local save data; Steam Cloud data is not modified.

## Runtime integrity

The installer verifies all runtime archives and important binaries before
publishing the application. It also verifies the complete GPTK 4.0 beta 3 file
and symlink manifests, rejects additions, requires a read-only mounted source,
and validates every native GPTK executable against Apple's signing anchor.

```text
0598a60af56d67b1efd35ac0751cbcc34a30a0329e2788e182dd67a5698f9353  scripts/WS12WineSikarugir10.0_2-20251028-pagonia.tar.xz
064de70024679010b65b3619c0de9f2993b432dc511bb018a55fc3b31aefece9  scripts/WineCX-11.17-SteamDownloader-4.7.3.tar.xz
dc97a4ff0f75b74a62b8571d4fe56387648f3755169e1dd8186b8f3d39aa597b  scripts/Wineskin-3.0.6-2.app.tar.xz
f1c7dafea25540477c6201e3224b742bafaac178b027456cb4bc19541794ff6d  scripts/pagonia-build-25784167-SHA256SUMS
```

The Wine archive contains its LGPL 2.1 license and source-provenance notice. It
contains no game files and no Apple GPTK or D3DMetal components. Detailed
provenance and limitations are documented in
[`scripts/RUNTIME-PROVENANCE.md`](scripts/RUNTIME-PROVENANCE.md).

## Tests

The non-human fresh-install packaging/control-flow smoke test can be run with a
trusted local fixture prefix:

```bash
./tests/security-controls.sh
./tests/simulate-installer.sh
python3 ./tests/test-steam-session.py
python3 ./tests/test-steam-login-log.py
python3 ./tests/test-steam-window-bmp.py
python3 ./tests/test-run-bounded-command.py
```

The control-flow test exercises fresh and completed-resume deployments, both
isolated Wine 11 SteamSetup lifecycles, the package-manifest-validated no-login
Steam client snapshot, selective authenticated-session transfer, Wine 10 prefix
initialization without executing SteamSetup there, 856-file depot verification,
downloader-sentinel exclusion, configuration, and atomic publication. It cannot validate
SteamSetup's real output, visible CEF rendering, Steam authentication, Steam Guard,
account-license, DNS/LANCache, or network-depot behavior. Only a real fresh
installation is accepted as end-to-end evidence.

## Important limitations

This is an unsupported compatibility setup. A Steam, game, macOS, Wine, or GPTK
update may invalidate the pinned hashes or behavior. The installer intentionally
refuses unknown game builds instead of applying binary modifications blindly.
