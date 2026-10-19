# Pioneers of Pagonia on macOS

Current release: **v1.1.0**

This project installs the Windows Steam version of **Pioneers of Pagonia** as a
standalone macOS Wineskin application using Apple Game Porting Toolkit 4.0 beta
3.

The installer uses a hash-pinned Wine/Wineskin runtime bundled in `scripts/`.
It does not require Porting Kit, another installed game, or another local
Wineskin application.

## Current status

The Wine-10-only installer has completed both a real Fresh installation and a
real Resume installation. Steam installation, authentication, download,
publication, and launch work. The game creates its D3D12 device and swapchain,
and the main world, terrain, water, buildings, units, and interface render.

One known graphics issue remains: the minimap background is blank, while its
symbols and position marker render correctly. Windows and Linux render the same
game content correctly, so current evidence strongly implicates the macOS
D3D12-to-D3DMetal/Metal compatibility path. The exact failing shader or render
stage has not yet been identified. See
[`analysis/v1.1.0-validation-and-known-issues-2026-10-18.md`](analysis/v1.1.0-validation-and-known-issues-2026-10-18.md).

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
git clone https://github.com/dmuiX/pioneers-of-pagonia-on-macos.git
cd pioneers-of-pagonia-on-macos
```

Mount the GPTK 4.0 beta 3 DMG or leave it in `~/Downloads`, then run:

```bash
./scripts/install-pagonia-gptk4b3.sh
```

The normal start discovers only staging marked by this installer version:
no candidate starts Fresh; one candidate asks whether to continue; multiple
candidates abort without guessing. `--fresh` ignores retained staging and starts
separately. Resume preserves the same Wine 10 Steam prefix, login, and partial
download. Exit Windows Steam/Wine before resuming. No `--resume PATH` is needed.

Resume covers only the Steam installation/download phase. Interruptions before
that checkpoint or during later graphics configuration/publication are retained
for diagnosis, not resumed. Older unmarked staging is never adopted. Resume
has fixture-test coverage and completed a real interrupted staging run through
publication and successful game launch.

All installation uses Wine 10 only: no Wine 11 runtime or cross-prefix transfer
is involved. The bootstrap installer is complete when
SteamSetup has exited and `steam.exe` and `uninstall.exe` exist; the `package`
directory belongs to the subsequent Steam client update. Setup and download
waits report status every 30 seconds, and archive checks every 25 seconds.

Restarts wait for both Wine and the Wineskin launcher to exit, preventing the
previous launcher's cleanup from overlapping the next launch. On interruption
or failure, the installer requests shutdown of its own prefix and preserves the
unfinished installation. If Wine or its debugger remains alive, it refuses to
restart or move the application. Recursive directory deletion is also blocked
while Wine/Steam/launcher processes are detected; the installer never deletes
Wine's `/tmp/.wine-*` server directory.

The final launch check requires the real game process, with both required
launch options, to remain active for ten seconds. D3D12 device and swapchain
messages are reported only as optional diagnostic evidence because Wineskin
does not emit them on every successful launch. Terrain rendering still requires
visual confirmation because process and log signals cannot prove correct output.
After that confirmation, close the game and confirm in the terminal. The
installer then terminates a game process left behind by a closed window,
requests a normal Steam shutdown so Cloud synchronization can finish, stops
Wine, and terminates only residual processes using this application's pinned
`wine64`.

The installed application also includes a Wineskin lifecycle finalizer for
normal Finder/Dock launches. Its startup hook watches for the game to exit and
then shuts down Steam and Wine. Its Quit and Shutdown hooks additionally handle
a game process left behind by a closed window. Forced cleanup is limited to
processes that have this application's pinned `wine64` open.

**Validation status:** a real Wine-10-only Fresh run on 18.10.2026 completed
Steam installation, login, game download, publication, and game launch with
both D3D12 markers. A real Resume run also completed publication and launch.
The user confirmed correct world terrain; the minimap background remains blank
because of an unresolved macOS graphics-translation issue. Automated tests do
not replace visual acceptance.

The script installs the pinned Windows Steam installer and opens Pagonia's
installation dialog after login. Confirm that dialog in Steam. This automatic
request is a later change and still needs real-run verification. Steam Cloud
conflicts are never resolved automatically. Existing external prefixes are not
imported.

To exercise the real post-installation verification path without reinstalling
Steam or downloading the game again, close Pagonia and Windows Steam, then run:

```bash
./scripts/install-pagonia-gptk4b3.sh --verify-existing
```

This verifies the installed deployment's pinned runtime, game build, graphics
components, Wineskin configuration, and Steam launch options. It then launches
the existing application through the same launch-check function used after a
fresh or resumed installation. It never republishes, renames, or deletes the
existing application. SteamSetup, authentication, download, graphics copying,
and atomic publication are necessarily outside this mode because they would
require a separate installation.

To remove the installed application, including its Steam login, game files, and
local saves, run `./scripts/install-pagonia-gptk4b3.sh --delete`. It verifies the
deployment marker and Wine identity, requires stopped Wine/Steam processes,
and asks for confirmation (`--yes` skips the question). Steam Cloud, other
prefixes, and temporary staging folders are not deleted. Apple GPTK is not
required for deletion.

The completed application is installed as:

```text
/Applications/Pioneers of Pagonia.app
```

## Refreshing a stale Apps/Launchpad icon

If Finder and Spotlight show the correct Pagonia icon but the Apps view opened
from Dock still shows older artwork, refresh only this application's registration:

```bash
LSREGISTER='/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister'
"$LSREGISTER" -u '/Applications/Pioneers of Pagonia.app'
"$LSREGISTER" -f '/Applications/Pioneers of Pagonia.app'
```

Then close and reopen the Apps view. Restarting Dock or the icon service alone
did not resolve the observed stale entry. Do not reset the global Launchpad
layout/database or repeatedly replace an icon that Finder already displays
correctly. These commands change registration only, not the app or its data.

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
PAGONIA_SIM_PREFIX=/path/to/a/verified-fixture-prefix \
  ./tests/simulate-installer.sh
```

This exercises the SteamSetup lifecycle, completed-login fixture state, depot
completion fixture, configuration, verification, and atomic publication. It
cannot validate SteamSetup's real output and cannot replace a real
Steam authentication, Steam Guard, account-license, or network-depot test.
Focused regression tests can be run with:

```bash
python3 tests/test-v1-steam-setup.py
python3 tests/test-v1-delete.py
python3 tests/test-v1-resume.py
python3 tests/test-v1-shutdown.py
python3 tests/test-v1-icon.py
python3 tests/test-v1-launch-verification.py
python3 tests/test-v1-verify-existing.py
```

## Development and diagnostics

The current repair history, real validation evidence, diagnosed installer
failures, minimap GPU-capture results, and remaining investigation steps are
recorded in
[`analysis/v1.1.0-validation-and-known-issues-2026-10-18.md`](analysis/v1.1.0-validation-and-known-issues-2026-10-18.md).

Earlier modular prototypes, specifications, ADRs, historical experiments, and
superseded documentation were intentionally removed from the release tree. They
remain available in Git history for research, but are not supported parts of the
current installer.

## Important limitations

The game is playable, but the minimap background is currently missing on the
verified macOS graphics stack. Minimap symbols remain visible. This is an
unresolved rendering defect, not an installation failure.

This is an unsupported compatibility setup. A Steam, game, macOS, Wine, or GPTK
update may invalidate the pinned hashes or behavior. The installer intentionally
refuses unknown game builds instead of applying binary modifications blindly.

## Support and maintenance

Most of this project was developed with AI assistance. It is published as-is,
without regular support, troubleshooting, maintenance, or compatibility
guarantees. Please do not assume that issues or pull requests will receive a
response.

I may update the project when I personally return to Pagonia and discover that
it no longer works, or when I choose to test a new Apple Game Porting Toolkit
release. Any such work will happen only when my time and interest permit.
