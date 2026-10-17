# Pioneers of Pagonia on macOS with GPTK 4.0 beta 3

Last verified: 16.10.2026
Game: Steam App 2155180, Build 25784167
Test system: MacBook Pro 14-inch (MacBookPro18,3), M1 Pro, 32 GB, macOS 26.3

> **Archived experiment — do not use these steps for a current installation.**
> This document preserves the earlier manual binary-patching investigation.
> The supported installer keeps the original `dxil.dll`, removes game-local
> `D3D12Core.dll`, and uses both game-provided launch switches. Follow the
> repository root `README.md` and `scripts/install-pagonia-gptk4b3.sh` instead.

## Historical result

Pioneers of Pagonia starts through Steam, creates a D3D12 device and swapchain, and loads into the game with the reconstructed Wineskin setup described below.

The successful run logged:

```text
Created D3D12Device
Created D3D12 Swapchain
```

Unlike the earlier GPTK 4.0 beta 2 test, the captured beta 3 run did not emit the known errors:

```text
irconverter_hull_shader: Failed to materializeAll
Failed to compile a pipeline, marking PSO(...) as no-op
```

A successful in-game test was visually confirmed by the user. This remains an unsupported configuration; future Steam, game, Wine, macOS, or GPTK updates may break it.

## The important discovery

The working setup does **not** use the separately downloaded Sikarugir 10.0.3 engine. It uses the complete older Wine/Wineskin runtime embedded in this already working local wrapper:

```text
~/Applications/GTA VC Nextgen Edition.app
```

The source application itself is not modified. Its wrapper and Wine runtime are copied to a new application.

Identifying values of the working runtime:

```text
Wineskin wrapper CFBundleVersion: 3.0.6_2
Wine version string: wine-10.0 (Sikarugir)
wine64 SHA-256: 08bbcc27b5a76e4473e8003007e140f74b529d67a164256d86d5163d88518300
ntdll.so SHA-256: cf836b0727c47f4d9fb667628de226395697a6a5089678acea09ae32a7fb279e
ntdll.dll SHA-256: 5549f99494e8e004cd112e72f0d721f6ffbb1bab1487871bff9f7d80c0b6a5da
```

The version string alone is insufficient. Sikarugir 10.0.3 reports a similar version but contains different binaries.

## Prerequisites

The following paths are used in the commands:

```bash
SOURCE_APP="$HOME/Applications/GTA VC Nextgen Edition.app"
SOURCE_PREFIX="$HOME/Games/Pagonia-GPTK4b3"
APP='/Applications/Pioneers of Pagonia.app'
BETA='/Volumes/Evaluation environment for Windows games 4.0 beta 3/redist/lib'
```

Required inputs:

1. The known-good Wineskin wrapper shown above, or a byte-identical engine.
2. A prefix in which Steam and Pioneers of Pagonia are already installed.
3. Apple's Game Porting Toolkit 4.0 beta 3 evaluation environment, obtained legitimately from Apple.
4. Python with `pefile` for the deterministic `dxil.dll` import patch. The verified run used `pefile` 2024.8.26.
5. An `objdump` implementation that can parse PE/COFF files. The verification commands below use the macOS tool available on the test system.

Do not redistribute Apple's GPTK files, Steam credentials, the game, prepatched DLLs, opaque wrapper bundles, or files from another commercial game.

## 1. Stop Wine and Steam

Do not modify a live prefix.

```bash
PFX="$SOURCE_PREFIX"
WINE="$SOURCE_APP/Contents/SharedSupport/wine/bin"
WINEPREFIX="$PFX" "$WINE/wineserver" -k || true
sleep 5
ps ax -o pid=,command= \
  | grep -E '[S]team\.exe|[P]ioneers of Pagonia|[w]inedbg' || true
```

Continue only when the final command prints no relevant process.

## 2. Create an independent Wineskin application

Copy the wrapper and Wine runtime without the GTA prefix, then copy the existing Pagonia prefix:

```bash
set -euo pipefail
SOURCE_APP="$HOME/Applications/GTA VC Nextgen Edition.app/"
SOURCE_PREFIX="$HOME/Games/Pagonia-GPTK4b3"
APP='/Applications/Pioneers of Pagonia.app/'

# Validate every source before moving an existing destination.
test -x "${SOURCE_APP}Contents/SharedSupport/wine/bin/wine64"
test -f "$SOURCE_PREFIX/drive_c/Program Files (x86)/Steam/steam.exe"
test -f "$SOURCE_PREFIX/drive_c/Program Files (x86)/Steam/steamapps/common/Pioneers of Pagonia/dxil.dll"

if [[ -e "$APP" ]]; then
  BACKUP="${APP%/}.backup-$(date +%Y%m%d-%H%M%S)"
  mv "$APP" "$BACKUP"
  echo "Existing application preserved at: $BACKUP"
fi
mkdir -p "$APP"
/usr/bin/rsync -a \
  --exclude='Contents/SharedSupport/prefix/***' \
  "$SOURCE_APP" "$APP"
rm -rf "${APP}Contents/SharedSupport/prefix"
ditto "$SOURCE_PREFIX" "${APP}Contents/SharedSupport/prefix"
```

The source GTA wrapper and the original Pagonia prefix remain untouched.

## 3. Configure the wrapper

```bash
APP='/Applications/Pioneers of Pagonia.app'
PLIST="$APP/Contents/Info.plist"

plutil -replace CFBundleName -string 'Pioneers of Pagonia' "$PLIST"
plutil -replace CFBundleDisplayName -string 'Pioneers of Pagonia' "$PLIST"
plutil -replace 'Program Name and Path' \
  -string '/Program Files (x86)/Steam/steam.exe' "$PLIST"
plutil -replace 'Program Flags' \
  -string '-applaunch 2155180 -NoDX12DeviceFactory' "$PLIST"
plutil -replace D3DMETAL -integer 1 "$PLIST"
plutil -replace D3DMETAL_FORCE -integer 1 "$PLIST"

launchctl setenv D3DM_MTL4 1
```

The Wineskin launcher may normalize the bundle identifier when it starts. That identifier is not part of the graphics fix.

## 4. Overlay GPTK 4.0 beta 3

The existing `wine` directory must be **overlaid**, not deleted. This preserves the Wine build's engine-specific Unix modules.

```bash
set -euo pipefail
APP='/Applications/Pioneers of Pagonia.app'
LIB="$APP/Contents/SharedSupport/wine/lib"
BETA='/Volumes/Evaluation environment for Windows games 4.0 beta 3/redist/lib'

test -d "$BETA/external"
test -d "$BETA/wine"
test ! -e "$LIB/external.portingkit-original-backup"
mv "$LIB/external" "$LIB/external.portingkit-original-backup"
ditto "$BETA/external" "$LIB/external"
ditto "$BETA/wine" "$LIB/wine"
```

Verification:

```bash
strings "$LIB/external/D3DMetal.framework/Versions/A/D3DMetal" \
  | grep -m1 'PROGRAM:D3DMetal'
```

Expected:

```text
@(#)PROGRAM:D3DMetal  PROJECT:D3DMetal-4.0b3
```

## 5. Install the D3D12 files

```bash
APP='/Applications/Pioneers of Pagonia.app'
PFX="$APP/Contents/SharedSupport/prefix"
GAME="$PFX/drive_c/Program Files (x86)/Steam/steamapps/common/Pioneers of Pagonia"
SYS="$PFX/drive_c/windows/system32"
BETA='/Volumes/Evaluation environment for Windows games 4.0 beta 3/redist/lib'

cp -p "$BETA/wine/x86_64-windows/dxgi.dll" "$SYS/dxgi.dll"
cp -p "$BETA/wine/x86_64-windows/d3d12.dll" "$SYS/d3d12.dll"
cp -p "$GAME/D3D12/D3D12Core.dll" "$GAME/D3D12Core.dll"
```

Expected hashes in the verified run:

```text
dxgi.dll:      d53d9ea91935f0de126ba528264fc4c9b4dfea8bfe43f3f1256bd3e8963d67ee
d3d12.dll:     3174fac027d3ff10971645ac41b665cd53949c87d6d2d7d53b0073bf4bb36981
D3D12Core.dll: 625bd40005b1c3708695d5256ecf230d278e6b8edba5a88af70f3d91324f3052
```

The verified reconstruction retained the engine-native `system32/d3d12core.dll`. The Microsoft Agility SDK core used by the game is the copy beside the game executable.

## 6. Set Windows build 19045

Back up the registry first, without overwriting an earlier backup, and change only the two documented value names:

```bash
test ! -e "$PFX/system.reg.before-pagonia"
cp -p "$PFX/system.reg" "$PFX/system.reg.before-pagonia"
python3 - "$PFX/system.reg" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
text = path.read_text(errors='surrogateescape')
text, count = re.subn(
    r'("CurrentBuild(?:Number)?"=")19043("$)',
    r'\g<1>19045\2',
    text,
    flags=re.MULTILINE,
)
if count == 0:
    raise SystemExit('No CurrentBuild 19043 values found')
path.write_text(text, errors='surrogateescape')
PY
```

Verify:

```bash
grep -E '"CurrentBuild"|"CurrentBuildNumber"' "$PFX/system.reg"
```

Every relevant value must be `19045`.

## 7. Add global DLL overrides

Use the copied wrapper's Wine runtime:

```bash
WINE="$APP/Contents/SharedSupport/wine/bin/wine64"
export WINEPREFIX="$PFX"

"$WINE" reg add 'HKCU\Software\Wine\DllOverrides' \
  /v '*d3d12' /t REG_SZ /d 'native,builtin' /f
"$WINE" reg add 'HKCU\Software\Wine\DllOverrides' \
  /v '*dxgi' /t REG_SZ /d 'native,builtin' /f
"$WINE" reg add 'HKCU\Software\Wine\DllOverrides' \
  /v '*d3d12core' /t REG_SZ /d 'native,builtin' /f
```

Remove conflicting per-application overrides left by earlier experiments. The effective global entries in `user.reg` must be:

```text
"*d3d12"="native,builtin"
"*d3d12core"="native,builtin"
"*dxgi"="native,builtin"
```

## 8. Patch `dxil.dll`

This patch is specific to the tested game DLL. Do not blindly apply it after a game update.

Original hash:

```text
9cccc7ef419da73fa314fdaecae831c6c20206ae70732c9093f95193378ced10
```

Create a backup and run the deterministic patch:

```bash
DXIL="$GAME/dxil.dll"
ORIGINAL_HASH='9cccc7ef419da73fa314fdaecae831c6c20206ae70732c9093f95193378ced10'
ACTUAL_HASH=$(shasum -a 256 "$DXIL" | awk '{print $1}')
test "$ACTUAL_HASH" = "$ORIGINAL_HASH"
test ! -e "$GAME/dxil.dll.original"
cp -p "$DXIL" "$GAME/dxil.dll.original"
python3 - "$DXIL" <<'PY'
from pathlib import Path
import hashlib
import struct
import sys
import pefile

EXPECTED = '9cccc7ef419da73fa314fdaecae831c6c20206ae70732c9093f95193378ced10'
path = Path(sys.argv[1])
data = bytearray(path.read_bytes())
if hashlib.sha256(data).hexdigest() != EXPECTED:
    raise SystemExit('Refusing to patch an unknown dxil.dll')
pe = pefile.PE(data=data)
imports = pe.OPTIONAL_HEADER.DATA_DIRECTORY[
    pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']
]

if any(entry.dll.lower() == b'd3d12core.dll' for entry in pe.DIRECTORY_ENTRY_IMPORT):
    raise SystemExit('dxil.dll is already patched')

entries = []
for entry in pe.DIRECTORY_ENTRY_IMPORT:
    descriptor = entry.struct
    entries.append(struct.pack(
        '<IIIII',
        descriptor.OriginalFirstThunk,
        descriptor.TimeDateStamp,
        descriptor.ForwarderChain,
        descriptor.Name,
        descriptor.FirstThunk,
    ))

if len(entries) != 10:
    raise SystemExit(f'Expected 10 imports, found {len(entries)}')

base = 0x1466A0
capacity = 0x160
rdata = next(section for section in pe.sections
             if section.Name.rstrip(b'\0') == b'.rdata')
if not (rdata.VirtualAddress <= base and
        base + capacity <= rdata.VirtualAddress + rdata.SizeOfRawData):
    raise SystemExit('Patch range is outside the raw .rdata section')
offset = pe.get_offset_from_rva(base)
if len(data[offset:offset + capacity]) != capacity:
    raise SystemExit('Patch range is truncated')
if any(data[offset:offset + capacity]):
    raise SystemExit('Expected zero-filled .rdata tail is not empty')

table_size = (len(entries) + 2) * 20
ilt = base + table_size
iat = ilt + 16
dll = iat + 16
name = (dll + len(b'D3D12Core.dll\0') + 1) & ~1

blob = bytearray(b''.join(entries))
blob += struct.pack('<IIIII', ilt, 0, 0, dll, iat)
blob += b'\0' * 20
blob += struct.pack('<QQ', name, 0)
blob += struct.pack('<QQ', name, 0)
blob += b'D3D12Core.dll\0'
while base + len(blob) < name:
    blob += b'\0'
blob += struct.pack('<H', 0) + b'D3D12SDKVersion\0'

data[offset:offset + len(blob)] = blob
struct.pack_into('<II', data, imports.get_file_offset(), base, table_size)

virtual_size = (base - rdata.VirtualAddress) + len(blob)
struct.pack_into('<I', data, rdata.get_file_offset() + 8, virtual_size)
path.write_bytes(data)
PY

PATCHED_HASH='844f55227c67036f9466f25f655ee9156355cac04de21a35b230579649010190'
test "$(shasum -a 256 "$DXIL" | awk '{print $1}')" = "$PATCHED_HASH"
```

Expected patched hash:

```text
844f55227c67036f9466f25f655ee9156355cac04de21a35b230579649010190
```

Verify the new import:

```bash
objdump -p "$DXIL" | grep -E 'D3D12Core.dll|D3D12SDKVersion'
shasum -a 256 "$DXIL"
```

## 9. Start and verify

Start the complete wrapper. Do not launch the game with a second Wine engine.

```bash
open -n '/Applications/Pioneers of Pagonia.app'
```

Steam starts Pagonia with:

```text
-applaunch 2155180 -NoDX12DeviceFactory
```

Optional diagnostics before launch:

```bash
launchctl setenv D3DM_LOGLEVEL_INFO 1
launchctl setenv D3DM_DXIL_PROCESS_DEBUG_INFORMATION 1
launchctl setenv OS_ACTIVITY_DT_MODE YES
```

Remove the diagnostic variables after testing so that they do not affect later applications:

```bash
launchctl unsetenv D3DM_LOGLEVEL_INFO
launchctl unsetenv D3DM_DXIL_PROCESS_DEBUG_INFORMATION
launchctl unsetenv OS_ACTIVITY_DT_MODE
```

The wrapper log is:

```text
/Applications/Pioneers of Pagonia.app/Contents/SharedSupport/Logs/LastRunWine.log
```

Success indicators:

```text
Created D3D12Device
Created D3D12 Swapchain
```

Failure indicators from the old setup:

```text
No Compatible Graphics Hardware Was Found
NVIDIA GeForce 6800
Device creation failed: 0x80004005
Unhandled page fault
irconverter_hull_shader: Failed to materializeAll
```

## 10. Backups and update safety

Keep backups of at least:

- the original wrapper engine;
- `system.reg` and `user.reg`;
- original `dxil.dll`;
- `dxgi.dll` and `d3d12.dll`;
- the complete working application before Steam or game updates.

Steam file verification or a Pagonia update can replace `dxil.dll`. Recheck its original hash before patching. A GPTK overlay update can replace D3DMetal. A Wine engine update can break the compatibility that made this setup work.

## Why this exact Wine build is required

The precise root cause inside Wine has not been reduced to one source-code change, so it would be inaccurate to claim that Wine 10.0.3 is universally incompatible. The tests establish the following:

1. Direct GPTK Wine 7.7 could not run the current Steam client reliably.
2. Sikarugir 10.0.3 could run Steam, but the mixed/direct GPTK game path crashed with a null page fault or fell back to WineD3D.
3. The older Wineskin runtime plus its launcher created the D3D12 device and swapchain successfully.
4. The binaries are genuinely different despite similar version strings.

Examples:

```text
                           working build                         Sikarugir 10.0.3
wine64 SHA-256             08bbcc27...8318300                   cddc8485...654a4
ntdll.so SHA-256           cf836b07...279e                     213b89fd...7aebb
ntdll.dll SHA-256          5549f994...a5da                     315e1e54...532d
```

GPTK is more than `D3DMetal.framework`. Its PE modules, Unix-side Wine modules, loader behavior, environment, DLL search order, and Wineskin launcher must cooperate. Replacing only selected pieces creates an untested ABI and loader combination. The working wrapper preserves that compatibility set and overlays only the GPTK beta 3 components documented above.

Therefore the practical rule is:

> Identify Wine builds by their complete runtime and hashes, not by `wine --version`, and never combine Steam from one running Wine server with a game launched by another engine.
