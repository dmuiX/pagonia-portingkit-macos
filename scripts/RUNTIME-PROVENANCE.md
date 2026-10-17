# Runtime provenance

Last updated: 17.10.2026

## Wine engine archive

File: `WS12WineSikarugir10.0_2-20251028-pagonia.tar.xz`

SHA-256:

```text
0598a60af56d67b1efd35ac0751cbcc34a30a0329e2788e182dd67a5698f9353
```

This is a preserved historical Sikarugir Wine 10.0 revision 2 binary build dated
28 October 2025. It is the exact binary runtime used in the verified Pagonia
configuration. The archive contains no commercial game files and no Apple GPTK
or D3DMetal files.

The closest published source snapshot by build timestamp is:

```text
https://github.com/Sikarugir-App/wine/commit/38938bdb6f752cb68d13d833be97d0c524fe827e
```

The archive contains `COPYING.LIB` and a source-provenance notice. This binary is
not reproducibly proven to originate from that commit: the original build recipe,
toolchain manifest, and signed builder attestation are unavailable. Consumers
must treat it as a preserved compatibility binary rather than a reproducible
upstream release.

Key binary hashes:

```text
wine64:   08bbcc27b5a76e4473e8003007e140f74b529d67a164256d86d5163d88518300
wineserver: dcfd293ca9d7dc29bb9fb1a413850319c85c9823368a8f1a76bb22339b64cd45
ntdll.so: cf836b0727c47f4d9fb667628de226395697a6a5089678acea09ae32a7fb279e
ntdll.dll: 5549f99494e8e004cd112e72f0d721f6ffbb1bab1487871bff9f7d80c0b6a5da
```

## Wine 11.17 Steam downloader archive

File: `WineCX-11.17-SteamDownloader-4.7.3.tar.xz`

SHA-256:

```text
064de70024679010b65b3619c0de9f2993b432dc511bb018a55fc3b31aefece9
```

The archive root is `steam-wine11.bundle`. It contains a Wine 11.17 runtime
packaged for the Porting Kit 4.7.3 wrapper interface, its LGPL license, pinned
DXVK-macOS 1.10.3 `d3d10core`/`d3d11` files for x86 and x64, the DXVK license,
and embedded provenance notices. It is used only for a private Steam
login/download prefix and is never installed as the gameplay engine. The
installer verifies the complete archive and these key binaries before executing
it:

```text
wine64:     a680abba30b4888355adb39d8b62255e43546eb33d163897260627f7741ef648
wineserver: f5be596e5c38a2ee77a4ccfc4acab028bef636f0afc340fe2f57dad29474eb15
ntdll.so:   7c7e226f62d840028916ed3d4a94ce49f62a18df27102a771271369473b26365
ntdll.dll:       8b32c9f6f71b4f15fcaccb19b0f2adab9391ae73ad539cae9e136f8ee7d24128
DXVK x64 d3d10:  0fa08bba860c63e3abeeabfc96d0e7aa327411a975f8f23d2dc63594ef5f796e
DXVK x64 d3d11:  0ff0b0835dde29556bd01dfce7b1ae348d7f229cb1e1a37cc71ea1a028beeca4
DXVK x32 d3d10:  2277187a4e13fc2049fe28cb8dd05b34b48c68031c386c3597ba0e18b0c3d327
DXVK x32 d3d11:  f79d417f675d00008375eb4ea2318af6fcd0b27971d604d3cf345a0dcfa998a0
DXVK license:     240101b852af584ded719e7335a36f9a3aae3ac816774cf3f460c00d2c88c161
```

This runtime is isolated from the historical Wine 10 gameplay prefix. Once the
download is complete its wineserver is stopped. No downloader registry, cache,
logs, package downloads, or depot state are transferred. The installer does
transfer a narrowly scoped authenticated Steam session so the user signs in
only once: `config.vdf`, `loginusers.vdf`, optional `SteamAppData.vdf`, the
active account's `localconfig.vdf`, and any `ssfn` machine-authorization files.
Current Steam clients persist the transferable authentication state under the
`AuthData` and `SharedAuth` sections of that account-local file; the obsolete
`config.vdf/ConnectCache` layout is not required. Those files receive an exact SHA-256 inventory and are consumed only after both
Wineservers have stopped. Steam is launched with `-no-cef-sandbox -vgui`; the
compatibility switch is required for a visible current-client login under this
runtime. After SteamSetup, the installer runs `steamservice.exe /Install`
inside the private prefix, verifies a rendered on-screen Steam window, and
sends `steam://install/2155180` to open the game's install dialog.

## Pagonia build transfer manifest

File: `pagonia-build-25784167-SHA256SUMS`

SHA-256:

```text
f1c7dafea25540477c6201e3224b742bafaac178b027456cb4bc19541794ff6d
```

This manifest pins 856 licensed game files from Steam build `25784167`.
`backtrace.txt`, which is generated locally rather than supplied by the depot,
is intentionally excluded. The installer validates every listed source file
and recursively creates a new game tree containing only listed files. It also
validates the Steam appmanifest's app ID, completion state, build ID, and
install directory, then reconstructs a minimal sanitized appmanifest containing
only the required public depot metadata.

## Wineskin wrapper archive

File: `Wineskin-3.0.6-2.app.tar.xz`

SHA-256:

```text
dc97a4ff0f75b74a62b8571d4fe56387648f3755169e1dd8186b8f3d39aa597b
```

The wrapper is a normalized tar.xz repack of the public upstream release:

```text
https://github.com/vitor251093/porting-kit-wrappers/releases/tag/Wineskin-3.0.6-2
```

Original upstream `Wineskin.app.tar.7z` SHA-256:

```text
fbe276bba96d5582b99c511117abb1e035a988b8c1aeefe27c32df266a07907a
```

Pinned launcher SHA-256:

```text
217d7f3cf154d7117103934c9ec9b952b7209412132f2ad61565fb24d6e56697
```

The wrapper contains ad-hoc and unsigned components, as is typical for this
upstream package. The installer verifies the complete normalized archive and the
launcher hash before publication.

## Apple Game Porting Toolkit

Apple GPTK and D3DMetal binaries are not included. The user must obtain Game
Porting Toolkit 4.0 beta 3 from Apple.

The installer verifies:

- the complete 18-file SHA-256 manifest in `gptk-4.0b3-SHA256SUMS`;
- the exact 10-entry symlink manifest in `gptk-4.0b3-SYMLINKS`;
- absence of additional files or links;
- a read-only `/Volumes/.../redist/lib` source;
- all six Mach-O files against the macOS `anchor apple` signing requirement.

## Steam installer

Both isolated Wine 11.17 Steam installations accept only this
`SteamSetup.exe` SHA-256:

```text
7d3654531c32d941b8cae81c4137fc542172bfa9635f169cb392f245a0a12bcb
```

The download is restricted to HTTPS, including redirects. If Valve replaces the
installer, installation fails closed until the new artifact has been reviewed
and its pinned digest deliberately updated. SteamSetup is never executed with
the Wine 10 gameplay runtime. After the authenticated downloader has stopped,
the installer extracts the pinned Wine 11 runtime again, runs SteamSetup in a
fresh no-login prefix backed only by that new extraction, and builds a client
snapshot strictly from Valve's
`steam_client_win64.installed` inventory. It verifies every listed file's size
and CRC and records an exact SHA-256 snapshot manifest. The snapshot is consumed
immediately and is never trusted across resume. The clean client snapshot also
includes only Valve's `steam_client_win64.installed` marker from the package
directory, preventing a redundant first-launch client reinstall without
transferring package downloads. The Wine 10 prefix then receives the separately
inventoried Steam session described above. Steam registry, caches, logs,
unrelated `userdata`, package downloads, and depot state are excluded.
