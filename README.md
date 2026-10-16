# Pioneers of Pagonia on macOS

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

## Prerequisites

1. An Apple Silicon Mac with Rosetta 2.
2. A Steam account that owns Pioneers of Pagonia.
3. Apple's **Game Porting Toolkit 4.0 beta 3** DMG, downloaded from the Apple
   Developer website after accepting Apple's license.
4. Git LFS when cloning this repository, because the pinned runtime archives
   are stored as LFS objects.

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

Fresh installation is the default. The script installs the pinned Windows
Steam installer and waits for you to sign in and install the game. A local
Pagonia prefix is reused only when explicitly supplied with `--source-prefix`;
only use a prefix you created and trust. Steam Cloud conflicts are never
resolved automatically.

The completed application is installed as:

```text
/Applications/Pioneers of Pagonia.app
```

## Runtime integrity

The installer verifies all runtime archives and important binaries before
publishing the application. It also verifies the complete GPTK 4.0 beta 3 file
and symlink manifests, rejects additions, requires a read-only mounted source,
and validates every native GPTK executable against Apple's signing anchor.

```text
0598a60af56d67b1efd35ac0751cbcc34a30a0329e2788e182dd67a5698f9353  scripts/WS12WineSikarugir10.0_2-20251028-pagonia.tar.xz
dc97a4ff0f75b74a62b8571d4fe56387648f3755169e1dd8186b8f3d39aa597b  scripts/Wineskin-3.0.6-2.app.tar.xz
```

The Wine archive contains its LGPL 2.1 license and source-provenance notice. It
contains no game files and no Apple GPTK or D3DMetal components. Detailed
provenance and limitations are documented in
[`scripts/RUNTIME-PROVENANCE.md`](scripts/RUNTIME-PROVENANCE.md).

## Tests

The non-human fresh-install packaging/control-flow smoke test can be run with a
trusted local fixture prefix:

```bash
./tests/simulate-installer.sh
```

This exercises the SteamSetup lifecycle, completed-login fixture state, depot
completion fixture, configuration, verification, and atomic publication. It
cannot validate SteamSetup's real output and cannot replace a real
Steam authentication, Steam Guard, account-license, or network-depot test.

## Important limitations

This is an unsupported compatibility setup. A Steam, game, macOS, Wine, or GPTK
update may invalidate the pinned hashes or behavior. The installer intentionally
refuses unknown game builds instead of applying binary modifications blindly.
