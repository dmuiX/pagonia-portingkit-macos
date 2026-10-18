# Runtime provenance

Last updated: 16.10.2026

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

The fresh-install path accepts only this `SteamSetup.exe` SHA-256:

```text
7d3654531c32d941b8cae81c4137fc542172bfa9635f169cb392f245a0a12bcb
```

The download is restricted to HTTPS, including redirects. If Valve replaces the
installer, installation fails closed until the new artifact has been reviewed
and its pinned digest deliberately updated.
