#!/bin/bash
# Deploy Pioneers of Pagonia for Windows Steam on macOS with GPTK 4.0b3.
# Supports a verified existing game prefix as an optional fast path; otherwise
# installs Steam and the game interactively into a new compatible base prefix.

set -euo pipefail

# Do not resolve security-sensitive tools through an inherited search path.
export PATH='/usr/bin:/bin:/usr/sbin:/sbin'
OPEN_COMMAND=${PAGONIA_OPEN_COMMAND:-/usr/bin/open}
PGREP_COMMAND=${PAGONIA_PGREP_COMMAND:-/usr/bin/pgrep}
SLEEP_COMMAND=${PAGONIA_SLEEP_COMMAND:-/bin/sleep}

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd -P)
SOURCE_PREFIX=''
GPTK_LIB=''
ENGINE_ARCHIVE_NAME='WS12WineSikarugir10.0_2-20251028-pagonia.tar.xz'
WRAPPER_ARCHIVE_NAME='Wineskin-3.0.6-2.app.tar.xz'
ENGINE_ARCHIVE="$SCRIPT_DIR/$ENGINE_ARCHIVE_NAME"
WRAPPER_ARCHIVE="$SCRIPT_DIR/$WRAPPER_ARCHIVE_NAME"
GPTK_HASH_MANIFEST="$SCRIPT_DIR/gptk-4.0b3-SHA256SUMS"
GPTK_LINK_MANIFEST="$SCRIPT_DIR/gptk-4.0b3-SYMLINKS"
GPTK_LIB_EXPLICIT=0
GPTK_DOWNLOAD_URL='https://developer.apple.com/download/all/?q=Game%20Porting%20Toolkit'
GPTK_DEFAULT_LIB='/Volumes/Evaluation environment for Windows games 4.0 beta 3/redist/lib'
DESTINATION='/Applications/Pioneers of Pagonia.app'
STEAM_INSTALLER_URL='https://cdn.akamai.steamstatic.com/client/installer/SteamSetup.exe'
REPLACE=0
ASSUME_YES=0
LAUNCH_TEST=1
FORCE_FRESH=0

EXPECTED_ENGINE_ARCHIVE='0598a60af56d67b1efd35ac0751cbcc34a30a0329e2788e182dd67a5698f9353'
EXPECTED_WRAPPER_ARCHIVE='dc97a4ff0f75b74a62b8571d4fe56387648f3755169e1dd8186b8f3d39aa597b'
EXPECTED_GPTK_HASH_MANIFEST='702296dc74d7522c43eb95d7ae1d697cd4ac1eb5523d643c47fc9c13ff89432c'
EXPECTED_GPTK_LINK_MANIFEST='26fbf032714eccd6254d3a1745cb39c12b886e58a6cec747ed4e15744a4bc952'
EXPECTED_STEAM_SETUP='7d3654531c32d941b8cae81c4137fc542172bfa9635f169cb392f245a0a12bcb'
EXPECTED_BUILD_ID='25784167'
EXPECTED_GAME_EXE='a4c8aa367a7164e3621ff86819bd5135616da0b1a4afea6b14f0eeb5e9901f46'
EXPECTED_WINESKIN_LAUNCHER='217d7f3cf154d7117103934c9ec9b952b7209412132f2ad61565fb24d6e56697'
EXPECTED_WINE64='08bbcc27b5a76e4473e8003007e140f74b529d67a164256d86d5163d88518300'
EXPECTED_WINESERVER='dcfd293ca9d7dc29bb9fb1a413850319c85c9823368a8f1a76bb22339b64cd45'
EXPECTED_NTDLL_UNIX='cf836b0727c47f4d9fb667628de226395697a6a5089678acea09ae32a7fb279e'
EXPECTED_NTDLL_WINDOWS='5549f99494e8e004cd112e72f0d721f6ffbb1bab1487871bff9f7d80c0b6a5da'
EXPECTED_ORIGINAL_DXIL='9cccc7ef419da73fa314fdaecae831c6c20206ae70732c9093f95193378ced10'
EXPECTED_DXGI='d53d9ea91935f0de126ba528264fc4c9b4dfea8bfe43f3f1256bd3e8963d67ee'
EXPECTED_D3D12='3174fac027d3ff10971645ac41b665cd53949c87d6d2d7d53b0073bf4bb36981'
EXPECTED_ENGINE_CORE='b8cabb79a3f0a14babcbfd575cca70814e4d1d3e71606dfc1670421aaa39b97e'
LAUNCH_OPTIONS='-NoDX12DeviceFactory -NoDX12SDKVersionCheck'

usage() {
  cat <<'EOF'
Usage: install-pagonia-gptk4b3.sh [options]

Options:
  --source-prefix PATH  Explicitly reuse a trusted local Pagonia prefix.
  --fresh               Install Steam/game anew (the default).
  --gptk-lib PATH       GPTK 4.0 beta 3 redist/lib directory.
  --destination PATH    Destination .app path.
  --replace             Back up and replace an existing destination.
  --no-launch           Install without the final interactive Steam Play test.
  -y, --yes             Accept the deployment plan non-interactively.
  -h, --help            Show this help.

Default behavior:
  1. Verify the bundled, exact known-good Wine/Wineskin runtime.
  2. Verify the user-supplied GPTK 4.0b3 runtime.
  3. Reuse a prefix only when explicitly supplied as trusted input.
  4. Otherwise install pinned official Windows Steam and wait for the user to
     sign in and install Pioneers of Pagonia.
  5. Configure the two game-provided D3D12 bypasses in Steam LaunchOptions.
  6. Create a Pagonia application icon and register the app with Launch Services.
  7. Launch Pagonia directly through its macOS application icon.
  8. Succeed only after D3D12 device and swapchain creation are logged.
EOF
}

while (($#)); do
  case "$1" in
    --source-prefix) SOURCE_PREFIX=${2:?Missing path}; shift ;;
    --fresh) FORCE_FRESH=1 ;;
    --gptk-lib) GPTK_LIB=${2:?Missing path}; GPTK_LIB_EXPLICIT=1; shift ;;
    --destination) DESTINATION=${2:?Missing path}; shift ;;
    --replace) REPLACE=1 ;;
    --no-launch) LAUNCH_TEST=0 ;;
    -y|--yes) ASSUME_YES=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

[[ -z "$GPTK_LIB" ]] || GPTK_LIB=${GPTK_LIB%/}
DESTINATION=${DESTINATION%/}
[[ -z "$SOURCE_PREFIX" ]] || SOURCE_PREFIX=${SOURCE_PREFIX%/}
WORK_ROOT=''
STAGING=''
BACKUP=''
BACKUP_MOVED=0
PUBLISHED=0
PUBLISHED_DEVICE=''
PUBLISHED_INODE=''
SUCCESS=0
STEAM_SETUP_DOWNLOAD=''

sha256() { shasum -a 256 "$1" | awk '{print $1}'; }

require_file() {
  [[ -f "$1" && ! -L "$1" ]] || {
    echo "ERROR: Missing, non-regular, or symbolic-link file: $1" >&2
    exit 1
  }
}

require_dir() {
  [[ -d "$1" && ! -L "$1" ]] || {
    echo "ERROR: Missing or symbolic-link directory: $1" >&2
    exit 1
  }
}

require_hash() {
  local path=$1 expected=$2 actual
  require_file "$path"
  actual=$(sha256 "$path")
  if [[ "$actual" != "$expected" ]]; then
    echo "ERROR: Unexpected hash for $path" >&2
    echo "Expected: $expected" >&2
    echo "Actual:   $actual" >&2
    exit 1
  fi
}

verify_archive_layout() {
  local archive=$1 expected_root=$2 max_expanded=$3
  python3 - "$archive" "$expected_root" "$max_expanded" <<'PY'
import posixpath
import stat
import sys
import tarfile

archive, expected_root, max_expanded = sys.argv[1], sys.argv[2], int(sys.argv[3])
seen = set()
total = 0
with tarfile.open(archive, 'r:*') as handle:
    for member in handle:
        normalized = posixpath.normpath(member.name)
        if (normalized.startswith('/') or normalized in ('.', '..') or
                normalized.startswith('../') or
                not (normalized == expected_root or
                     normalized.startswith(expected_root + '/'))):
            raise SystemExit(f'Unsafe archive member path: {member.name}')
        if normalized in seen:
            raise SystemExit(f'Duplicate archive member: {member.name}')
        seen.add(normalized)
        total += max(member.size, 0)
        if total > max_expanded:
            raise SystemExit('Archive exceeds the permitted expanded size')
        if member.isdev() or member.mode & (stat.S_ISUID | stat.S_ISGID):
            raise SystemExit(f'Unsafe archive member type/mode: {member.name}')
        if member.islnk():
            raise SystemExit(f'Archive hard links are not permitted: {member.name}')
        if member.issym():
            target = posixpath.normpath(
                posixpath.join(posixpath.dirname(normalized), member.linkname)
            )
            if not (target == expected_root or target.startswith(expected_root + '/')):
                raise SystemExit(f'Escaping archive link: {member.name} -> {member.linkname}')
            stripped = normalized.removeprefix(expected_root).lstrip('/')
            stripped_target = posixpath.normpath(
                posixpath.join(posixpath.dirname(stripped), member.linkname)
            )
            if stripped_target == '..' or stripped_target.startswith('../'):
                raise SystemExit(f'Link escapes after root stripping: {member.name}')
if not seen:
    raise SystemExit('Archive is empty')
PY
}

verify_gptk_lib() {
  local path=${1%/}
  [[ "$path" == /Volumes/*/redist/lib ]] || {
    echo "GPTK must be on a mounted volume: $path" >&2
    return 1
  }
  [[ -d "$path/external" && ! -L "$path/external" \
     && -d "$path/wine" && ! -L "$path/wine" \
     && ! -w "$path" ]] || {
    echo "GPTK library is missing, linked, or writable: $path" >&2
    return 1
  }
  python3 - "$path" "$GPTK_HASH_MANIFEST" "$GPTK_LINK_MANIFEST" <<'PY'
from hashlib import sha256
from pathlib import Path
import os
import plistlib
import stat
import subprocess
import sys

root = Path(sys.argv[1])
df = subprocess.run(['/bin/df', str(root)], check=True, text=True,
                    capture_output=True).stdout.splitlines()
if len(df) < 2:
    raise SystemExit('Could not identify GPTK filesystem')
device = df[-1].split()[0]
info = plistlib.loads(subprocess.run(
    ['/usr/sbin/diskutil', 'info', '-plist', device], check=True,
    capture_output=True).stdout)
mount = Path(info.get('MountPoint', '')).resolve(strict=True)
if info.get('Writable', True) or info.get('WritableVolume', True):
    raise SystemExit(f'GPTK filesystem is writable: {mount}')
resolved_root = root.resolve(strict=True)
if mount != resolved_root and mount not in resolved_root.parents:
    raise SystemExit(f'GPTK path is not on its reported mount: {resolved_root}')
expected_hashes = {}
for line in Path(sys.argv[2]).read_text().splitlines():
    digest, name = line.split('  ', 1)
    expected_hashes[name] = digest
expected_links = {}
for line in Path(sys.argv[3]).read_text().splitlines():
    name, target = line.split('\t', 1)
    expected_links[name] = target
actual_hashes = {}
actual_links = {}
for base in ('external', 'wine'):
    for current, dirs, files in os.walk(root / base, followlinks=False):
        for name in dirs + files:
            path = Path(current) / name
            rel = path.relative_to(root).as_posix()
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                actual_links[rel] = os.readlink(path)
            elif stat.S_ISREG(mode):
                actual_hashes[rel] = sha256(path.read_bytes()).hexdigest()
            elif not stat.S_ISDIR(mode):
                raise SystemExit(f'Unsupported GPTK file type: {rel}')
if actual_hashes != expected_hashes:
    missing = sorted(expected_hashes.keys() - actual_hashes.keys())
    extra = sorted(actual_hashes.keys() - expected_hashes.keys())
    changed = sorted(k for k in expected_hashes.keys() & actual_hashes.keys()
                     if expected_hashes[k] != actual_hashes[k])
    raise SystemExit(f'GPTK file manifest mismatch: missing={missing}, extra={extra}, changed={changed}')
if actual_links != expected_links:
    raise SystemExit(f'GPTK symlink manifest mismatch: expected={expected_links}, actual={actual_links}')
PY
  local executable count=0
  while IFS= read -r -d '' executable; do
    if file "$executable" | grep -q 'Mach-O'; then
      codesign --verify --strict -R='anchor apple' "$executable" 2>/dev/null || {
        echo "GPTK executable is not validly Apple-signed: $executable" >&2
        return 1
      }
      count=$((count + 1))
    fi
  done < <(find "$path/external" "$path/wine" -type f -print0)
  [[ $count -eq 6 ]] || {
    echo "Expected 6 Apple-signed GPTK Mach-O files, found $count" >&2
    return 1
  }
}

is_expected_gptk_lib() {
  verify_gptk_lib "${1%/}" >/dev/null
}

find_mounted_gptk_lib() {
  local candidate
  if is_expected_gptk_lib "$GPTK_DEFAULT_LIB"; then
    printf '%s\n' "$GPTK_DEFAULT_LIB"
    return 0
  fi
  while IFS= read -r -d '' candidate; do
    if is_expected_gptk_lib "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done < <(find /Volumes -mindepth 3 -maxdepth 4 -type d \
    -path '*/redist/lib' -print0 2>/dev/null)
  return 1
}

find_downloaded_gptk_dmg() {
  python3 - "$HOME/Downloads" <<'PY'
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
if not root.is_dir():
    raise SystemExit(1)
for path in sorted(root.glob('*.dmg'), key=lambda item: item.stat().st_mtime,
                   reverse=True):
    normalized = re.sub(r'[^a-z0-9]+', ' ', path.name.lower())
    product = ('game porting toolkit' in normalized or
               'evaluation environment for windows games' in normalized)
    version = re.search(r'\b4(?: 0)? beta 3\b', normalized)
    if product and version and path.is_file() and not path.is_symlink():
        print(path)
        break
else:
    raise SystemExit(1)
PY
}

mount_gptk_dmg() {
  local dmg=$1 output
  echo "Mounting GPTK disk image: $dmg" >&2
  if ! output=$(diskutil image attach --nobrowse --readOnly "$dmg" 2>&1); then
    echo "$output" >&2
    return 1
  fi
  echo "$output" >&2
  find_mounted_gptk_lib
}

resolve_gptk_lib() {
  local found='' dmg=''
  if [[ $GPTK_LIB_EXPLICIT -eq 1 ]]; then
    if ! is_expected_gptk_lib "$GPTK_LIB"; then
      echo "ERROR: --gptk-lib is not the verified GPTK 4.0 beta 3 library: $GPTK_LIB" >&2
      exit 1
    fi
    return
  fi
  if found=$(find_mounted_gptk_lib); then
    GPTK_LIB=$found
    return
  fi
  if dmg=$(find_downloaded_gptk_dmg) && found=$(mount_gptk_dmg "$dmg"); then
    GPTK_LIB=$found
    return
  fi
  if [[ $ASSUME_YES -eq 1 || ! -t 0 ]]; then
    echo 'ERROR: Game Porting Toolkit 4.0 beta 3 is not mounted and its DMG was not found in ~/Downloads.' >&2
    echo "Download it manually from: $GPTK_DOWNLOAD_URL" >&2
    exit 1
  fi
  "$OPEN_COMMAND" "$GPTK_DOWNLOAD_URL"
  while true; do
    echo
    echo 'Download “Game Porting Toolkit 4.0 beta 3” from Apple.'
    echo 'Save the DMG in your Downloads folder, then return here.'
    printf 'Press Enter after the download is complete (or type q to quit): '
    IFS= read -r answer
    [[ "$answer" != 'q' && "$answer" != 'Q' ]] || exit 0
    if dmg=$(find_downloaded_gptk_dmg) && found=$(mount_gptk_dmg "$dmg"); then
      GPTK_LIB=$found
      return
    fi
    echo 'The verified GPTK 4.0 beta 3 DMG was not found. Please try again.' >&2
  done
}

yes_no() {
  local prompt=$1 default=${2:-no} answer
  if [[ $ASSUME_YES -eq 1 ]]; then
    [[ "$default" == 'yes' ]]
    return
  fi
  if [[ ! -t 0 ]]; then
    echo 'ERROR: A required question cannot be asked without a terminal.' >&2
    echo 'Rerun interactively or use explicit options with --yes.' >&2
    exit 1
  fi
  if [[ "$default" == 'yes' ]]; then
    printf '%s [Y/n] ' "$prompt"
  else
    printf '%s [y/N] ' "$prompt"
  fi
  read -r answer
  if [[ -z "$answer" ]]; then
    [[ "$default" == 'yes' ]]
  else
    case "$answer" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
  fi
}

atomic_rename_exclusive() {
  python3 - "$1" "$2" <<'PY'
import ctypes
import os
import sys

source, destination = map(os.path.abspath, sys.argv[1:3])
source_parent, source_name = os.path.split(source)
destination_parent, destination_name = os.path.split(destination)
flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
source_fd = os.open(source_parent, flags)
destination_fd = os.open(destination_parent, flags)
try:
    libc = ctypes.CDLL(None, use_errno=True)
    renameatx_np = libc.renameatx_np
    renameatx_np.argtypes = [ctypes.c_int, ctypes.c_char_p,
                             ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameatx_np.restype = ctypes.c_int
    RENAME_EXCL = 0x00000004
    if renameatx_np(source_fd, os.fsencode(source_name),
                    destination_fd, os.fsencode(destination_name),
                    RENAME_EXCL) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), destination)
finally:
    os.close(source_fd)
    os.close(destination_fd)
PY
}

same_identity() {
  local path=$1 device=$2 inode=$3
  [[ -e "$path" && ! -L "$path" \
     && "$(stat -f '%d' "$path")" == "$device" \
     && "$(stat -f '%i' "$path")" == "$inode" ]]
}

unique_sibling_path() {
  python3 - "$1" "$2" <<'PY'
from pathlib import Path
import secrets
import sys

path = Path(sys.argv[1])
print(f'{path}.{sys.argv[2]}-{secrets.token_hex(12)}')
PY
}

validate_destination() {
  python3 - "$1" "$(id -u)" <<'PY'
from pathlib import Path
import grp
import os
import stat
import sys

raw = sys.argv[1]
uid = int(sys.argv[2])
if not raw.startswith('/') or not raw.endswith('.app'):
    raise SystemExit('Destination must be an absolute .app path')
path = Path(raw)
parent = path.parent.resolve(strict=True)
if parent != path.parent:
    raise SystemExit('Destination parent must not contain symbolic links')
info = parent.stat()
if info.st_mode & stat.S_IWOTH:
    raise SystemExit('Destination parent must not be world-writable')
if info.st_uid not in (0, uid):
    raise SystemExit('Destination parent must be owned by root or the current user')
if info.st_mode & stat.S_IWGRP:
    group = grp.getgrgid(info.st_gid).gr_name
    if info.st_uid != 0 or group not in ('admin', 'wheel'):
        raise SystemExit('Destination parent has an untrusted writable group')
print(parent / path.name)
PY
}

validate_trusted_prefix_paths() {
  python3 - "$1" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve(strict=True)
critical = [
    'system.reg', 'user.reg',
    'drive_c/windows/system32',
    'drive_c/windows/system32/dxgi.dll',
    'drive_c/windows/system32/d3d12.dll',
    'drive_c/windows/system32/d3d12core.dll',
    'drive_c/Program Files (x86)/Steam/steam.exe',
    'drive_c/Program Files (x86)/Steam/steamapps/appmanifest_2155180.acf',
    'drive_c/Program Files (x86)/Steam/steamapps/common/Pioneers of Pagonia/Pioneers of Pagonia.exe',
    'drive_c/Program Files (x86)/Steam/steamapps/common/Pioneers of Pagonia/dxil.dll',
]
steam = root / 'drive_c/Program Files (x86)/Steam'
critical.extend(str(path.relative_to(root))
                for path in steam.glob('userdata/*/config/localconfig.vdf'))
for relative in critical:
    path = root / relative
    current = root
    for part in Path(relative).parts:
        current /= part
        if current.is_symlink():
            raise SystemExit(f'Critical prefix path is a symbolic link: {current}')
    resolved = path.resolve(strict=True)
    if root != resolved and root not in resolved.parents:
        raise SystemExit(f'Critical prefix path escapes prefix: {path}')
PY
}

cleanup() {
  local status=$?
  if [[ $PUBLISHED -eq 1 && $SUCCESS -ne 1 ]]; then
    local deployed_prefix failed
    if same_identity "$DESTINATION" "$PUBLISHED_DEVICE" "$PUBLISHED_INODE"; then
      deployed_prefix="$DESTINATION/Contents/SharedSupport/prefix"
      if [[ -x "$DESTINATION/Contents/SharedSupport/wine/bin/wineserver" ]]; then
        WINEPREFIX="$deployed_prefix" \
          "$DESTINATION/Contents/SharedSupport/wine/bin/wineserver" -k \
          2>/dev/null || true
      fi
      failed=$(unique_sibling_path "$DESTINATION" failed)
      if atomic_rename_exclusive "$DESTINATION" "$failed"; then
        echo "Failed deployment preserved at: $failed" >&2
      else
        echo "ERROR: Could not preserve failed deployment; left untouched: $DESTINATION" >&2
      fi
    else
      echo "ERROR: Published destination identity changed; cleanup left it untouched: $DESTINATION" >&2
    fi
    if [[ -n "$BACKUP" && -e "$BACKUP" && ! -e "$DESTINATION" ]]; then
      if atomic_rename_exclusive "$BACKUP" "$DESTINATION"; then
        echo "Previous deployment restored: $DESTINATION" >&2
      else
        echo "ERROR: Could not restore previous deployment: $BACKUP" >&2
      fi
    fi
  elif [[ $BACKUP_MOVED -eq 1 && -n "$BACKUP" \
          && -e "$BACKUP" && ! -e "$DESTINATION" ]]; then
    if atomic_rename_exclusive "$BACKUP" "$DESTINATION"; then
      BACKUP_MOVED=0
      echo "Previous deployment restored after interrupted publication: $DESTINATION" >&2
    else
      echo "ERROR: Interrupted publication left backup at: $BACKUP" >&2
    fi
  fi
  if [[ -n "$WORK_ROOT" && -e "$WORK_ROOT" ]]; then
    if [[ -d "$WORK_ROOT" && ! -L "$WORK_ROOT" \
          && "$WORK_ROOT" == /tmp/Pagonia-GPTK4b3-deployment.* \
          && "$(stat -f '%u' "$WORK_ROOT")" == "$UID" ]]; then
      if [[ $status -eq 0 && $SUCCESS -eq 1 ]]; then
        rm -rf "$WORK_ROOT"
      else
        echo "Incomplete deployment preserved for resume: $WORK_ROOT" >&2
        echo "Its Wine prefix is: $STAGING/Contents/SharedSupport/prefix" >&2
      fi
    else
      echo "ERROR: Refusing to clean unexpected work path: $WORK_ROOT" >&2
    fi
  fi
  if [[ -n "$STEAM_SETUP_DOWNLOAD" && -e "$STEAM_SETUP_DOWNLOAD" ]]; then
    if [[ $status -eq 0 && $SUCCESS -eq 1 ]]; then
      rm -f "$STEAM_SETUP_DOWNLOAD"
    else
      echo "Steam installer cache preserved: $STEAM_SETUP_DOWNLOAD" >&2
    fi
  fi
  return "$status"
}
on_signal() {
  exit 130
}
trap cleanup EXIT
trap on_signal INT TERM

if [[ $EUID -eq 0 ]]; then
  echo 'ERROR: Do not run this installer with sudo or as root.' >&2
  exit 1
fi
DESTINATION=$(validate_destination "$DESTINATION")
DESTINATION_PARENT=$(dirname "$DESTINATION")
if [[ "$(stat -f '%d' /tmp)" != "$(stat -f '%d' "$DESTINATION_PARENT")" ]]; then
  echo 'ERROR: Destination must be on the same filesystem as /tmp for atomic publication.' >&2
  exit 1
fi

stop_if_running() {
  if "$PGREP_COMMAND" -u "$UID" -f 'Steam\.exe|Pioneers of Pagonia\.exe|winedbg' >/dev/null; then
    echo 'ERROR: Windows Steam or Pioneers of Pagonia is running. Exit it first.' >&2
    ps -U "$UID" -o pid=,command= \
      | grep -E '[S]team\.exe|[P]ioneers of Pagonia\.exe|[w]inedbg' >&2 || true
    exit 1
  fi
}

validate_game() {
  local prefix=$1 steam game manifest build
  steam="$prefix/drive_c/Program Files (x86)/Steam"
  game="$steam/steamapps/common/Pioneers of Pagonia"
  manifest="$steam/steamapps/appmanifest_2155180.acf"
  require_file "$steam/steam.exe"
  require_file "$manifest"
  build=$(awk -F'"' '/"buildid"/{print $4; exit}' "$manifest")
  [[ "$build" == "$EXPECTED_BUILD_ID" ]] || {
    echo "ERROR: Expected game build $EXPECTED_BUILD_ID, found $build." >&2
    return 1
  }
  require_hash "$game/Pioneers of Pagonia.exe" "$EXPECTED_GAME_EXE"
  require_hash "$game/dxil.dll" "$EXPECTED_ORIGINAL_DXIL"
  python3 - "$game/Pioneers of Pagonia.exe" <<'PY'
from pathlib import Path
import sys

data = Path(sys.argv[1]).read_bytes()
for option in ('-NoDX12DeviceFactory', '-NoDX12SDKVersionCheck'):
    if option.encode('utf-16le') not in data:
        raise SystemExit(f'Game executable does not implement {option}')
PY
}

stop_if_running

# GPTK requires the user's Apple download. Wine and Wineskin are bundled next
# to this script and must match the pinned archive hashes exactly.
require_hash "$GPTK_HASH_MANIFEST" "$EXPECTED_GPTK_HASH_MANIFEST"
require_hash "$GPTK_LINK_MANIFEST" "$EXPECTED_GPTK_LINK_MANIFEST"
require_hash "$WRAPPER_ARCHIVE" "$EXPECTED_WRAPPER_ARCHIVE"
require_hash "$ENGINE_ARCHIVE" "$EXPECTED_ENGINE_ARCHIVE"
verify_archive_layout "$WRAPPER_ARCHIVE" 'Wineskin-3.0.6-2.app' 300000000
verify_archive_layout "$ENGINE_ARCHIVE" 'wswine.bundle' 900000000
resolve_gptk_lib
verify_gptk_lib "$GPTK_LIB"

REUSE_PREFIX=0
if [[ $FORCE_FRESH -eq 0 && -n "$SOURCE_PREFIX" ]]; then
  SOURCE_PREFIX=$(python3 - "$SOURCE_PREFIX" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve(strict=True))
PY
)
  validate_trusted_prefix_paths "$SOURCE_PREFIX"
  validate_game "$SOURCE_PREFIX"
  if [[ $ASSUME_YES -eq 1 ]] \
     || yes_no "Trust and reuse the explicitly supplied prefix $SOURCE_PREFIX?" no; then
    REUSE_PREFIX=1
  else
    echo 'Cancelled.'
    exit 0
  fi
fi

DEST_INITIAL_EXISTS=0
DEST_INITIAL_DEVICE=''
DEST_INITIAL_INODE=''
if [[ -e "$DESTINATION" ]]; then
  [[ ! -L "$DESTINATION" ]] || {
    echo "ERROR: Destination must not be a symbolic link: $DESTINATION" >&2
    exit 1
  }
  DEST_INITIAL_EXISTS=1
  DEST_INITIAL_DEVICE=$(stat -f '%d' "$DESTINATION")
  DEST_INITIAL_INODE=$(stat -f '%i' "$DESTINATION")
  if [[ $REPLACE -ne 1 ]]; then
    if yes_no "Back up and replace existing $DESTINATION?" no; then
      REPLACE=1
    else
      echo 'Cancelled.'
      exit 0
    fi
  fi
fi

cat <<EOF

Deployment plan
  Wine engine:   $ENGINE_ARCHIVE
  Wineskin:      $WRAPPER_ARCHIVE
  Prefix mode:   $([[ $REUSE_PREFIX -eq 1 ]] && echo "reuse $SOURCE_PREFIX" || echo 'fresh Steam/game installation')
  GPTK library:  $GPTK_LIB
  Destination:   $DESTINATION
  Game build:    $EXPECTED_BUILD_ID
  Steam options: $LAUNCH_OPTIONS
  Launch test:   $([[ $LAUNCH_TEST -eq 1 ]] && echo enabled || echo disabled)
EOF
if [[ $ASSUME_YES -ne 1 ]] && ! yes_no 'Continue?' no; then
  echo 'Cancelled.'
  exit 0
fi

WORK_ROOT=$(mktemp -d '/tmp/Pagonia-GPTK4b3-deployment.XXXXXX')
chmod 700 "$WORK_ROOT"
STAGING="$WORK_ROOT/Pioneers of Pagonia.app"
mkdir -m 700 "$STAGING"
INPUT_SNAPSHOT="$WORK_ROOT/verified-inputs"
ENGINE_EXTRACT=$(mktemp -d "$WORK_ROOT/engine.XXXXXX")
mkdir -m 700 "$INPUT_SNAPSHOT"
cp -p "$WRAPPER_ARCHIVE" "$INPUT_SNAPSHOT/$WRAPPER_ARCHIVE_NAME"
cp -p "$ENGINE_ARCHIVE" "$INPUT_SNAPSHOT/$ENGINE_ARCHIVE_NAME"
require_hash "$INPUT_SNAPSHOT/$WRAPPER_ARCHIVE_NAME" "$EXPECTED_WRAPPER_ARCHIVE"
require_hash "$INPUT_SNAPSHOT/$ENGINE_ARCHIVE_NAME" "$EXPECTED_ENGINE_ARCHIVE"
verify_archive_layout "$INPUT_SNAPSHOT/$WRAPPER_ARCHIVE_NAME" \
  'Wineskin-3.0.6-2.app' 300000000
verify_archive_layout "$INPUT_SNAPSHOT/$ENGINE_ARCHIVE_NAME" \
  'wswine.bundle' 900000000

printf '%s\n' '1/7 Extracting the verified Wineskin and Wine runtime...'
tar -x --strip-components 1 -f "$INPUT_SNAPSHOT/$WRAPPER_ARCHIVE_NAME" -C "$STAGING"
tar -xf "$INPUT_SNAPSHOT/$ENGINE_ARCHIVE_NAME" -C "$ENGINE_EXTRACT"
ditto "$ENGINE_EXTRACT/wswine.bundle" "$STAGING/Contents/SharedSupport/wine"
rm -rf "$ENGINE_EXTRACT" "$INPUT_SNAPSHOT"
mv "$STAGING/Contents/SharedSupport/wine/bin/wine" \
  "$STAGING/Contents/SharedSupport/wine/bin/wine64"
rm -rf "$STAGING/Contents/SharedSupport/prefix"

printf '%s\n' '2/7 Creating the Wine prefix...'
if [[ $REUSE_PREFIX -eq 1 ]]; then
  ditto "$SOURCE_PREFIX" "$STAGING/Contents/SharedSupport/prefix"
  # Consume only the private snapshot after revalidating it. The live source
  # prefix is never mutated or executed.
  validate_trusted_prefix_paths "$STAGING/Contents/SharedSupport/prefix"
  validate_game "$STAGING/Contents/SharedSupport/prefix"
else
  mkdir -p "$STAGING/Contents/SharedSupport/prefix/drive_c"
fi

APP="$STAGING"
PFX="$APP/Contents/SharedSupport/prefix"
WINE_ROOT="$APP/Contents/SharedSupport/wine"
LIB="$WINE_ROOT/lib"
STEAM="$PFX/drive_c/Program Files (x86)/Steam"
SYS="$PFX/drive_c/windows/system32"
PLIST="$APP/Contents/Info.plist"

printf '%s\n' '3/7 Configuring Wineskin and GPTK 4.0 beta 3...'
plutil -replace CFBundleName -string 'Pioneers of Pagonia' "$PLIST"
plutil -replace CFBundleDisplayName -string 'Pioneers of Pagonia' "$PLIST"
plutil -replace CFBundleIdentifier -string 'com.soad1337.pioneersofpagonia.gptk4b3' "$PLIST"
plutil -replace D3DMETAL -integer 1 "$PLIST"
plutil -replace D3DMETAL_FORCE -integer 1 "$PLIST"
plutil -replace 'Debug Mode' -bool true "$PLIST"
plutil -replace 'Symlinks In User Folder' -bool false "$PLIST"
plutil -replace WINEDEBUG -string 'fixme-all' "$PLIST"
plutil -replace WINEESYNC -integer 0 "$PLIST"
plutil -replace WINEMSYNC -integer 0 "$PLIST"
plutil -remove WINEFSYNC "$PLIST" 2>/dev/null || true
plutil -insert WINEFSYNC -integer 0 "$PLIST"
plutil -remove LSEnvironment "$PLIST" 2>/dev/null || true
plutil -insert LSEnvironment -json '{"D3DM_MTL4":"1"}' "$PLIST"
ENGINE_CORE_SOURCE="$APP/Contents/SharedSupport/d3d12core-engine.dll"
cp -p "$LIB/wine/x86_64-windows/d3d12core.dll" "$ENGINE_CORE_SOURCE"
require_hash "$ENGINE_CORE_SOURCE" "$EXPECTED_ENGINE_CORE"
rm -rf "$LIB/external" "$LIB/external.portingkit-original-backup"
ditto "$GPTK_LIB/external" "$LIB/external"
ditto "$GPTK_LIB/wine" "$LIB/wine"

if [[ $REUSE_PREFIX -eq 0 ]]; then
  printf '%s\n' '4/7 Installing official Windows Steam...'
  STEAM_SETUP_DOWNLOAD=$(mktemp '/tmp/PagoniaSteamSetup.XXXXXX')
  STEAM_SETUP="$PFX/drive_c/SteamSetup.exe"
  curl --fail --location --show-error \
    --proto '=https' --proto-redir '=https' \
    --output "$STEAM_SETUP_DOWNLOAD" "$STEAM_INSTALLER_URL"
  require_hash "$STEAM_SETUP_DOWNLOAD" "$EXPECTED_STEAM_SETUP"
  cp -p "$STEAM_SETUP_DOWNLOAD" "$STEAM_SETUP"
  plutil -replace 'Program Name and Path' -string '/SteamSetup.exe' "$PLIST"
  plutil -replace 'Program Flags' -string '/S' "$PLIST"
  rm -f "$APP/Contents/SharedSupport/Logs/LastRunWine.log"
  "$OPEN_COMMAND" -n "$APP"
  SETUP_SEEN=0
  SETUP_FINISHED=0
  for _ in $(jot 150); do
    if "$PGREP_COMMAND" -u "$UID" -f 'SteamSetup\.exe' >/dev/null; then
      SETUP_SEEN=1
    elif [[ $SETUP_SEEN -eq 1 \
            && -f "$STEAM/steam.exe" \
            && -d "$STEAM/package" ]]; then
      SETUP_FINISHED=1
      break
    fi
    "$SLEEP_COMMAND" 2
  done
  if [[ $SETUP_FINISHED -ne 1 ]]; then
    echo 'ERROR: SteamSetup did not complete cleanly within five minutes.' >&2
    exit 1
  fi
  WINEPREFIX="$PFX" "$WINE_ROOT/bin/wineserver" -k 2>/dev/null || true
  rm -f "$STEAM_SETUP" "$STEAM_SETUP_DOWNLOAD"
  STEAM_SETUP_DOWNLOAD=''
  plutil -replace 'Program Name and Path' -string '/Program Files (x86)/Steam/steam.exe' "$PLIST"
  plutil -replace 'Program Flags' -string '' "$PLIST"

  echo
  echo 'Steam is installed. It will now open for the interactive game install.'
  echo 'Sign in, install Pioneers of Pagonia (App 2155180), and let the download finish.'
  "$OPEN_COMMAND" -n "$APP"
  GAME_MANIFEST="$STEAM/steamapps/appmanifest_2155180.acf"
  GAME_DOWNLOAD_COMPLETE=0
  for _ in $(jot 10800); do
    if [[ -f "$GAME_MANIFEST" ]]; then
      STATE=$(awk -F'"' '/"StateFlags"/{print $4; exit}' "$GAME_MANIFEST" 2>/dev/null || true)
      BUILD=$(awk -F'"' '/"buildid"/{print $4; exit}' "$GAME_MANIFEST" 2>/dev/null || true)
      if [[ "$STATE" == '4' && "$BUILD" == "$EXPECTED_BUILD_ID" ]]; then
        GAME_DOWNLOAD_COMPLETE=1
        break
      fi
    fi
    "$SLEEP_COMMAND" 2
  done
  if [[ $GAME_DOWNLOAD_COMPLETE -ne 1 ]]; then
    echo "ERROR: Pagonia download did not complete as build $EXPECTED_BUILD_ID." >&2
    exit 1
  fi
  WINEPREFIX="$PFX" "$WINE_ROOT/bin/wineserver" -k 2>/dev/null || true
  "$SLEEP_COMMAND" 5
fi

printf '%s\n' '5/7 Verifying the installed game and configuring D3D12...'
validate_game "$PFX"
GAME="$STEAM/steamapps/common/Pioneers of Pagonia"
cp -p "$GPTK_LIB/wine/x86_64-windows/dxgi.dll" "$SYS/dxgi.dll"
cp -p "$GPTK_LIB/wine/x86_64-windows/d3d12.dll" "$SYS/d3d12.dll"
cp -p "$ENGINE_CORE_SOURCE" "$SYS/d3d12core.dll"
rm -f "$ENGINE_CORE_SOURCE"
# The current game supplies a supported SDK-version bypass. Remove artifacts
# from the former binary-import workaround.
rm -f "$GAME/D3D12Core.dll" "$GAME/dxil.dll.original"

printf '%s\n' '6/7 Configuring Windows, DLL overrides, and Steam Play...'
python3 - "$PFX/system.reg" "$PFX/user.reg" "$STEAM" "$LAUNCH_OPTIONS" <<'PY'
from pathlib import Path
import re
import sys

system_path, user_path, steam_path = map(Path, sys.argv[1:4])
launch_options = sys.argv[4]

system = system_path.read_text(errors='surrogateescape')
system = re.sub(
    r'("CurrentBuild(?:Number)?"=")19043("$)',
    r'\g<1>19045\2',
    system,
    flags=re.MULTILINE,
)
for name in ('CurrentBuild', 'CurrentBuildNumber'):
    values = re.findall(rf'^"{name}"="([^"]+)"$', system, flags=re.MULTILINE)
    if not values or any(value != '19045' for value in values):
        raise SystemExit(f'Failed to set every {name} value to 19045')
system_path.write_text(system, errors='surrogateescape')

user = user_path.read_text(errors='surrogateescape')
user = re.sub(
    r'(?ms)^\[Software\\\\Wine\\\\AppDefaults\\\\Pioneers of Pagonia\.exe\\\\DllOverrides\][^\n]*\n'
    r'.*?(?=^\[|\Z)',
    '',
    user,
)
section_re = re.compile(
    r'(?ms)^\[Software\\\\Wine\\\\DllOverrides\][^\n]*\n(.*?)(?=^\[|\Z)'
)
values = {
    '*d3d12': 'native,builtin',
    '*d3d12core': 'builtin',
    '*dxgi': 'native,builtin',
}
match = section_re.search(user)
if match:
    body = match.group(1)
    for key, value in values.items():
        pattern = re.compile(rf'^"{re.escape(key)}"=.*$', re.MULTILINE)
        line = f'"{key}"="{value}"'
        body = pattern.sub(line, body) if pattern.search(body) else body + line + '\n'
    user = user[:match.start(1)] + body + user[match.end(1):]
else:
    user += '\n[Software\\\\Wine\\\\DllOverrides] 0\n#time=1\n'
    user += ''.join(f'"{key}"="{value}"\n' for key, value in values.items())
verified = section_re.search(user)
if not verified or any(
    f'"{key}"="{value}"' not in verified.group(1)
    for key, value in values.items()
):
    raise SystemExit('Global DLL override verification failed')
user_path.write_text(user, errors='surrogateescape')

def brace_delta(line):
    depth = 0
    quoted = False
    escaped = False
    for char in line:
        if escaped:
            escaped = False
        elif char == '\\' and quoted:
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif not quoted and char == '{':
            depth += 1
        elif not quoted and char == '}':
            depth -= 1
    return depth

def find_blocks(lines, key, start=0, end=None):
    end = len(lines) if end is None else end
    found = []
    for index in range(start, end):
        if lines[index].strip() != f'"{key}"':
            continue
        opening = index + 1
        while opening < end and not lines[opening].strip():
            opening += 1
        if opening >= end or lines[opening].strip() != '{':
            continue
        depth = 0
        for cursor in range(opening, end):
            depth += brace_delta(lines[cursor])
            if depth == 0:
                found.append((index, opening, cursor))
                break
    return found

def one_block(lines, key, start=0, end=None):
    found = find_blocks(lines, key, start, end)
    if len(found) != 1:
        raise SystemExit(f'Expected one {key} block, found {len(found)}')
    return found[0]

localconfigs = sorted(steam_path.glob('userdata/*/config/localconfig.vdf'))
if not localconfigs:
    raise SystemExit('No Steam user localconfig.vdf found; sign in to Steam first')
for localconfig in localconfigs:
    lines = localconfig.read_text(errors='surrogateescape').splitlines(keepends=True)
    scope = (0, len(lines))
    for key in ('UserLocalConfigStore', 'Software', 'Valve', 'Steam', 'apps'):
        block = one_block(lines, key, scope[0], scope[1])
        scope = (block[1] + 1, block[2])
    apps_open = scope[0] - 1
    apps_close = scope[1]
    app_blocks = find_blocks(lines, '2155180', scope[0], scope[1])
    if len(app_blocks) > 1:
        raise SystemExit(f'Duplicate App 2155180 blocks in {localconfig}')
    app = app_blocks[0] if app_blocks else None
    apps_indent = re.match(r'\s*', lines[apps_open]).group(0)
    if app is None:
        indent = apps_indent + '\t'
        lines[apps_close:apps_close] = [
            f'{indent}"2155180"\n', f'{indent}{{\n',
            f'{indent}\t"LaunchOptions"\t\t"{launch_options}"\n',
            f'{indent}}}\n',
        ]
    else:
        _, opening, closing = app
        body = [line for line in lines[opening + 1:closing]
                if not re.match(r'^\s*"LaunchOptions"(?:\s|$)', line)]
        indent = re.match(r'\s*', lines[opening]).group(0) + '\t'
        body.insert(0, f'{indent}"LaunchOptions"\t\t"{launch_options}"\n')
        lines[opening + 1:closing] = body
    rendered = ''.join(lines)
    expected = f'"LaunchOptions"\t\t"{launch_options}"'
    if rendered.count(expected) != 1:
        raise SystemExit(f'LaunchOptions verification failed in {localconfig}')
    localconfig.write_text(rendered, errors='surrogateescape')
PY

plutil -replace 'Program Name and Path' -string '/Program Files (x86)/Steam/steam.exe' "$PLIST"
plutil -replace 'Program Flags' -string '-applaunch 2155180' "$PLIST"

# Build a native macOS icon from Steam's official Pagonia library artwork.
ARTWORK=$(find "$STEAM/appcache/librarycache/2155180" -type f \
  -name 'library_capsule.jpg' -print 2>/dev/null | head -1 || true)
if [[ -z "$ARTWORK" ]]; then
  echo 'ERROR: Steam did not provide Pagonia library artwork for the app icon.' >&2
  exit 1
fi
ICON_WORK=$(mktemp -d /tmp/PagoniaIcon.XXXXXX)
ICONSET="$ICON_WORK/Pagonia.iconset"
mkdir -p "$ICONSET"
sips -s format png --padToHeightWidth 1024 1024 --padColor 17251D \
  "$ARTWORK" --out "$ICON_WORK/source.png" >/dev/null
for spec in '16 icon_16x16.png' '32 icon_16x16@2x.png' \
            '32 icon_32x32.png' '64 icon_32x32@2x.png' \
            '128 icon_128x128.png' '256 icon_128x128@2x.png' \
            '256 icon_256x256.png' '512 icon_256x256@2x.png' \
            '512 icon_512x512.png' '1024 icon_512x512@2x.png'; do
  size=${spec%% *}
  name=${spec#* }
  sips -z "$size" "$size" "$ICON_WORK/source.png" \
    --out "$ICONSET/$name" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/Pagonia.icns"
rm -rf "$ICON_WORK"
plutil -replace CFBundleIconFile -string 'Pagonia.icns' "$PLIST"

printf '%s\n' '7/7 Verifying and publishing the deployment...'
require_hash "$APP/Contents/MacOS/wineskinlauncher" "$EXPECTED_WINESKIN_LAUNCHER"
require_hash "$WINE_ROOT/bin/wine64" "$EXPECTED_WINE64"
require_hash "$WINE_ROOT/bin/wineserver" "$EXPECTED_WINESERVER"
require_hash "$WINE_ROOT/lib/wine/x86_64-unix/ntdll.so" "$EXPECTED_NTDLL_UNIX"
require_hash "$WINE_ROOT/lib/wine/x86_64-windows/ntdll.dll" "$EXPECTED_NTDLL_WINDOWS"
require_hash "$GAME/dxil.dll" "$EXPECTED_ORIGINAL_DXIL"
[[ ! -e "$GAME/D3D12Core.dll" ]]
require_hash "$SYS/dxgi.dll" "$EXPECTED_DXGI"
require_hash "$SYS/d3d12.dll" "$EXPECTED_D3D12"
require_hash "$SYS/d3d12core.dll" "$EXPECTED_ENGINE_CORE"
require_file "$GAME/Pioneers of Pagonia.exe"
grep -a -q 'PROJECT:D3DMetal-4.0b3' \
  "$LIB/external/D3DMetal.framework/Versions/A/D3DMetal"
[[ "$(plutil -extract 'Program Name and Path' raw "$PLIST")" == '/Program Files (x86)/Steam/steam.exe' ]]
[[ "$(plutil -extract 'Program Flags' raw "$PLIST")" == '-applaunch 2155180' ]]
[[ "$(plutil -extract CFBundleIconFile raw "$PLIST")" == 'Pagonia.icns' ]]
require_file "$APP/Contents/Resources/Pagonia.icns"
[[ "$(plutil -extract D3DMETAL raw "$PLIST")" == '1' ]]
[[ "$(plutil -extract D3DMETAL_FORCE raw "$PLIST")" == '1' ]]
[[ "$(plutil -extract 'Debug Mode' raw "$PLIST")" == 'true' ]]
[[ "$(plutil -extract 'Symlinks In User Folder' raw "$PLIST")" == 'false' ]]
[[ "$(plutil -extract WINEESYNC raw "$PLIST")" == '0' ]]
[[ "$(plutil -extract WINEMSYNC raw "$PLIST")" == '0' ]]
[[ "$(plutil -extract WINEFSYNC raw "$PLIST")" == '0' ]]
[[ "$(plutil -extract 'LSEnvironment.D3DM_MTL4' raw "$PLIST")" == '1' ]]
for localconfig in "$STEAM"/userdata/*/config/localconfig.vdf; do
  [[ $(grep -c '"LaunchOptions".*"-NoDX12DeviceFactory -NoDX12SDKVersionCheck"' "$localconfig") -eq 1 ]]
done

cat >"$APP/Contents/SharedSupport/Pagonia-GPTK4b3-deployment.txt" <<EOF
Pioneers of Pagonia GPTK deployment
Created: $(date '+%d.%m.%Y %H:%M:%S %Z')
Game build: $EXPECTED_BUILD_ID
GPTK: Game Porting Toolkit 4.0 beta 3 / D3DMetal 4.0b3
Wine64 SHA-256: $EXPECTED_WINE64
Original dxil.dll SHA-256: $EXPECTED_ORIGINAL_DXIL
D3D12 SDK check: game-provided -NoDX12SDKVersionCheck (no binary patch)
Steam launch options: $LAUNCH_OPTIONS
Application behavior: launch Steam App 2155180 directly
EOF

touch "$APP"
if [[ $DEST_INITIAL_EXISTS -eq 0 && -e "$DESTINATION" ]]; then
  echo 'ERROR: Destination appeared during deployment; refusing to replace it.' >&2
  exit 1
fi
PUBLISHED_DEVICE=$(stat -f '%d' "$STAGING")
PUBLISHED_INODE=$(stat -f '%i' "$STAGING")
# Defer interactive signals across the two-rename publication transaction so
# cleanup always observes a complete, explicitly recorded state.
trap '' INT TERM
if [[ $DEST_INITIAL_EXISTS -eq 1 ]]; then
  if ! same_identity "$DESTINATION" "$DEST_INITIAL_DEVICE" "$DEST_INITIAL_INODE"; then
    trap on_signal INT TERM
    echo 'ERROR: Destination changed during deployment; refusing to publish.' >&2
    exit 1
  fi
  BACKUP=$(unique_sibling_path "$DESTINATION" backup)
  atomic_rename_exclusive "$DESTINATION" "$BACKUP"
  BACKUP_MOVED=1
fi
if ! atomic_rename_exclusive "$STAGING" "$DESTINATION"; then
  echo 'ERROR: Atomic publication failed; attempting to restore the previous deployment.' >&2
  if [[ $BACKUP_MOVED -eq 1 && -e "$BACKUP" && ! -e "$DESTINATION" ]]; then
    if atomic_rename_exclusive "$BACKUP" "$DESTINATION"; then
      BACKUP_MOVED=0
    else
      echo "ERROR: Restore failed; previous deployment remains at: $BACKUP" >&2
    fi
  fi
  trap on_signal INT TERM
  exit 1
fi
PUBLISHED=1
STAGING=''
rmdir "$WORK_ROOT"
WORK_ROOT=''
if ! same_identity "$DESTINATION" "$PUBLISHED_DEVICE" "$PUBLISHED_INODE"; then
  trap on_signal INT TERM
  echo 'ERROR: Published application identity changed during publication.' >&2
  exit 1
fi
BACKUP_MOVED=0
trap on_signal INT TERM
[[ -z "$BACKUP" ]] || echo "Previous deployment preserved pending launch verification: $BACKUP"
LSREGISTER='/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister'
if [[ -x "$LSREGISTER" ]]; then
  "$LSREGISTER" -f "$DESTINATION"
fi

echo
echo "Deployment installed: $DESTINATION"
echo 'The Pagonia application is registered for Applications and Launchpad.'
if [[ $LAUNCH_TEST -eq 0 ]]; then
  SUCCESS=1
  echo 'Launch test skipped. Open the application to start Pagonia directly.'
  exit 0
fi

LOG="$DESTINATION/Contents/SharedSupport/Logs/LastRunWine.log"
rm -f "$LOG"
same_identity "$DESTINATION" "$PUBLISHED_DEVICE" "$PUBLISHED_INODE" || {
  echo 'ERROR: Published application changed before launch.' >&2
  exit 1
}
"$OPEN_COMMAND" -n "$DESTINATION"
echo
echo 'Pioneers of Pagonia is starting through its new application icon.'
echo 'The installer is waiting up to fifteen minutes for the verified game launch.'
echo 'If Steam shows a Cloud conflict, choose the correct save explicitly.'

GAME_COMMAND=''
CLOUD_NOTICE_SHOWN=0
STEAM_CONSOLE="$DESTINATION/Contents/SharedSupport/prefix/drive_c/Program Files (x86)/Steam/logs/console_log.txt"
for _ in $(jot 450); do
  GAME_COMMAND=$(ps -U "$UID" -o command= \
    | grep '[P]ioneers of Pagonia.exe' | head -1 || true)
  [[ -n "$GAME_COMMAND" ]] && break
  if [[ $CLOUD_NOTICE_SHOWN -eq 0 && -f "$STEAM_CONSOLE" ]] \
     && tail -100 "$STEAM_CONSOLE" | grep -q 'SynchronizingCloud "syncfailed"'; then
    CLOUD_NOTICE_SHOWN=1
    echo
    echo 'ACTION REQUIRED: Steam is waiting for a Cloud conflict decision.'
    echo 'Bring the Windows Steam window forward and choose the correct save.'
    osascript -e 'tell application "System Events" to set frontmost of first process whose name is "wine64" to true' 2>/dev/null || true
  fi
  "$SLEEP_COMMAND" 2
done
if [[ -z "$GAME_COMMAND" ]]; then
  echo 'ERROR: Pioneers of Pagonia did not start within fifteen minutes.' >&2
  exit 1
fi
for option in -NoDX12DeviceFactory -NoDX12SDKVersionCheck; do
  [[ "$GAME_COMMAND" == *"$option"* ]] || {
    echo "ERROR: Running game is missing $option" >&2
    echo "$GAME_COMMAND" >&2
    exit 1
  }
done
for _ in $(jot 90); do
  if [[ -f "$LOG" ]] && grep -q 'Created D3D12Device' "$LOG" \
     && grep -q 'Created D3D12 Swapchain' "$LOG"; then
    echo
    echo 'End-to-end verification succeeded:'
    echo '  Steam Play supplied both game-supported bypasses.'
    echo '  Created D3D12Device'
    echo '  Created D3D12 Swapchain'
    echo 'Pioneers of Pagonia is installed and running.'
    SUCCESS=1
    exit 0
  fi
  "$SLEEP_COMMAND" 2
done

echo 'ERROR: Game started, but D3D12 device/swapchain creation was not logged.' >&2
exit 1
