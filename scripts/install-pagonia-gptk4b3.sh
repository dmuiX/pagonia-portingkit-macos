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
WINE_RUNNER=${PAGONIA_WINE_RUNNER:-}
TEST_MODE=${PAGONIA_TEST_MODE:-0}
STEAM_WINDOW_CHECKER=${PAGONIA_STEAM_WINDOW_CHECKER:-}

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd -P)
SOURCE_PREFIX=''
GPTK_LIB=''
ENGINE_ARCHIVE_NAME='WS12WineSikarugir10.0_2-20251028-pagonia.tar.xz'
DOWNLOADER_ARCHIVE_NAME='WineCX-11.17-SteamDownloader-4.7.3.tar.xz'
WRAPPER_ARCHIVE_NAME='Wineskin-3.0.6-2.app.tar.xz'
ENGINE_ARCHIVE="$SCRIPT_DIR/$ENGINE_ARCHIVE_NAME"
DOWNLOADER_ARCHIVE="$SCRIPT_DIR/$DOWNLOADER_ARCHIVE_NAME"
WRAPPER_ARCHIVE="$SCRIPT_DIR/$WRAPPER_ARCHIVE_NAME"
GAME_HASH_MANIFEST_NAME='pagonia-build-25784167-SHA256SUMS'
GAME_HASH_MANIFEST="$SCRIPT_DIR/$GAME_HASH_MANIFEST_NAME"
GPTK_HASH_MANIFEST="$SCRIPT_DIR/gptk-4.0b3-SHA256SUMS"
GPTK_LINK_MANIFEST="$SCRIPT_DIR/gptk-4.0b3-SYMLINKS"
STEAM_SESSION_HELPER="$SCRIPT_DIR/pagonia-steam-session.py"
STEAM_LOGIN_LOG_HELPER="$SCRIPT_DIR/check-steam-login-log.py"
STEAM_WINDOW_HELPER="$SCRIPT_DIR/check-steam-window-bmp.py"
BOUNDED_COMMAND_HELPER="$SCRIPT_DIR/run-bounded-command.py"
GPTK_LIB_EXPLICIT=0
GPTK_DOWNLOAD_URL='https://developer.apple.com/download/all/?q=Game%20Porting%20Toolkit'
GPTK_DEFAULT_LIB='/Volumes/Evaluation environment for Windows games 4.0 beta 3/redist/lib'
DESTINATION='/Applications/Pioneers of Pagonia.app'
STEAM_INSTALLER_URL='https://cdn.akamai.steamstatic.com/client/installer/SteamSetup.exe'
REPLACE=0
DELETE_MODE=0
RESUME_ROOT=''
DESTINATION_EXPLICIT=0
ASSUME_YES=0
LAUNCH_TEST=1
FORCE_FRESH=0
LOCK_DIR="/private/tmp/Pagonia-GPTK4b3-installer-${UID}.lock"
LOCK_HELD=0
LOCK_PARENT_PID=${PAGONIA_LOCK_PARENT_PID:-}
DOWNLOADER_SOURCE_PREFIX=''
RESUME_SOURCE_ROOT=''
RESUME_SOURCE_DEVICE=''
RESUME_SOURCE_INODE=''
WINE_CHILD_PID=''
STEAM_CAPTURE_PNG=''
STEAM_CAPTURE_BMP=''

EXPECTED_ENGINE_ARCHIVE='0598a60af56d67b1efd35ac0751cbcc34a30a0329e2788e182dd67a5698f9353'
EXPECTED_DOWNLOADER_ARCHIVE='064de70024679010b65b3619c0de9f2993b432dc511bb018a55fc3b31aefece9'
EXPECTED_GAME_HASH_MANIFEST='f1c7dafea25540477c6201e3224b742bafaac178b027456cb4bc19541794ff6d'
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
EXPECTED_DOWNLOADER_WINE='a680abba30b4888355adb39d8b62255e43546eb33d163897260627f7741ef648'
EXPECTED_DOWNLOADER_WINESERVER='f5be596e5c38a2ee77a4ccfc4acab028bef636f0afc340fe2f57dad29474eb15'
EXPECTED_DOWNLOADER_NTDLL_UNIX='7c7e226f62d840028916ed3d4a94ce49f62a18df27102a771271369473b26365'
EXPECTED_DOWNLOADER_NTDLL_WINDOWS='8b32c9f6f71b4f15fcaccb19b0f2adab9391ae73ad539cae9e136f8ee7d24128'
EXPECTED_DXVK_X64_D3D10CORE='0fa08bba860c63e3abeeabfc96d0e7aa327411a975f8f23d2dc63594ef5f796e'
EXPECTED_DXVK_X64_D3D11='0ff0b0835dde29556bd01dfce7b1ae348d7f229cb1e1a37cc71ea1a028beeca4'
EXPECTED_DXVK_X32_D3D10CORE='2277187a4e13fc2049fe28cb8dd05b34b48c68031c386c3597ba0e18b0c3d327'
EXPECTED_DXVK_X32_D3D11='f79d417f675d00008375eb4ea2318af6fcd0b27971d604d3cf345a0dcfa998a0'
EXPECTED_DOWNLOADER_NATIVE_DXGI='f72fe1c82373fe3e2f198df7affb527b0d2117392f5f46577e856efa97a8d024'
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
  --destination PATH    Install destination, or exact deletion target.
  --replace             Back up and replace an existing destination.
  --delete              List Pagonia paths and delete selected entries.
  --resume PATH         Resume an interrupted private staging deployment.
  --no-launch           Install without the final interactive Steam Play test.
  -y, --yes             Accept the deployment plan non-interactively.
  -h, --help            Show this help.

Default behavior:
  1. Verify the pinned Wine 11.17 downloader and Wine 10 gameplay runtimes.
  2. Verify the user-supplied GPTK 4.0b3 runtime.
  3. Reuse a prefix only when explicitly supplied as trusted input.
  4. Otherwise use a private Wine 11.17 prefix for one Steam login/download,
     stop it, and hash-validate the complete pinned game depot.
  5. Transfer an integrity-checked Steam login session into a separate Wine 10
     gameplay prefix, then selectively import only manifest-listed game files.
  6. Configure the two game-provided D3D12 bypasses and register the app.
  7. Launch Pagonia directly through its macOS application icon.
  8. Succeed only after D3D12 device and swapchain creation are logged.
EOF
}

while (($#)); do
  case "$1" in
    --source-prefix) SOURCE_PREFIX=${2:?Missing path}; shift ;;
    --fresh) FORCE_FRESH=1 ;;
    --gptk-lib) GPTK_LIB=${2:?Missing path}; GPTK_LIB_EXPLICIT=1; shift ;;
    --destination) DESTINATION=${2:?Missing path}; DESTINATION_EXPLICIT=1; shift ;;
    --replace) REPLACE=1 ;;
    --delete) DELETE_MODE=1 ;;
    --resume) RESUME_ROOT=${2:?Missing path}; shift ;;
    --no-launch) LAUNCH_TEST=0 ;;
    -y|--yes) ASSUME_YES=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

if [[ -n "$RESUME_ROOT" && -n "$SOURCE_PREFIX" ]]; then
  echo 'ERROR: --resume and --source-prefix are mutually exclusive.' >&2
  exit 2
fi
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
DOWNLOADER_APP=''
SEED_PREFIX=''
SEED_WINE=''
STEAM_SESSION_SNAPSHOT=''
STEAM_SESSION_ID=''

sha256() { shasum -a 256 "$1" | awk '{print $1}'; }

CUSTOM_TOOL_OVERRIDE=0
[[ "$OPEN_COMMAND" == '/usr/bin/open' ]] || CUSTOM_TOOL_OVERRIDE=1
[[ "$PGREP_COMMAND" == '/usr/bin/pgrep' ]] || CUSTOM_TOOL_OVERRIDE=1
[[ "$SLEEP_COMMAND" == '/bin/sleep' ]] || CUSTOM_TOOL_OVERRIDE=1
[[ -z "$WINE_RUNNER" && -z "$STEAM_WINDOW_CHECKER" ]] || CUSTOM_TOOL_OVERRIDE=1
if [[ $CUSTOM_TOOL_OVERRIDE -eq 1 ]]; then
  [[ "$TEST_MODE" == '1' ]] || {
    echo 'ERROR: PAGONIA command overrides require explicit PAGONIA_TEST_MODE=1.' >&2
    exit 2
  }
  python3 - "$OPEN_COMMAND" "$PGREP_COMMAND" "$SLEEP_COMMAND" \
    "$WINE_RUNNER" "$STEAM_WINDOW_CHECKER" <<'PY'
from pathlib import Path
import os
import stat
import sys

system_tools = {Path('/usr/bin/open'), Path('/usr/bin/pgrep'), Path('/bin/sleep')}
for candidate in filter(None, sys.argv[1:]):
    executable = Path(candidate).resolve(strict=True)
    if executable in system_tools:
        continue
    for path in (executable.parent, executable):
        info = path.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise SystemExit(f'Unsafe test executable owner or mode: {path}')
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise SystemExit(f'Invalid test executable: {executable}')
PY
fi

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

copy_verified_file() {
  local source=$1 destination=$2 expected=$3
  python3 - "$source" "$destination" "$expected" <<'PY'
from hashlib import sha256
import os
from pathlib import Path
import stat
import sys

source, destination = map(Path, sys.argv[1:3])
expected = sys.argv[3]
source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
try:
    info = os.fstat(source_fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
        raise SystemExit(f'Untrusted verified-copy source: {source}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    output_fd = os.open(
        destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    digest = sha256()
    try:
        with os.fdopen(source_fd, 'rb', closefd=False) as input_file, \
             os.fdopen(output_fd, 'wb') as output_file:
            while True:
                chunk = input_file.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                output_file.write(chunk)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
finally:
    os.close(source_fd)
if digest.hexdigest() != expected:
    destination.unlink(missing_ok=True)
    raise SystemExit(f'Verified-copy hash mismatch: {source}')
PY
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
  local path=${1%/}
  [[ -d "$path/external" && ! -L "$path/external" \
     && -d "$path/wine" && ! -L "$path/wine" \
     && -f "$path/wine/x86_64-windows/dxgi.dll" \
     && -f "$path/wine/x86_64-windows/d3d12.dll" \
     && "$(sha256 "$path/wine/x86_64-windows/dxgi.dll")" == "$EXPECTED_DXGI" \
     && "$(sha256 "$path/wine/x86_64-windows/d3d12.dll")" == "$EXPECTED_D3D12" ]]
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

release_installer_lock() {
  if [[ $LOCK_HELD -eq 1 && -d "$LOCK_DIR" && ! -L "$LOCK_DIR" \
        && "$(stat -f '%u' "$LOCK_DIR")" == "$UID" \
        && "$(cat "$LOCK_DIR/pid" 2>/dev/null || true)" == "$$" ]]; then
    rm -f "$LOCK_DIR/pid"
    rmdir "$LOCK_DIR" 2>/dev/null || true
  fi
  LOCK_HELD=0
}

acquire_installer_lock() {
  local owner=''
  if ! mkdir -m 700 "$LOCK_DIR" 2>/dev/null; then
    [[ -d "$LOCK_DIR" && ! -L "$LOCK_DIR" \
       && "$(stat -f '%u' "$LOCK_DIR")" == "$UID" ]] || {
      echo 'ERROR: Untrusted installer lock exists; refusing to continue.' >&2
      return 1
    }
    owner=$(cat "$LOCK_DIR/pid" 2>/dev/null || true)
    if [[ -z "$owner" ]]; then
      # Never reclaim an empty lock: its creator may be between the atomic
      # mkdir and PID write. Conservative refusal preserves exclusivity. An
      # empty lock left by a killed creator must be removed manually after
      # confirming that no installer process exists.
      echo 'ERROR: Installer lock is being initialized or is stale; refusing to race it.' >&2
      echo "Inspect and, if safe, remove: $LOCK_DIR" >&2
      return 1
    fi
    if [[ -n "$owner" && "$owner" == "$LOCK_PARENT_PID" && "$PPID" == "$owner" \
          && "$owner" =~ ^[0-9]+$ && -O "$LOCK_DIR/pid" ]]; then
      printf '%s\n' "$$" >"$LOCK_DIR/pid"
      LOCK_HELD=1
      return 0
    fi
    if [[ -n "$owner" && "$owner" =~ ^[0-9]+$ ]] && kill -0 "$owner" 2>/dev/null \
       && ps -p "$owner" -o command= \
          | grep -Fq 'install-pagonia-gptk4b3.sh'; then
      echo "ERROR: Pagonia installer process $owner is already running." >&2
      return 1
    fi
    if [[ -n "$owner" ]]; then
      # Safe stale-lock reclamation needs a compare-and-swap operation that a
      # portable shell cannot provide. Refuse instead of risking a race that
      # removes a newly acquired lock from another installer.
      echo "ERROR: Stale installer lock for process $owner; refusing automatic reclamation." >&2
      echo "Inspect and, if safe, remove: $LOCK_DIR" >&2
      return 1
    fi
  fi
  printf '%s\n' "$$" >"$LOCK_DIR/pid"
  LOCK_HELD=1
}

cleanup() {
  local status=$?
  [[ -z "$STEAM_CAPTURE_PNG" ]] || rm -f "$STEAM_CAPTURE_PNG"
  [[ -z "$STEAM_CAPTURE_BMP" ]] || rm -f "$STEAM_CAPTURE_BMP"
  STEAM_CAPTURE_PNG=''
  STEAM_CAPTURE_BMP=''
  terminate_wine_child 2>/dev/null || true
  if [[ $PUBLISHED -eq 1 && $SUCCESS -ne 1 ]]; then
    local deployed_prefix failed
    if same_identity "$DESTINATION" "$PUBLISHED_DEVICE" "$PUBLISHED_INODE"; then
      deployed_prefix="$DESTINATION/Contents/SharedSupport/prefix"
      if [[ -z "$WINE_RUNNER" \
            && -x "$DESTINATION/Contents/SharedSupport/wine/bin/wineserver" ]]; then
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
          && "$WORK_ROOT" == /private/tmp/Pagonia-GPTK4b3-deployment.* \
          && "$(stat -f '%u' "$WORK_ROOT")" == "$UID" ]]; then
      if [[ $status -eq 0 && $SUCCESS -eq 1 ]]; then
        rm -rf "$WORK_ROOT"
      else
        if [[ -z "$WINE_RUNNER" && -n "$STAGING" \
              && -x "$STAGING/Contents/SharedSupport/wine/bin/wineserver" ]]; then
          WINEPREFIX="$STAGING/Contents/SharedSupport/prefix" \
            "$STAGING/Contents/SharedSupport/wine/bin/wineserver" -k \
            2>/dev/null || true
          WINEPREFIX="$STAGING/Contents/SharedSupport/prefix" \
            "$STAGING/Contents/SharedSupport/wine/bin/wineserver" -w \
            2>/dev/null || true
        fi
        if [[ -z "$WINE_RUNNER" && -n "$DOWNLOADER_APP" \
              && -x "$DOWNLOADER_APP/Contents/SharedSupport/wine/bin/wineserver" ]]; then
          WINEPREFIX="$DOWNLOADER_APP/Contents/SharedSupport/prefix" \
            "$DOWNLOADER_APP/Contents/SharedSupport/wine/bin/wineserver" -k \
            2>/dev/null || true
          WINEPREFIX="$DOWNLOADER_APP/Contents/SharedSupport/prefix" \
            "$DOWNLOADER_APP/Contents/SharedSupport/wine/bin/wineserver" -w \
            2>/dev/null || true
        fi
        if [[ -n "$SEED_PREFIX" && -n "$SEED_WINE" \
              && -x "$SEED_WINE/bin/wineserver" ]]; then
          WINEPREFIX="$SEED_PREFIX" "$SEED_WINE/bin/wineserver" -k \
            2>/dev/null || true
          WINEPREFIX="$SEED_PREFIX" "$SEED_WINE/bin/wineserver" -w \
            2>/dev/null || true
        fi
        if [[ -n "$RESUME_SOURCE_ROOT" && "$RESUME_SOURCE_ROOT" != "$WORK_ROOT" ]]; then
          /bin/rm -x -rf "$WORK_ROOT"
          echo "Failed gameplay staging removed; downloader remains resumable: $RESUME_SOURCE_ROOT" >&2
          WORK_ROOT=''
          STAGING=''
        fi
        if [[ -n "$WORK_ROOT" ]]; then
          echo "Incomplete deployment preserved for resume: $WORK_ROOT" >&2
          if [[ -n "$DOWNLOADER_APP" ]]; then
            echo "Its resumable downloader prefix is: $DOWNLOADER_APP/Contents/SharedSupport/prefix" >&2
          fi
        fi
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
  if [[ $status -eq 0 && $SUCCESS -eq 1 && -n "$RESUME_SOURCE_ROOT" ]]; then
    if same_identity "$RESUME_SOURCE_ROOT" "$RESUME_SOURCE_DEVICE" "$RESUME_SOURCE_INODE"; then
      /bin/rm -x -rf "$RESUME_SOURCE_ROOT"
      echo "Removed completed downloader staging: $RESUME_SOURCE_ROOT"
    else
      echo 'WARNING: Resumed downloader changed and was left untouched.' >&2
    fi
  fi
  release_installer_lock
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
acquire_installer_lock
if [[ $DELETE_MODE -eq 0 ]]; then
  DESTINATION=$(validate_destination "$DESTINATION")
  DESTINATION_PARENT=$(dirname "$DESTINATION")
  if [[ "$(stat -f '%d' /tmp)" != "$(stat -f '%d' "$DESTINATION_PARENT")" ]]; then
    echo 'ERROR: Destination must be on the same filesystem as /tmp for atomic publication.' >&2
    exit 1
  fi
fi

stop_if_running() {
  if "$PGREP_COMMAND" -u "$UID" \
      -f '[Ss]team\.exe|steamwebhelper\.exe|steamservice\.exe|Pioneers of Pagonia\.exe|winedbg' \
      >/dev/null; then
    echo 'ERROR: Windows Steam or Pioneers of Pagonia is running. Exit it first.' >&2
    ps -U "$UID" -o pid=,command= \
      | grep -E '[Ss]team\.exe|[s]teamwebhelper\.exe|[s]teamservice\.exe|[P]ioneers of Pagonia\.exe|[w]inedbg' >&2 || true
    exit 1
  fi
}

steam_processes_running() {
  "$PGREP_COMMAND" -u "$UID" \
    -f '[Ss]team\.exe|steamwebhelper\.exe|steamservice\.exe|winedbg --auto' >/dev/null
}

steam_processes_belong_to_prefix() {
  local prefix=$1
  if [[ -n "$WINE_RUNNER" ]]; then
    steam_processes_running
    return
  fi
  python3 - "$prefix" <<'PY'
from pathlib import Path
import os
import re
import subprocess
import sys

prefix = Path(sys.argv[1]).resolve(strict=True)
processes = subprocess.check_output(
    ['ps', '-U', str(os.getuid()), '-o', 'pid=,command='], text=True)
pids = []
pattern = re.compile(r'(?:^|[\\/])[Ss]team\.exe|steamwebhelper\.exe|steamservice\.exe')
for line in processes.splitlines():
    fields = line.strip().split(None, 1)
    if len(fields) == 2 and pattern.search(fields[1]):
        pids.append(int(fields[0]))
if not pids:
    raise SystemExit(1)
for pid in pids:
    try:
        output = subprocess.check_output(
            ['lsof', '-a', '-p', str(pid), '-d', 'cwd', '-Fn'],
            text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        raise SystemExit(1)
    current = next((line[1:] for line in output.splitlines() if line.startswith('n')), '')
    try:
        Path(current).resolve(strict=True).relative_to(prefix)
    except (ValueError, FileNotFoundError):
        raise SystemExit(1)
PY
}

terminate_staging_processes_without_runtime() {
  local root=$1 prefix=$2
  python3 - "$root" "$prefix" <<'PY'
from pathlib import Path
import os
import signal
import subprocess
import sys
import time

root = Path(sys.argv[1]).resolve(strict=True)
prefix = Path(sys.argv[2]).resolve(strict=True)
self_pid = os.getpid()
protected = {self_pid, os.getppid()}


def targets():
    output = subprocess.check_output(
        ['ps', '-U', str(os.getuid()), '-o', 'pid=,command='], text=True)
    result = []
    for line in output.splitlines():
        fields = line.strip().split(None, 1)
        if len(fields) != 2:
            continue
        pid, command = int(fields[0]), fields[1]
        if pid in protected:
            continue
        runtime_process = str(root) in command and any(
            token in command for token in ('/wineserver', '/wine64', '/wine '))
        windows_process = command.startswith('C:\\')
        if not runtime_process and not windows_process:
            continue
        if windows_process:
            try:
                cwd_output = subprocess.check_output(
                    ['lsof', '-a', '-p', str(pid), '-d', 'cwd', '-Fn'],
                    text=True, stderr=subprocess.DEVNULL)
                cwd = next(
                    line[1:] for line in cwd_output.splitlines() if line.startswith('n'))
                Path(cwd).resolve(strict=True).relative_to(prefix)
            except (subprocess.CalledProcessError, StopIteration, ValueError,
                    FileNotFoundError):
                continue
        result.append(pid)
    return result

for pid in targets():
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
for _ in range(30):
    if not targets():
        raise SystemExit(0)
    time.sleep(0.1)
for pid in targets():
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
if targets():
    raise SystemExit('Could not terminate processes from mutable resume runtime')
PY
}

stop_wineskin_app_processes() {
  local app=$1
  python3 - "$app" <<'PY'
from pathlib import Path
import os
import signal
import subprocess
import sys
import time

app = Path(sys.argv[1]).resolve()
executables = (
    str(app / 'Contents/MacOS/wineskinlauncher'),
    str(app / 'Contents/Wineskin.app/Contents/MacOS/Wineskin'),
)

def matching_pids():
    output = subprocess.check_output(
        ['ps', '-U', str(os.getuid()), '-o', 'pid=,command='], text=True)
    result = []
    for line in output.splitlines():
        fields = line.strip().split(None, 1)
        if len(fields) != 2:
            continue
        pid, command = int(fields[0]), fields[1]
        if any(command == executable or command.startswith(executable + ' ')
               for executable in executables):
            result.append(pid)
    return result

for pid in matching_pids():
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
for _ in range(20):
    if not matching_pids():
        raise SystemExit(0)
    time.sleep(0.1)
for pid in matching_pids():
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
if matching_pids():
    raise SystemExit('Wineskin wrapper process did not stop')
PY
}

launch_wine_program() {
  local prefix=$1 wine_root=$2 log=$3 program=$4 app dxvk_root
  local -a wine_environment
  shift 4
  app=${wine_root%/Contents/SharedSupport/wine}
  dxvk_root="${wine_root%/wine}/dxvk"
  wine_environment=(
    "WINEPREFIX=$prefix" "WINEDEBUG=fixme-all" 'WINEESYNC=0' 'WINEMSYNC=0'
    'LANG=en_US.UTF-8' 'LC_ALL=en_US.UTF-8' 'LC_TIME=C' 'LC_NUMERIC=C'
    'CEF_DISABLE_SANDBOX=1' 'STEAM_DISABLE_CEF_SANDBOX=1' 'STEAM_RUNTIME=0'
    'WINHTTP_CONNECT_TIMEOUT=90000' 'WINHTTP_RECEIVE_TIMEOUT=180000'
  )
  if [[ -d "$dxvk_root" ]]; then
    wine_environment+=(
      'DXVK_ASYNC=1' 'WINEDLLOVERRIDES=dxgi,d3d10core,d3d11=n,b'
      "DYLD_FALLBACK_LIBRARY_PATH=$app/Contents/Frameworks:$wine_root/lib"
    )
  fi
  if [[ -n "$WINE_RUNNER" ]]; then
    "$WINE_RUNNER" "$prefix" "$wine_root" "$log" "$program" "$@"
    WINE_CHILD_PID=''
  else
    env "${wine_environment[@]}" \
      "$wine_root/bin/wine64" "$program" "$@" >>"$log" 2>&1 &
    WINE_CHILD_PID=$!
  fi
}

run_wine_program_bounded() {
  local prefix=$1 wine_root=$2 log=$3 timeout_seconds=$4 program=$5 app dxvk_root
  local -a wine_environment
  shift 5
  app=${wine_root%/Contents/SharedSupport/wine}
  dxvk_root="${wine_root%/wine}/dxvk"
  wine_environment=(
    "WINEPREFIX=$prefix" "WINEDEBUG=fixme-all" 'WINEESYNC=0' 'WINEMSYNC=0'
    'LANG=en_US.UTF-8' 'LC_ALL=en_US.UTF-8' 'LC_TIME=C' 'LC_NUMERIC=C'
    'CEF_DISABLE_SANDBOX=1' 'STEAM_DISABLE_CEF_SANDBOX=1' 'STEAM_RUNTIME=0'
    'WINHTTP_CONNECT_TIMEOUT=90000' 'WINHTTP_RECEIVE_TIMEOUT=180000'
  )
  if [[ -d "$dxvk_root" ]]; then
    wine_environment+=(
      'DXVK_ASYNC=1' 'WINEDLLOVERRIDES=dxgi,d3d10core,d3d11=n,b'
      "DYLD_FALLBACK_LIBRARY_PATH=$app/Contents/Frameworks:$wine_root/lib"
    )
  fi
  if [[ -n "$WINE_RUNNER" ]]; then
    "$WINE_RUNNER" "$prefix" "$wine_root" "$log" "$program" "$@"
    return
  fi
  env "${wine_environment[@]}" python3 "$BOUNDED_COMMAND_HELPER" \
    "$timeout_seconds" 2 "$log" "$wine_root/bin/wine64" "$program" "$@"
}

terminate_wine_child() {
  local check
  if [[ "$WINE_CHILD_PID" =~ ^[0-9]+$ ]] && kill -0 "$WINE_CHILD_PID" 2>/dev/null; then
    kill -TERM "$WINE_CHILD_PID" 2>/dev/null || true
    for ((check = 1; check <= 20; check++)); do
      kill -0 "$WINE_CHILD_PID" 2>/dev/null || break
      /bin/sleep 0.1
    done
    kill -KILL "$WINE_CHILD_PID" 2>/dev/null || true
  fi
  if [[ "$WINE_CHILD_PID" =~ ^[0-9]+$ ]]; then
    wait "$WINE_CHILD_PID" 2>/dev/null || true
  fi
  WINE_CHILD_PID=''
}

remove_stale_wineskin_lock() {
  local app=$1
  python3 - "$app" <<'PY'
from pathlib import Path
import os
import stat
import subprocess
import sys

app = Path(sys.argv[1]).resolve()
executables = (
    str(app / 'Contents/MacOS/wineskinlauncher'),
    str(app / 'Contents/Wineskin.app/Contents/MacOS/Wineskin'),
)
output = subprocess.check_output(
    ['ps', '-U', str(os.getuid()), '-o', 'command='], text=True)
if any(any(command.strip() == executable or command.strip().startswith(executable + ' ')
           for executable in executables) for command in output.splitlines()):
    raise SystemExit(f'Refusing to remove lock for active Wineskin app: {app}')
lock_dir = Path('/private/tmp') / str(app).replace('/', 'xWSx')
try:
    info = lock_dir.lstat()
except FileNotFoundError:
    raise SystemExit(0)
if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid():
    raise SystemExit(f'Refusing unsafe Wineskin lock directory: {lock_dir}')
entries = list(lock_dir.iterdir())
if len(entries) != 1 or entries[0].name != 'lockfile':
    raise SystemExit(f'Refusing unexpected Wineskin lock contents: {lock_dir}')
lock_info = entries[0].lstat()
if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_uid != os.getuid():
    raise SystemExit(f'Refusing unsafe Wineskin lock file: {entries[0]}')
entries[0].unlink()
lock_dir.rmdir()
PY
}

stop_wine_prefix() {
  local prefix=$1 wine_root=$2 app check
  app=${prefix%/Contents/SharedSupport/prefix}
  # wineserver returns non-zero when this prefix already has no server. That is
  # already the desired state, so process disappearance—not -k's status—is the
  # shutdown result that matters.
  if [[ -z "$WINE_RUNNER" ]]; then
    WINEPREFIX="$prefix" "$wine_root/bin/wineserver" -k 2>/dev/null || true
    terminate_wine_child
    WINEPREFIX="$prefix" "$wine_root/bin/wineserver" -w 2>/dev/null || true
    stop_wineskin_app_processes "$app" || return 1
  else
    terminate_wine_child
    "$WINE_RUNNER" "$prefix" "$wine_root" /dev/null \
      "$wine_root/bin/wineserver" -k
  fi
  for ((check = 1; check <= 20; check++)); do
    if ! steam_processes_running; then
      echo "  Wine prefix shutdown confirmed: $prefix"
      return 0
    fi
    "$SLEEP_COMMAND" 1 || return 1
  done
  echo 'ERROR: Steam processes remain after wineserver shutdown.' >&2
  return 1
}

remove_steam_cef_cache() {
  local prefix=$1
  python3 - "$prefix/drive_c/users" <<'PY'
from pathlib import Path
import shutil
import sys

users = Path(sys.argv[1]).resolve(strict=True)
for profile in users.iterdir():
    cache = profile / 'AppData/Local/Steam/htmlcache'
    if not cache.exists():
        continue
    current = users
    for part in cache.relative_to(users).parts:
        current /= part
        if current.is_symlink():
            raise SystemExit(f'Refusing linked Steam cache path: {current}')
    resolved = cache.resolve(strict=True)
    if users not in resolved.parents:
        raise SystemExit(f'Steam cache escapes prefix: {cache}')
    shutil.rmtree(resolved)
PY
}

require_screen_recording_permission() {
  [[ "$TEST_MODE" == '1' ]] && return 0
  if ! /usr/bin/swift -e \
      'import CoreGraphics; import Darwin; exit(CGPreflightScreenCaptureAccess() ? 0 : 1)' \
      >/dev/null 2>&1; then
    echo 'ERROR: Steam window verification requires Screen Recording permission.' >&2
    echo 'Grant permission to your terminal in System Settings > Privacy & Security > Screen Recording, then rerun the installer.' >&2
    return 1
  fi
}

steam_login_window_has_pixels() {
  local window_ids window_id status=1
  if [[ -n "$WINE_RUNNER" ]]; then
    [[ -z "$STEAM_WINDOW_CHECKER" ]] || "$STEAM_WINDOW_CHECKER"
    return
  fi
  window_ids=$(/usr/bin/swift -e '
import CoreGraphics
let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as! [[String: Any]]
for window in windows {
    let owner = window[kCGWindowOwnerName as String] as? String ?? ""
    let name = window[kCGWindowName as String] as? String ?? ""
    if owner == "wine" && (name == "Sign in to Steam" || name == "Steam") {
        print(window[kCGWindowNumber as String]!)
    }
}' 2>/dev/null)
  [[ -n "$window_ids" ]] || return 2
  for window_id in $window_ids; do
    [[ "$window_id" =~ ^[0-9]+$ ]] || continue
    STEAM_CAPTURE_PNG=$(mktemp '/tmp/PagoniaSteamWindow.XXXXXX.png')
    STEAM_CAPTURE_BMP=$(mktemp '/tmp/PagoniaSteamWindow.XXXXXX.bmp')
    chmod 600 "$STEAM_CAPTURE_PNG" "$STEAM_CAPTURE_BMP"
    if /usr/sbin/screencapture -x -l "$window_id" "$STEAM_CAPTURE_PNG" 2>/dev/null \
       && /usr/bin/sips -s format bmp "$STEAM_CAPTURE_PNG" \
          --out "$STEAM_CAPTURE_BMP" >/dev/null 2>&1 \
       && python3 "$STEAM_WINDOW_HELPER" "$STEAM_CAPTURE_BMP"
    then
      status=0
    fi
    rm -f "$STEAM_CAPTURE_PNG" "$STEAM_CAPTURE_BMP"
    STEAM_CAPTURE_PNG=''
    STEAM_CAPTURE_BMP=''
    [[ $status -eq 0 ]] && break
  done
  return "$status"
}

steam_ui_is_ready() {
  local log=$1
  awk '
    /PopupHTMLWindow:/ {
      popup=$0
      sub(/^.*idx:/, "", popup)
      sub(/ .*/, "", popup)
      expected[popup]=1
    }
    /BrowserReady: handle:/ {
      ready=$0
      sub(/^.*BrowserReady: handle:/, "", ready)
      sub(/[^0-9].*$/, "", ready)
      if (expected[ready]) found=1
    }
    END { exit !found }
  ' "$log"
}

wait_for_steam_ui() {
  local steam_ui_log=$1 wine_log=$2 check window_status
  for check in $(jot 90); do
    if [[ -f "$steam_ui_log" ]] \
       && grep -q 'Timed out waiting for webhelper init' "$steam_ui_log"; then
      echo '  Steam reported a webhelper initialization timeout.' >&2
      return 1
    fi
    if [[ -f "$wine_log" ]] \
       && grep -q 'Couldn.t get first exception.*steamwebhelper' "$wine_log"; then
      echo '  Wine reported a steamwebhelper exception.' >&2
      return 1
    fi
    if [[ -f "$steam_ui_log" ]] && steam_ui_is_ready "$steam_ui_log" \
       && "$PGREP_COMMAND" -u "$UID" -f 'steamwebhelper\.exe' >/dev/null; then
      if steam_login_window_has_pixels; then
        echo '  Steam UI is visibly rendered.'
        return 0
      else
        window_status=$?
      fi
      if ((check % 10 == 0)); then
        if [[ $window_status -eq 1 ]]; then
          echo "  Steam window capture is still black after $((check * 2)) seconds." >&2
        else
          echo "  Waiting for an on-screen Steam window ($((check * 2)) seconds)." >&2
        fi
      fi
    fi
    "$SLEEP_COMMAND" 2 || return 1
  done
  echo '  Steam did not create a usable login window within three minutes.' >&2
  return 1
}

install_steam_service() {
  local app=$1 prefix=$2 wine_root=$3 service log
  service="$prefix/drive_c/Program Files (x86)/Common Files/Steam/steamservice.exe"
  log="$app/Contents/SharedSupport/Logs/SteamServiceInstall.log"
  require_file "$service"
  echo '  Installing the Steam Client Service inside the private Wine prefix...'
  if ! run_wine_program_bounded "$prefix" "$wine_root" "$log" 60 \
      "$service" /Install; then
    echo 'ERROR: Steam Client Service installation did not complete cleanly.' >&2
    return 1
  fi
  echo '  Steam Client Service installation completed.'
}

wait_for_steam_authentication() {
  local steam=$1 check
  local login_log="$steam/logs/steamui_login.txt"
  echo 'ACTION REQUIRED: Sign in and complete Steam Guard or QR confirmation.'
  for check in $(jot 900); do
    if [[ -f "$steam/config/loginusers.vdf" && ! -L "$steam/config/loginusers.vdf" \
          && -f "$login_log" && ! -L "$login_log" ]] \
       && grep -q 'Received logon success response' "$login_log" \
       && grep -q 'SetLoginState: Success - OK' "$login_log"; then
      echo '  Steam sign-in completed.'
      return 0
    fi
    ((check % 15 != 0)) || echo "  Waiting for Steam sign-in ($((check * 2)) seconds)..."
    "$SLEEP_COMMAND" 2 || return 1
  done
  echo 'ERROR: Steam sign-in did not complete within 30 minutes.' >&2
  return 1
}

request_pagonia_install() {
  local app=$1 prefix=$2 wine_root=$3 steam=$4 log
  log="$app/Contents/SharedSupport/Logs/SteamInstallRequest.log"
  echo '  Opening the Pioneers of Pagonia installation dialog in Steam...'
  if ! run_wine_program_bounded "$prefix" "$wine_root" "$log" 30 \
      "$steam/steam.exe" 'steam://install/2155180'; then
    echo 'ERROR: Steam did not accept the Pagonia installation request.' >&2
    return 1
  fi
  echo 'ACTION REQUIRED: Confirm the preselected Steam installation dialog once.'
}

launch_steam_ui() {
  local app=$1 prefix=$2 wine_root=$3 steam=$4
  require_screen_recording_permission || return 1
  local logs="$steam/logs" steam_ui_log="$steam/logs/steamui_html.txt"
  local login_log="$steam/logs/steamui_login.txt"
  local wine_log="$app/Contents/SharedSupport/Logs/LastRunWine.log"
  local attempt
  mkdir -p "$logs" || return 1
  for attempt in 1 2; do
    rm -f "$steam_ui_log" "$login_log" "$wine_log" || return 1
    echo "  Starting Steam UI directly with Wine (attempt $attempt/2)..."
    echo '  Steam may need a while to create its first window after a client update; the installer is still monitoring it.'
    launch_wine_program "$prefix" "$wine_root" "$wine_log" \
      "$steam/steam.exe" -no-cef-sandbox -vgui
    if wait_for_steam_ui "$steam_ui_log" "$wine_log"; then
      return 0
    fi
    stop_wine_prefix "$prefix" "$wine_root" || return 1
    [[ $attempt -eq 1 ]] || break
    echo "  Clearing this prefix's CEF cache before one controlled retry..."
    remove_steam_cef_cache "$prefix" || return 1
  done
  echo 'ERROR: Steam UI failed twice; aborting instead of waiting for a nonexistent game download.' >&2
  return 1
}

install_steam_in_prefix() {
  local app=$1 prefix=$2 wine_root=$3 steam=$4 plist=$5 setup_source=$6
  local setup="$prefix/drive_c/SteamSetup.exe" attempt setup_finished=0
  mkdir -p "$prefix/drive_c"
  if [[ "$setup_source" != "$setup" ]]; then
    copy_verified_file "$setup_source" "$setup" "$EXPECTED_STEAM_SETUP"
  else
    require_hash "$setup" "$EXPECTED_STEAM_SETUP"
  fi
  plutil -replace 'Program Name and Path' -string '/SteamSetup.exe' "$plist"
  plutil -replace 'Program Flags' -string '/S' "$plist"
  rm -f "$app/Contents/SharedSupport/Logs/LastRunWine.log"
  launch_wine_program "$prefix" "$wine_root" \
    "$app/Contents/SharedSupport/Logs/LastRunWine.log" "$setup" /S
  for attempt in $(jot 150); do
    if [[ -f "$steam/steam.exe" && -f "$steam/uninstall.exe" ]] \
       && ! "$PGREP_COMMAND" -u "$UID" -f 'SteamSetup\.exe' >/dev/null; then
      setup_finished=1
      break
    fi
    ((attempt % 15 != 0)) || echo "  Still waiting for SteamSetup (${attempt}/150 checks)..."
    "$SLEEP_COMMAND" 2
  done
  if [[ $setup_finished -ne 1 ]]; then
    echo "ERROR: SteamSetup did not complete in the private prefix: $prefix" >&2
    stop_wine_prefix "$prefix" "$wine_root" || true
    return 1
  fi
  stop_wine_prefix "$prefix" "$wine_root" || return 1
  rm -f "$setup"
  install_steam_service "$app" "$prefix" "$wine_root" || return 1
  stop_wine_prefix "$prefix" "$wine_root" || return 1
  plutil -replace 'Program Name and Path' -string '/Program Files (x86)/Steam/steam.exe' "$plist"
  plutil -replace 'Program Flags' -string '-no-cef-sandbox -vgui' "$plist"
}

steam_package_inventory_is_complete() {
  local source=$1
  python3 - "$source" <<'PY'
from pathlib import Path, PureWindowsPath
import re
import stat
import sys
import zlib

source = Path(sys.argv[1]).resolve(strict=True)
manifest = source / 'package/steam_client_win64.installed'
if not manifest.is_file() or manifest.is_symlink():
    raise SystemExit(1)
for raw in manifest.read_text(errors='strict').splitlines():
    if re.fullmatch(r'(?:OSVER|VERSION)=\d+|SHA1=[0-9A-F]{40}', raw):
        continue
    try:
        windows_name, metadata = raw.rsplit(',', 1)
        size_text, _, crc_text = metadata.split(';')
        size = int(size_text)
        crc = int(crc_text)
    except (ValueError, UnicodeError):
        raise SystemExit(1)
    if size < 0:
        continue
    windows_path = PureWindowsPath(windows_name)
    if windows_path.is_absolute() or '..' in windows_path.parts:
        raise SystemExit(1)
    path = source / Path(*windows_path.parts)
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_size != size:
            raise SystemExit(1)
        if zlib.crc32(path.read_bytes()) != crc:
            raise SystemExit(1)
    except OSError:
        raise SystemExit(1)
PY
}

create_clean_steam_snapshot() {
  local source=$1 snapshot=$2
  python3 - "$source" "$snapshot" <<'PY'
from hashlib import sha256
from pathlib import Path, PureWindowsPath
import os
import re
import shutil
import stat
import sys
import zlib

source = Path(sys.argv[1]).resolve(strict=True)
snapshot = Path(sys.argv[2])
if snapshot.exists():
    raise SystemExit(f'Steam snapshot destination already exists: {snapshot}')
package = source / 'package'
# The current client is 64-bit. Its installed-file inventory is authoritative
# and includes all x86 compatibility files that Valve ships with that client.
# Do not merge the win32 inventory: hundreds of duplicate paths intentionally
# differ, and the files on disk match the win64 package.
manifests = [package / 'steam_client_win64.installed']
files = {}
for manifest in manifests:
    if not manifest.is_file() or manifest.is_symlink():
        raise SystemExit(f'Missing Steam installed-file manifest: {manifest}')
    for number, raw in enumerate(manifest.read_text(errors='strict').splitlines(), 1):
        if re.fullmatch(r'(?:OSVER|VERSION)=\d+|SHA1=[0-9A-F]{40}', raw):
            continue
        try:
            windows_name, metadata = raw.rsplit(',', 1)
            size_text, _, crc_text = metadata.split(';')
            size = int(size_text)
            crc = int(crc_text)
        except (ValueError, UnicodeError):
            raise SystemExit(f'Invalid Steam package manifest line {manifest}:{number}')
        if size < 0:
            continue
        windows_path = PureWindowsPath(windows_name)
        if windows_path.is_absolute() or '..' in windows_path.parts:
            raise SystemExit(f'Unsafe Steam package path: {windows_name}')
        relative = Path(*windows_path.parts)
        if not relative.parts or any('\n' in part or '\r' in part for part in relative.parts):
            raise SystemExit(f'Unsafe Steam package path: {windows_name}')
        lowered = {part.lower() for part in relative.parts}
        if lowered & {'appcache', 'config', 'depotcache', 'dumps', 'logs', 'package',
                      'steamapps', 'userdata', 'cache', 'htmlcache'}:
            raise SystemExit(f'Mutable state listed as Steam client package content: {windows_name}')
        key = str(relative).lower()
        candidate = (relative, size, crc)
        if key in files and files[key] != candidate:
            raise SystemExit(f'Conflicting Steam package entries: {windows_name}')
        files[key] = candidate

snapshot.mkdir(mode=0o700)
hashes = []
for relative, expected_size, expected_crc in sorted(files.values(), key=lambda item: str(item[0]).lower()):
    src = source / relative
    info = src.lstat()
    if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or
            info.st_uid != os.getuid() or info.st_size != expected_size):
        raise SystemExit(f'Invalid installed Steam package file: {src}')
    data = src.read_bytes()
    if zlib.crc32(data) != expected_crc:
        raise SystemExit(f'Steam package CRC mismatch: {src}')
    target = snapshot / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
    hashes.append(f'{sha256(data).hexdigest()}  {relative.as_posix()}')
# Preserve only the installed-inventory marker, not Steam's package downloads.
# Without this marker the final client needlessly downloads and reinstalls the
# same ~250 MB client before its first launch.
installed_manifest = manifests[0]
installed_info = installed_manifest.lstat()
if (not stat.S_ISREG(installed_info.st_mode) or stat.S_ISLNK(installed_info.st_mode) or
        installed_info.st_uid != os.getuid() or installed_info.st_nlink != 1):
    raise SystemExit(f'Unsafe Steam installed-file manifest: {installed_manifest}')
installed_data = installed_manifest.read_bytes()
installed_relative = Path('package/steam_client_win64.installed')
installed_target = snapshot / installed_relative
installed_target.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(installed_manifest, installed_target)
hashes.append(f'{sha256(installed_data).hexdigest()}  {installed_relative.as_posix()}')
(snapshot / '.pagonia-steam-client-SHA256SUMS').write_text('\n'.join(hashes) + '\n')
PY
  validate_clean_steam_snapshot "$snapshot"
}

validate_clean_steam_snapshot() {
  local snapshot=$1
  python3 - "$snapshot" <<'PY'
from hashlib import sha256
from pathlib import Path
import os
import re
import stat
import sys

root = Path(sys.argv[1]).resolve(strict=True)
manifest = root / '.pagonia-steam-client-SHA256SUMS'
manifest_info = manifest.lstat()
if (not stat.S_ISREG(manifest_info.st_mode) or stat.S_ISLNK(manifest_info.st_mode) or
        manifest_info.st_uid != os.getuid() or manifest_info.st_mode & 0o022):
    raise SystemExit(f'Invalid clean Steam snapshot manifest: {manifest}')
expected = {}
for number, line in enumerate(manifest.read_text().splitlines(), 1):
    match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
    if not match:
        raise SystemExit(f'Invalid clean Steam snapshot manifest line {number}')
    relative = Path(match.group(2))
    if relative.is_absolute() or '..' in relative.parts or str(relative) in expected:
        raise SystemExit(f'Unsafe or duplicate clean Steam path: {relative}')
    expected[str(relative)] = match.group(1)
for required in ('steam.exe', 'package/steam_client_win64.installed'):
    if required not in expected:
        raise SystemExit(f'Missing required clean Steam client entry: {required}')
actual = set()
for path in root.rglob('*'):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise SystemExit(f'Untrusted Steam snapshot entry: {path}')
    if path.is_dir() or path == manifest:
        continue
    relative = str(path.relative_to(root))
    actual.add(relative)
    if relative not in expected or sha256(path.read_bytes()).hexdigest() != expected[relative]:
        raise SystemExit(f'Unlisted or changed Steam snapshot file: {path}')
if actual != set(expected):
    raise SystemExit(f'Clean Steam snapshot inventory mismatch: missing={sorted(set(expected) - actual)}')
PY
}

install_clean_steam_seed() {
  local prefix=$1 wine_root=$2 setup_source=$3 snapshot=$4
  local setup="$prefix/drive_c/SteamSetup.exe" steam
  steam="$prefix/drive_c/Program Files (x86)/Steam"
  mkdir -p "$prefix/drive_c"
  copy_verified_file "$setup_source" "$setup" "$EXPECTED_STEAM_SETUP"
  echo '  Creating a clean pre-login Steam client seed with Wine 11.17...'
  launch_wine_program "$prefix" "$wine_root" "$prefix/steam-seed.log" "$setup" /S
  local attempt complete=0
  for attempt in $(jot 150); do
    if [[ -f "$steam/steam.exe" && -f "$steam/uninstall.exe" ]] \
       && ! "$PGREP_COMMAND" -u "$UID" -f 'SteamSetup\.exe' >/dev/null; then
      complete=1
      break
    fi
    ((attempt % 15 != 0)) || echo "  Still waiting for clean Steam seed (${attempt}/150 checks)..."
    "$SLEEP_COMMAND" 2
  done
  if [[ $complete -ne 1 ]]; then
    echo 'ERROR: Wine 11.17 could not create the clean Steam client seed.' >&2
    stop_wine_prefix "$prefix" "$wine_root" || true
    return 1
  fi
  stop_wine_prefix "$prefix" "$wine_root" || return 1

  # SteamSetup initially installs only the bootstrap client. Let that isolated,
  # no-login client update until every file in Valve's installed-package
  # inventory has its declared size and CRC. A rendered login window is not a
  # seed-completeness requirement and can be absent even after a valid update.
  deploy_downloader_graphics "$prefix" "$wine_root"
  local bootstrap_log="$steam/logs/bootstrap_log.txt"
  mkdir -p "$steam/logs"
  rm -f "$prefix/steam-seed-ui.log" "$bootstrap_log"
  echo '  Updating and validating the clean no-login Steam seed...'
  launch_wine_program "$prefix" "$wine_root" "$prefix/steam-seed-ui.log" \
    "$steam/steam.exe" -no-cef-sandbox
  local inventory_complete=0
  for attempt in $(jot 180); do
    if [[ -f "$bootstrap_log" ]] \
       && grep -Eq 'Update complete, launching Steam|Verification complete' "$bootstrap_log" \
       && steam_package_inventory_is_complete "$steam" 2>/dev/null; then
      inventory_complete=1
      break
    fi
    ((attempt % 10 != 0)) || echo "  Waiting for complete Steam package inventory (${attempt}/180 checks)..."
    "$SLEEP_COMMAND" 2 || break
  done
  stop_wine_prefix "$prefix" "$wine_root" || return 1
  [[ $inventory_complete -eq 1 ]] || {
    echo 'ERROR: Steam seed did not produce a complete package inventory.' >&2
    return 1
  }
  create_clean_steam_snapshot "$steam" "$snapshot"
}

initialize_gameplay_prefix() {
  local prefix=$1 wine_root=$2 log=$3
  if [[ -n "$WINE_RUNNER" ]]; then
    "$WINE_RUNNER" "$prefix" "$wine_root" "$log" wineboot -u
  else
    env WINEPREFIX="$prefix" WINEDEBUG='fixme-all' WINEESYNC=0 WINEMSYNC=0 \
      "$wine_root/bin/wine64" wineboot -u >>"$log" 2>&1
  fi
  stop_wine_prefix "$prefix" "$wine_root"
  require_dir "$prefix/drive_c/windows/system32"
  require_file "$prefix/user.reg"
}

install_clean_steam_snapshot() {
  local snapshot=$1 prefix=$2 wine_root=$3 steam=$4 plist=$5 log
  validate_clean_steam_snapshot "$snapshot"
  log="${prefix%/Contents/SharedSupport/prefix}/Contents/SharedSupport/Logs/LastRunWine.log"
  mkdir -p "$(dirname "$log")"
  initialize_gameplay_prefix "$prefix" "$wine_root" "$log"
  mkdir -p "$(dirname "$steam")"
  ditto "$snapshot" "$steam"
  validate_clean_steam_snapshot "$steam"
  rm -f "$steam/.pagonia-steam-client-SHA256SUMS"
  plutil -replace 'Program Name and Path' -string '/Program Files (x86)/Steam/steam.exe' "$plist"
  plutil -replace 'Program Flags' -string '-no-cef-sandbox' "$plist"
}

create_steam_session_snapshot() {
  local prefix=$1 snapshot=$2 steam
  steam="$prefix/drive_c/Program Files (x86)/Steam"
  python3 "$STEAM_SESSION_HELPER" create "$steam" "$snapshot"
  python3 "$STEAM_SESSION_HELPER" validate "$snapshot"
}

install_steam_session_snapshot() {
  local snapshot=$1 steam=$2
  STEAM_SESSION_ID=$(python3 "$STEAM_SESSION_HELPER" install "$snapshot" "$steam")
  [[ "$STEAM_SESSION_ID" =~ ^7656119[0-9]{10}$ ]] || {
    echo 'ERROR: Transferred Steam session has an invalid Steam ID.' >&2
    return 1
  }
}

verify_transferred_steam_login() {
  local prefix=$1 wine_root=$2 steam=$3 steam_id=$4 log connection_log
  local attempt authenticated=0 account_id
  account_id=$((10#$steam_id - 76561197960265728))
  log="$prefix/steam-session-verification.log"
  connection_log="$steam/logs/connection_log.txt"
  rm -f "$log" "$connection_log"
  echo '  Verifying transferred Steam login in the Wine 10 prefix...'
  launch_wine_program "$prefix" "$wine_root" "$log" \
    "$steam/steam.exe" -cef-disable-gpu -no-cef-sandbox -silent
  for attempt in $(jot 180); do
    if "$PGREP_COMMAND" -u "$UID" \
        -f "steamwebhelper\\.exe.*-+steamid=$steam_id" >/dev/null \
       && [[ -f "$connection_log" ]] \
       && python3 "$STEAM_LOGIN_LOG_HELPER" "$connection_log" "$account_id"; then
      authenticated=1
      break
    fi
    ((attempt % 10 != 0)) || echo "  Waiting for transferred Steam login (${attempt}/180 checks)..."
    "$SLEEP_COMMAND" 2 || break
  done
  stop_wine_prefix "$prefix" "$wine_root" || return 1
  [[ $authenticated -eq 1 ]] || {
    echo 'ERROR: Steam did not authenticate the transferred login in the Wine 10 prefix.' >&2
    return 1
  }
  echo '  Transferred Steam login verified.'
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

validate_downloader_runtime() {
  local wine_root=$1 dxvk_root wine_target='../lib/wine/x86_64-unix/wine'
  dxvk_root="${wine_root%/wine}/dxvk"
  for launcher in wine wine64 wineloader; do
    [[ -L "$wine_root/bin/$launcher" \
       && "$(readlink "$wine_root/bin/$launcher")" == "$wine_target" ]] || {
      echo "ERROR: Unexpected Wine 11.17 launcher link: $wine_root/bin/$launcher" >&2
      return 1
    }
  done
  require_hash "$wine_root/lib/wine/x86_64-unix/wine" "$EXPECTED_DOWNLOADER_WINE"
  require_hash "$wine_root/bin/wineserver" "$EXPECTED_DOWNLOADER_WINESERVER"
  require_hash "$wine_root/lib/wine/x86_64-unix/ntdll.so" "$EXPECTED_DOWNLOADER_NTDLL_UNIX"
  require_hash "$wine_root/lib/wine/x86_64-windows/ntdll.dll" "$EXPECTED_DOWNLOADER_NTDLL_WINDOWS"
  require_hash "$dxvk_root/x64/d3d10core.dll" "$EXPECTED_DXVK_X64_D3D10CORE"
  require_hash "$dxvk_root/x64/d3d11.dll" "$EXPECTED_DXVK_X64_D3D11"
  require_hash "$dxvk_root/x32/d3d10core.dll" "$EXPECTED_DXVK_X32_D3D10CORE"
  require_hash "$dxvk_root/x32/d3d11.dll" "$EXPECTED_DXVK_X32_D3D11"
}

deploy_downloader_graphics() {
  local prefix=$1 wine_root=$2 dxvk_root system32 syswow64
  dxvk_root="${wine_root%/wine}/dxvk"
  system32="$prefix/drive_c/windows/system32"
  syswow64="$prefix/drive_c/windows/syswow64"
  validate_downloader_runtime "$wine_root"
  cp -p "$dxvk_root/x64/d3d10core.dll" "$system32/d3d10core.dll"
  cp -p "$dxvk_root/x64/d3d11.dll" "$system32/d3d11.dll"
  cp -p "$dxvk_root/x32/d3d10core.dll" "$syswow64/d3d10core.dll"
  cp -p "$dxvk_root/x32/d3d11.dll" "$syswow64/d3d11.dll"
  cp -p "$wine_root/lib/wine/x86_64-windows/dxgi.dll" "$system32/dxgi.dll"
  python3 - "$system32/dxgi.dll" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
data = bytearray(path.read_bytes())
if len(data) < 0x50:
    raise SystemExit('Wine dxgi.dll is too short to remove its builtin marker')
data[0x40:0x50] = bytes((
    0x0e, 0x1f, 0xba, 0x0e, 0x00, 0xb4, 0x09, 0xcd,
    0x21, 0xb8, 0x01, 0x4c, 0xcd, 0x21, 0x90, 0x90,
))
path.write_bytes(data)
PY
  require_hash "$system32/dxgi.dll" "$EXPECTED_DOWNLOADER_NATIVE_DXGI"
  python3 - "$prefix/user.reg" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
text = path.read_text(errors='surrogateescape')
executables = (
    'steam.exe', 'steamwebhelper.exe', 'steamservice.exe',
    'gameoverlayui.exe', 'gameoverlayui64.exe',
)
for executable in executables:
    escaped = re.escape(executable)
    text = re.sub(
        rf'(?ms)^\[Software\\\\Wine\\\\AppDefaults\\\\{escaped}\\\\DllOverrides\][^\n]*\n'
        rf'.*?(?=^\[|\Z)', '', text,
    )
    text += (
        f'\n[Software\\\\Wine\\\\AppDefaults\\\\{executable}\\\\DllOverrides] 0\n'
        '#time=1\n'
        '"d3d10core"="native,builtin"\n'
        '"d3d11"="native,builtin"\n'
        '"dxgi"="native,builtin"\n'
    )
path.write_text(text, errors='surrogateescape')
PY
}

validate_downloaded_depot() {
  local prefix=$1 steam game appmanifest
  steam="$prefix/drive_c/Program Files (x86)/Steam"
  game="$steam/steamapps/common/Pioneers of Pagonia"
  appmanifest="$steam/steamapps/appmanifest_2155180.acf"
  require_file "$appmanifest"
  python3 - "$prefix" "$game" "$GAME_HASH_MANIFEST" "$appmanifest" "$EXPECTED_BUILD_ID" <<'PY'
from hashlib import sha256
from pathlib import Path
import re
import stat
import sys

prefix_input = Path(sys.argv[1])
prefix = prefix_input.resolve(strict=True)
raw_root = Path(sys.argv[2])
manifest = Path(sys.argv[3])
appmanifest = Path(sys.argv[4])
expected_build = sys.argv[5]
for critical in (raw_root, appmanifest):
    current = prefix_input
    try:
        relative = critical.relative_to(prefix_input)
    except ValueError:
        raise SystemExit(f'Transfer path is outside prefix: {critical}')
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise SystemExit(f'Linked transfer path is not permitted: {current}')
    resolved = critical.resolve(strict=True)
    if prefix not in resolved.parents:
        raise SystemExit(f'Transfer path escapes prefix: {critical}')
root = raw_root.resolve(strict=True)
expected = {}
for line in manifest.read_text().splitlines():
    if not line or line.startswith('#'):
        continue
    digest, relative = line.split('  ', 1)
    candidate = Path(relative)
    if (len(digest) != 64 or not re.fullmatch(r'[0-9a-f]{64}', digest) or
            candidate.is_absolute() or '..' in candidate.parts or
            relative in expected):
        raise SystemExit(f'Invalid game manifest entry: {line}')
    expected[relative] = digest
if len(expected) != 856:
    raise SystemExit(f'Expected 856 game files, manifest has {len(expected)}')
total_size = 0
for relative, digest in expected.items():
    path = root / relative
    current = root
    for part in Path(relative).parts:
        current /= part
        if current.is_symlink():
            raise SystemExit(f'Linked game path is not permitted: {current}')
    try:
        info = path.lstat()
    except FileNotFoundError:
        raise SystemExit(f'Missing game file: {relative}')
    if not stat.S_ISREG(info.st_mode):
        raise SystemExit(f'Non-regular game file: {relative}')
    actual = sha256(path.read_bytes()).hexdigest()
    if actual != digest:
        raise SystemExit(f'Game file hash mismatch: {relative}')
    total_size += info.st_size

def parse_vdf(text):
    token_re = re.compile(r'\s*(?:"((?:\\.|[^"\\])*)"|([{}]))', re.DOTALL)
    tokens = []
    position = 0
    while position < len(text):
        if not text[position:].strip():
            break
        match = token_re.match(text, position)
        if not match:
            raise SystemExit(f'Invalid appmanifest syntax at byte {position}')
        tokens.append(('string', match.group(1)) if match.group(1) is not None
                      else (match.group(2), match.group(2)))
        position = match.end()

    def object_at(index):
        if index >= len(tokens) or tokens[index][0] != '{':
            raise SystemExit('Expected appmanifest object')
        index += 1
        result = {}
        while index < len(tokens) and tokens[index][0] != '}':
            if tokens[index][0] != 'string':
                raise SystemExit('Expected appmanifest key')
            key = tokens[index][1]
            index += 1
            if key in result:
                raise SystemExit(f'Duplicate appmanifest key: {key}')
            if index < len(tokens) and tokens[index][0] == 'string':
                result[key] = tokens[index][1]
                index += 1
            elif index < len(tokens) and tokens[index][0] == '{':
                result[key], index = object_at(index)
            else:
                raise SystemExit(f'Missing appmanifest value for {key}')
        if index >= len(tokens):
            raise SystemExit('Unbalanced appmanifest braces')
        return result, index + 1

    if len(tokens) < 2 or tokens[0] != ('string', 'AppState'):
        raise SystemExit('Appmanifest does not start with AppState')
    parsed, end = object_at(1)
    if end != len(tokens):
        raise SystemExit('Trailing appmanifest data')
    return parsed

fields = parse_vdf(appmanifest.read_text(errors='strict'))
required = {
    'appid': '2155180', 'StateFlags': '4', 'buildid': expected_build,
    'installdir': 'Pioneers of Pagonia', 'SizeOnDisk': str(total_size),
}
for key, value in required.items():
    if fields.get(key) != value:
        raise SystemExit(f'Invalid appmanifest field {key}: {fields.get(key)!r}')
expected_depots = {
    '2155181': {'manifest': '839939076860606424', 'size': str(total_size)},
}
if fields.get('InstalledDepots') != expected_depots:
    raise SystemExit('InstalledDepots does not match pinned build 25784167')
if fields.get('SharedDepots') != {'228989': '228980'}:
    raise SystemExit('SharedDepots does not match pinned build 25784167')
print(f'Validated {len(expected)} manifest-listed game files ({total_size} bytes).')
PY
}

import_validated_depot() {
  local source_prefix=$1 destination_prefix=$2 steam_owner=$3 source_steam destination_steam
  source_steam="$source_prefix/drive_c/Program Files (x86)/Steam"
  destination_steam="$destination_prefix/drive_c/Program Files (x86)/Steam"
  python3 - "$source_steam/steamapps/common/Pioneers of Pagonia" \
    "$destination_steam/steamapps/common/Pioneers of Pagonia" \
    "$GAME_HASH_MANIFEST" \
    "$source_steam/steamapps/appmanifest_2155180.acf" \
    "$destination_steam/steamapps/appmanifest_2155180.acf" \
    "$steam_owner" <<'PY'
from pathlib import Path
import os
import shutil
import stat
import sys

source, destination, manifest, source_acf, destination_acf = map(Path, sys.argv[1:6])
steam_owner = sys.argv[6]
if not steam_owner.isdecimal() or len(steam_owner) != 17:
    raise SystemExit('Invalid Steam owner for sanitized appmanifest')
destination.mkdir(parents=True, exist_ok=False)
entries = []
for line in manifest.read_text().splitlines():
    if line and not line.startswith('#'):
        _, relative = line.split('  ', 1)
        entries.append(relative)
for relative in entries:
    source_path = source / relative
    destination_path = destination / relative
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    source_fd = os.open(source_path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        with os.fdopen(source_fd, 'rb') as input_file, open(destination_path, 'xb') as output_file:
            shutil.copyfileobj(input_file, output_file, 1024 * 1024)
        shutil.copystat(source_path, destination_path, follow_symlinks=False)
    except BaseException:
        try:
            os.close(source_fd)
        except OSError:
            pass
        raise
source_acf_info = source_acf.lstat()
if not stat.S_ISREG(source_acf_info.st_mode):
    raise SystemExit('Source appmanifest changed before selective import')
total_size = sum((source / relative).stat().st_size for relative in entries)
destination_acf.parent.mkdir(parents=True, exist_ok=True)
sanitary_appmanifest = f'''"AppState"
{{
\t"appid"\t\t"2155180"
\t"Universe"\t\t"1"
\t"LauncherPath"\t\t"C:\\\\Program Files (x86)\\\\Steam\\\\steam.exe"
\t"name"\t\t"Pioneers of Pagonia"
\t"StateFlags"\t\t"4"
\t"installdir"\t\t"Pioneers of Pagonia"
\t"LastUpdated"\t\t"0"
\t"LastPlayed"\t\t"0"
\t"SizeOnDisk"\t\t"{total_size}"
\t"StagingSize"\t\t"0"
\t"buildid"\t\t"25784167"
\t"LastOwner"\t\t"{steam_owner}"
\t"DownloadType"\t\t"1"
\t"UpdateResult"\t\t"0"
\t"BytesToDownload"\t\t"0"
\t"BytesDownloaded"\t\t"0"
\t"BytesToStage"\t\t"0"
\t"BytesStaged"\t\t"0"
\t"TargetBuildID"\t\t"25784167"
\t"AutoUpdateBehavior"\t\t"0"
\t"AllowOtherDownloadsWhileRunning"\t\t"0"
\t"ScheduledAutoUpdate"\t\t"0"
\t"InstalledDepots"
\t{{
\t\t"2155181"
\t\t{{
\t\t\t"manifest"\t\t"839939076860606424"
\t\t\t"size"\t\t"{total_size}"
\t\t}}
\t}}
\t"SharedDepots"
\t{{
\t\t"228989"\t\t"228980"
\t}}
}}
'''
with destination_acf.open('x', encoding='utf-8', newline='') as output_file:
    output_file.write(sanitary_appmanifest)
PY
}

find_active_pagonia_staging() {
  ps -U "$UID" -o command= | python3 -c '
import re
import sys
from pathlib import Path
roots = set()
pattern = re.compile(r"(/(?:private/)?tmp/Pagonia-GPTK4b3-deployment\.[^/ ]+)/(?:Steam Downloader|Pioneers of Pagonia)\.app/.*/wineserver")
for line in sys.stdin:
    match = pattern.search(line)
    if match:
        roots.add(str(Path(match.group(1)).resolve()))
for root in sorted(roots):
    print(root)
'
}

pagonia_staging_is_active() {
  local expected=$1 active
  while IFS= read -r active; do
    [[ "$active" != "$expected" ]] || return 0
  done < <(find_active_pagonia_staging)
  return 1
}

find_resumable_downloader_staging() {
  python3 - "$GAME_HASH_MANIFEST_NAME" "$EXPECTED_GAME_HASH_MANIFEST" \
    "$EXPECTED_WINESKIN_LAUNCHER" "$EXPECTED_STEAM_SETUP" <<'PY'
from hashlib import sha256
from pathlib import Path
import os
import re
import stat
import sys

manifest_name, manifest_hash, launcher_hash, setup_hash = sys.argv[1:]
root = Path('/private/tmp')
if root.is_dir() and not root.is_symlink():
    for path in root.glob('Pagonia-GPTK4b3-deployment.*'):
        try:
            valid_name = re.fullmatch(r'Pagonia-GPTK4b3-deployment\.[A-Za-z0-9]+', path.name)
            app = path / 'Steam Downloader.app'
            manifest = path / manifest_name
            launcher = app / 'Contents/MacOS/wineskinlauncher'
            prefix = app / 'Contents/SharedSupport/prefix'
            steam = prefix / 'drive_c/Program Files (x86)/Steam/steam.exe'
            setup = prefix / 'drive_c/SteamSetup.exe'
            private = stat.S_IMODE(path.lstat().st_mode) & 0o077 == 0
            steam_regular = (steam.exists() and not steam.is_symlink() and
                             stat.S_ISREG(steam.lstat().st_mode))
            setup_regular = (setup.exists() and not setup.is_symlink() and
                             stat.S_ISREG(setup.lstat().st_mode))
            valid_setup_state = steam_regular or (
                setup_regular and sha256(setup.read_bytes()).hexdigest() == setup_hash)
            if (valid_name and path.is_dir() and not path.is_symlink() and private and
                    path.lstat().st_uid == os.getuid() and app.is_dir() and
                    not app.is_symlink() and manifest.is_file() and launcher.is_file() and
                    sha256(manifest.read_bytes()).hexdigest() == manifest_hash and
                    sha256(launcher.read_bytes()).hexdigest() == launcher_hash and
                    valid_setup_state):
                print(path.resolve())
        except (FileNotFoundError, PermissionError):
            pass
PY
}

resume_pagonia_staging() {
  local requested=${1%/} root app prefix manifest state='' build='' attempt plist wine_root steam private_game_manifest service_installed=0
  root=$(python3 - "$requested" <<'PY'
from pathlib import Path
import re
import sys
raw = Path(sys.argv[1])
if (not raw.is_absolute() or raw.parent != Path('/private/tmp') or
        not re.fullmatch(r'Pagonia-GPTK4b3-deployment\.[A-Za-z0-9]+', raw.name)):
    raise SystemExit(f'Invalid resume path: {raw}')
path = raw.resolve(strict=True)
if path.parent != Path('/private/tmp') or path.name != raw.name:
    raise SystemExit(f'Invalid resume path: {raw}')
print(path)
PY
) || return 1
  [[ -d "$root" && ! -L "$root" && "$(stat -f '%u' "$root")" == "$UID" ]] || {
    echo "ERROR: Invalid or untrusted resume path: $root" >&2
    return 1
  }
  [[ $((8#$(stat -f '%Lp' "$root") & 8#077)) -eq 0 ]] || {
    echo "ERROR: Resume root is accessible by group or other users: $root" >&2
    return 1
  }
  echo 'Resume 1/4: Validating the preserved downloader staging...'
  RESUME_SOURCE_ROOT=$root
  RESUME_SOURCE_DEVICE=$(stat -f '%d' "$root")
  RESUME_SOURCE_INODE=$(stat -f '%i' "$root")
  private_game_manifest="$root/$GAME_HASH_MANIFEST_NAME"
  require_hash "$private_game_manifest" "$EXPECTED_GAME_HASH_MANIFEST"
  GAME_HASH_MANIFEST=$private_game_manifest
  app="$root/Steam Downloader.app"
  prefix="$app/Contents/SharedSupport/prefix"
  wine_root="$app/Contents/SharedSupport/wine"
  steam="$prefix/drive_c/Program Files (x86)/Steam"
  manifest="$steam/steamapps/appmanifest_2155180.acf"
  plist="$app/Contents/Info.plist"
  require_dir "$app"
  require_dir "$prefix"
  require_file "$plist"
  require_hash "$app/Contents/MacOS/wineskinlauncher" "$EXPECTED_WINESKIN_LAUNCHER"
  [[ "$(plutil -extract CFBundleExecutable raw "$plist")" == 'wineskinlauncher' ]] || {
    echo 'ERROR: Resumable downloader has an unexpected bundle executable.' >&2
    return 1
  }
  python3 - "$app" <<'PY'
from pathlib import Path
import os
import stat
import sys

app = Path(sys.argv[1]).resolve(strict=True)
required = [
    'Contents', 'Contents/MacOS', 'Contents/MacOS/wineskinlauncher',
    'Contents/SharedSupport',
    'Contents/SharedSupport/prefix', 'Contents/SharedSupport/prefix/drive_c',
    'Contents/Info.plist',
]
steam_root = Path('Contents/SharedSupport/prefix/drive_c/Program Files (x86)/Steam')
setup = Path('Contents/SharedSupport/prefix/drive_c/SteamSetup.exe')
if (app / steam_root).exists():
    required.extend([str(steam_root.parent), str(steam_root)])
    for executable in (steam_root / 'steam.exe', steam_root / 'uninstall.exe'):
        if (app / executable).exists():
            required.append(str(executable))
elif (app / setup).exists():
    required.append(str(setup))
else:
    raise SystemExit('Resume prefix has neither Steam nor its pinned installer')
for relative in required:
    current = app
    for part in Path(relative).parts:
        current /= part
        if current.is_symlink() and current.name != 'wine64':
            raise SystemExit(f'Linked resume path is not permitted: {current}')
    info = current.lstat()
    if info.st_uid != os.getuid():
        raise SystemExit(f'Untrusted owner for resume path: {current}')
for relative in (steam_root / 'steam.exe', steam_root / 'uninstall.exe'):
    path = app / relative
    if path.exists() and not stat.S_ISREG(path.lstat().st_mode):
        raise SystemExit(f'Resume Steam executable is not regular: {path}')
PY
  same_identity "$root" "$RESUME_SOURCE_DEVICE" "$RESUME_SOURCE_INODE" || {
    echo 'ERROR: Resume root changed during validation.' >&2
    return 1
  }
  if [[ -f "$manifest" ]]; then
    state=$(awk -F'"' '/"StateFlags"/{print $4; exit}' "$manifest" 2>/dev/null || true)
    build=$(awk -F'"' '/"buildid"/{print $4; exit}' "$manifest" 2>/dev/null || true)
  fi
  if [[ "$state" == '4' && "$build" == "$EXPECTED_BUILD_ID" ]]; then
    if pagonia_staging_is_active "$root"; then
      if ! steam_processes_belong_to_prefix "$prefix"; then
        echo 'ERROR: Active staging wineserver does not own every Steam process.' >&2
        return 1
      fi
      terminate_staging_processes_without_runtime "$root" "$prefix" || return 1
    elif steam_processes_running; then
      echo 'ERROR: Another Steam instance is running; refusing to validate the completed staging.' >&2
      return 1
    fi
    same_identity "$root" "$RESUME_SOURCE_DEVICE" "$RESUME_SOURCE_INODE" || {
      echo 'ERROR: Resume root changed before completed-depot validation.' >&2
      return 1
    }
    validate_downloaded_depot "$prefix"
    echo "Validated completed split-runtime download for resume: $root"
    DOWNLOADER_SOURCE_PREFIX=$prefix
    return 0
  fi
  state=''
  build=''

  if pagonia_staging_is_active "$root"; then
    if ! steam_processes_belong_to_prefix "$prefix"; then
      echo 'ERROR: Active staging wineserver does not own every Steam process.' >&2
      return 1
    fi
    terminate_staging_processes_without_runtime "$root" "$prefix" || return 1
  fi
  if steam_processes_running; then
    echo 'ERROR: Another Steam instance is running; refusing to mix Wine prefixes.' >&2
    return 1
  fi

  # Never execute mutable runtime files retained from an interrupted session.
  # Replace them from the pinned archive after every incomplete resume.
  echo 'Resume 2/4: Extracting a fresh pinned Wine 11.17 runtime...'
  local refresh
  refresh=$(mktemp -d "$root/.runtime-refresh.XXXXXX") || return 1
  if ! tar -xf "$DOWNLOADER_ARCHIVE" -C "$refresh"; then
    rm -rf "$refresh"
    return 1
  fi
  mkdir -m 700 "$refresh/normalized"
  if ! ditto "$refresh/steam-wine11.bundle/Wine" \
      "$refresh/normalized/wine" \
     || ! ditto "$refresh/steam-wine11.bundle/DXVK" \
      "$refresh/normalized/dxvk" \
     || ! validate_downloader_runtime "$refresh/normalized/wine"; then
    rm -rf "$refresh"
    return 1
  fi
  rm -rf "$wine_root" "$app/Contents/SharedSupport/dxvk"
  mv "$refresh/normalized/wine" "$wine_root"
  mv "$refresh/normalized/dxvk" "$app/Contents/SharedSupport/dxvk"
  rm -rf "$refresh"
  validate_downloader_runtime "$wine_root" || return 1
  echo 'Resume 3/4: Deploying the verified Steam graphics configuration...'

  if [[ ! -f "$steam/steam.exe" || -L "$steam/steam.exe" \
        || ! -f "$steam/uninstall.exe" || -L "$steam/uninstall.exe" ]]; then
    echo 'The interrupted downloader did not finish SteamSetup; restarting it safely.'
    require_hash "$prefix/drive_c/SteamSetup.exe" "$EXPECTED_STEAM_SETUP"
    install_steam_in_prefix "$app" "$prefix" "$wine_root" "$steam" "$plist" \
      "$prefix/drive_c/SteamSetup.exe" || return 1
    service_installed=1
  fi
  if [[ $service_installed -eq 0 ]]; then
    install_steam_service "$app" "$prefix" "$wine_root" || return 1
    stop_wine_prefix "$prefix" "$wine_root" || return 1
  fi
  deploy_downloader_graphics "$prefix" "$wine_root" || return 1
  DOWNLOADER_APP=$app
  DOWNLOADER_PREFIX=$prefix
  DOWNLOADER_WINE=$wine_root

  echo 'Resume 4/4: Starting Steam from the refreshed runtime...'
  echo 'The interrupted Wine 11.17 downloader is starting from a refreshed runtime.'
  plutil -replace 'Program Name and Path' -string '/Program Files (x86)/Steam/steam.exe' "$plist"
  plutil -replace 'Program Flags' -string '-no-cef-sandbox -vgui' "$plist"
  launch_steam_ui "$app" "$prefix" "$wine_root" "$steam" || return 1
  wait_for_steam_authentication "$steam" || return 1
  request_pagonia_install "$app" "$prefix" "$wine_root" "$steam" || return 1

  echo "Resuming interrupted split-runtime download: $root"
  echo 'Keep Steam open, sign in, and install Pioneers of Pagonia.'
  for attempt in $(jot 10800); do
    state=''; build=''
    if [[ -f "$manifest" ]]; then
      state=$(awk -F'"' '/"StateFlags"/{print $4; exit}' "$manifest" 2>/dev/null || true)
      build=$(awk -F'"' '/"buildid"/{print $4; exit}' "$manifest" 2>/dev/null || true)
      [[ "$state" == '4' && "$build" == "$EXPECTED_BUILD_ID" ]] && break
    fi
    ((attempt % 15 != 0)) || echo "  Waiting for Pagonia: StateFlags=${state:-missing}, build=${build:-missing}"
    "$SLEEP_COMMAND" 2
  done
  [[ "$state" == '4' && "$build" == "$EXPECTED_BUILD_ID" ]] || {
    echo "ERROR: Pagonia did not complete as build $EXPECTED_BUILD_ID." >&2
    return 1
  }
  stop_wine_prefix "$prefix" "$wine_root" || return 1
  same_identity "$root" "$RESUME_SOURCE_DEVICE" "$RESUME_SOURCE_INODE" || {
    echo 'ERROR: Resume root changed before depot validation.' >&2
    return 1
  }
  validate_downloaded_depot "$prefix"
  DOWNLOADER_SOURCE_PREFIX=$prefix
}

discover_pagonia_installations() {
  python3 - "$HOME" "$EXPECTED_BUILD_ID" "$EXPECTED_GAME_EXE" <<'PY'
from hashlib import sha256
from pathlib import Path
import os
import plistlib
import re
import stat
import sys

home = Path(sys.argv[1]).resolve()
expected_build, expected_exe = sys.argv[2:4]
candidates = set()

def regular_unlinked(path):
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except FileNotFoundError:
        return False

def safe_child(root, path):
    current = root
    try:
        for part in path.relative_to(root).parts:
            current /= part
            if current.is_symlink():
                return False
    except (OSError, ValueError):
        return False
    return True

def valid_application(root, path):
    marker = path / 'Contents/SharedSupport/Pagonia-GPTK4b3-deployment.txt'
    plist = path / 'Contents/Info.plist'
    if (path.suffix != '.app' or not safe_child(root, marker) or
            not safe_child(root, plist) or not regular_unlinked(marker) or
            not regular_unlinked(plist)):
        return False
    try:
        if not marker.read_text(errors='replace').startswith(
                'Pioneers of Pagonia GPTK deployment\n'):
            return False
        return plistlib.loads(plist.read_bytes()).get('CFBundleIdentifier') == \
            'com.soad1337.pioneersofpagonia.gptk4b3'
    except (OSError, ValueError, plistlib.InvalidFileException):
        return False

def valid_dedicated_prefix(root, path):
    steamapps = path / 'drive_c/Program Files (x86)/Steam/steamapps'
    manifest = steamapps / 'appmanifest_2155180.acf'
    game = steamapps / 'common/Pioneers of Pagonia/Pioneers of Pagonia.exe'
    if not all(safe_child(root, item) and regular_unlinked(item)
               for item in (manifest, game)):
        return False
    manifests = sorted(item.name for item in steamapps.glob('appmanifest_*.acf')
                       if regular_unlinked(item))
    if manifests != ['appmanifest_2155180.acf']:
        return False
    try:
        text = manifest.read_text(errors='replace')
        build = re.search(r'"buildid"\s+"([^"]+)"', text)
        state = re.search(r'"StateFlags"\s+"([^"]+)"', text)
        digest = sha256(game.read_bytes()).hexdigest()
        return (build and build.group(1) == expected_build and state and
                state.group(1) == '4' and digest == expected_exe)
    except OSError:
        return False

for root in (Path('/Applications'), home / 'Applications'):
    if not root.is_dir() or root.is_symlink():
        continue
    root = root.resolve()
    for path in root.iterdir():
        if path.is_dir() and not path.is_symlink() and valid_application(root, path):
            candidates.add(path)
games = home / 'Games'
if games.is_dir() and not games.is_symlink():
    games = games.resolve()
    for path in games.iterdir():
        if path.is_dir() and not path.is_symlink() and valid_dedicated_prefix(games, path):
            candidates.add(path)
for path in sorted(candidates, key=lambda item: str(item).lower()):
    sys.stdout.buffer.write(os.fsencode(path) + b'\0')
PY
}

discover_possible_pagonia_paths() {
  python3 - "$HOME" <<'PY'
from pathlib import Path
import os
import sys

home = Path(sys.argv[1]).resolve()
paths = set()
for root in (Path('/Applications'), home / 'Applications', home / 'Games'):
    if not root.is_dir() or root.is_symlink():
        continue
    root = root.resolve()
    for path in root.iterdir():
        if 'pagonia' in path.name.lower() and not path.is_symlink():
            paths.add(path)
# Include private, interrupted installer deployments. List the deployment root
# rather than its nested app so deletion does not leave staging debris behind.
temporary = Path('/private/tmp')
if temporary.is_dir() and not temporary.is_symlink():
    for path in temporary.glob('Pagonia-GPTK4b3-deployment.*'):
        try:
            owned = path.lstat().st_uid == os.getuid()
        except FileNotFoundError:
            continue
        if path.is_dir() and not path.is_symlink() and owned:
            paths.add(path)
for path in sorted(paths, key=lambda item: str(item).lower()):
    sys.stdout.buffer.write(os.fsencode(path) + b'\0')
PY
}

verify_single_filesystem_tree() {
  python3 - "$1" <<'PY'
from pathlib import Path
import os
import stat
import sys

root = Path(sys.argv[1])
device = root.lstat().st_dev
for current, dirs, files in os.walk(root, followlinks=False):
    for name in dirs + files:
        path = Path(current) / name
        mode = path.lstat().st_mode
        if not stat.S_ISLNK(mode) and path.lstat().st_dev != device:
            raise SystemExit(f'Nested mount or foreign filesystem: {path}')
PY
}

delete_one_pagonia_installation() {
  local selected=$1 device=$2 inode=$3 parent delete_root quarantined
  if ! same_identity "$selected" "$device" "$inode"; then
    echo "ERROR: Installation changed after discovery: $selected" >&2
    return 1
  fi
  verify_single_filesystem_tree "$selected"
  parent=$(dirname "$selected")
  delete_root=$(mktemp -d "$parent/.Pagonia-delete.XXXXXX")
  chmod 700 "$delete_root"
  quarantined="$delete_root/deleted-installation"
  trap '' INT TERM
  if ! same_identity "$selected" "$device" "$inode"; then
    trap on_signal INT TERM
    echo "ERROR: Installation changed before deletion: $selected" >&2
    rmdir "$delete_root" 2>/dev/null || true
    return 1
  fi
  if ! atomic_rename_exclusive "$selected" "$quarantined"; then
    trap on_signal INT TERM
    echo "ERROR: Could not quarantine installation: $selected" >&2
    rmdir "$delete_root" 2>/dev/null || true
    return 1
  fi
  if ! same_identity "$quarantined" "$device" "$inode"; then
    trap on_signal INT TERM
    echo "ERROR: Quarantined identity changed; left untouched at: $quarantined" >&2
    return 1
  fi
  if ! python3 - "$delete_root" "$device" "$inode" <<'PY'
import os
import stat
import sys

parent, expected_device, expected_inode = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])

def remove_entry(parent_fd, name):
    info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if info.st_dev != expected_device:
        raise OSError(f'Refusing foreign filesystem during deletion: {name}')
    if not stat.S_ISDIR(info.st_mode):
        os.unlink(name, dir_fd=parent_fd)
        return
    child_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                       dir_fd=parent_fd)
    try:
        opened = os.fstat(child_fd)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise OSError(f'Directory changed while opening for deletion: {name}')
        if opened.st_dev != expected_device:
            raise OSError(f'Refusing mounted directory during deletion: {name}')
        for child in os.listdir(child_fd):
            remove_entry(child_fd, child)
    finally:
        os.close(child_fd)
    os.rmdir(name, dir_fd=parent_fd)

fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
try:
    info = os.stat('deleted-installation', dir_fd=fd, follow_symlinks=False)
    if (info.st_dev, info.st_ino) != (expected_device, expected_inode):
        raise SystemExit('Quarantined deletion target identity changed')
    remove_entry(fd, 'deleted-installation')
finally:
    os.close(fd)
PY
  then
    trap on_signal INT TERM
    echo "ERROR: Deletion incomplete; quarantined data remains in: $delete_root" >&2
    return 1
  fi
  if ! rmdir "$delete_root"; then
    trap on_signal INT TERM
    echo "ERROR: Could not remove deletion quarantine: $delete_root" >&2
    return 1
  fi
  trap on_signal INT TERM
  echo "Deleted: $selected"
}

delete_pagonia_installation() {
  local candidate selection size kind index=1 discovery suspect_file token duplicate found choice_index
  local -a candidates=() suspects=() choices=() selected=() tokens=()
  local -a choice_devices=() choice_inodes=()
  discovery=$(mktemp '/tmp/Pagonia-discovery.XXXXXX')
  if ! discover_pagonia_installations >"$discovery"; then
    rm -f "$discovery"
    echo 'ERROR: Could not inspect Pagonia installations.' >&2
    return 1
  fi
  while IFS= read -r -d '' candidate; do
    candidates[${#candidates[@]}]="$candidate"
  done <"$discovery"
  rm -f "$discovery"
  suspect_file=$(mktemp '/tmp/Pagonia-suspects.XXXXXX')
  if ! discover_possible_pagonia_paths >"$suspect_file"; then
    rm -f "$suspect_file"
    echo 'ERROR: Could not inspect possible Pagonia paths.' >&2
    return 1
  fi
  while IFS= read -r -d '' candidate; do
    found=0
    if [[ ${#candidates[@]} -gt 0 ]]; then
      for selection in "${candidates[@]}"; do
        [[ "$selection" != "$candidate" ]] || found=1
      done
    fi
    [[ $found -eq 1 ]] || suspects[${#suspects[@]}]="$candidate"
  done <"$suspect_file"
  rm -f "$suspect_file"

  echo
  echo 'Verified Pagonia installations:'
  if [[ ${#candidates[@]} -eq 0 ]]; then
    echo '  None found in /Applications, ~/Applications, or ~/Games.'
  fi
  if [[ ${#candidates[@]} -gt 0 ]]; then
    for candidate in "${candidates[@]}"; do
      size=$(du -sh "$candidate" 2>/dev/null | awk '{print $1}' || true)
      [[ "$candidate" == *.app ]] && kind='application' || kind='dedicated Wine prefix'
      printf '  %d) %q [%s, %s]\n' "$index" "$candidate" "$kind" "${size:-unknown size}"
      index=$((index + 1))
    done
  fi
  if [[ ${#candidates[@]} -gt 0 ]]; then
    choices=("${candidates[@]}")
  fi
  if [[ ${#suspects[@]} -gt 0 ]]; then
    echo
    echo 'Additional possible Pagonia paths (broad name match; review carefully):'
    for candidate in "${suspects[@]}"; do
      size=$(du -sh "$candidate" 2>/dev/null | awk '{print $1}' || true)
      printf '  %d) %q [unverified name match, %s]\n' "$index" "$candidate" "${size:-unknown size}"
      choices[${#choices[@]}]="$candidate"
      index=$((index + 1))
    done
  fi
  if [[ ${#choices[@]} -eq 0 ]]; then
    [[ $DESTINATION_EXPLICIT -eq 0 ]] || return 1
    return 0
  fi
  for candidate in "${choices[@]}"; do
    [[ -e "$candidate" && ! -L "$candidate" ]] || {
      echo "ERROR: Candidate changed during discovery: $candidate" >&2
      return 1
    }
    choice_devices[${#choice_devices[@]}]=$(stat -f '%d' "$candidate")
    choice_inodes[${#choice_inodes[@]}]=$(stat -f '%i' "$candidate")
  done

  if [[ $DESTINATION_EXPLICIT -eq 1 ]]; then
    [[ "$DESTINATION" == /* && ! -L "$DESTINATION" ]] || {
      echo 'ERROR: Deletion target must be an exact absolute, non-symlink path from the list.' >&2
      return 1
    }
    for candidate in "${choices[@]}"; do
      [[ "$candidate" != "$DESTINATION" ]] || selected[0]="$candidate"
    done
    [[ ${#selected[@]} -eq 1 ]] || {
      echo 'ERROR: --destination is not one of the detected installations.' >&2
      return 1
    }
  else
    if [[ $ASSUME_YES -eq 1 ]]; then
      echo 'ERROR: --delete --yes requires an exact --destination from the list.' >&2
      return 1
    fi
    printf 'Select installations (for example 1,2; all; or 0 to cancel): '
    read -r selection
    if [[ "$selection" == 0 ]]; then
      echo 'Cancelled.'
      return 0
    elif [[ "$selection" == all ]]; then
      selected=("${choices[@]}")
    else
      IFS=',' read -r -a tokens <<<"$selection"
      for token in "${tokens[@]}"; do
        token=${token//[[:space:]]/}
        [[ "$token" =~ ^[0-9]+$ ]] \
          && ((token >= 1 && token <= ${#choices[@]})) || {
          echo "Invalid selection: $token" >&2
          return 1
        }
        candidate=${choices[$((token - 1))]}
        duplicate=0
        for selection in "${selected[@]}"; do
          [[ "$selection" != "$candidate" ]] || duplicate=1
        done
        [[ $duplicate -eq 1 ]] || selected[${#selected[@]}]="$candidate"
      done
    fi
  fi

  echo
  echo 'Selected for permanent deletion:'
  printf '  %q\n' "${selected[@]}"
  echo 'This includes each contained Wine prefix, local Steam session, and local save data.'
  if [[ $ASSUME_YES -ne 1 ]] && ! yes_no 'Delete all selected installations permanently?' no; then
    echo 'Cancelled.'
    return 0
  fi

  if "$PGREP_COMMAND" -u "$UID" \
      -f '[Ss]team\.exe|steamwebhelper\.exe|steamservice\.exe|Pioneers of Pagonia\.exe|[/]wineserver' \
      >/dev/null; then
    echo 'ERROR: Exit all Wine, Steam, and Pagonia processes before deletion.' >&2
    return 1
  fi
  for candidate in "${selected[@]}"; do
    choice_index=''
    for index in "${!choices[@]}"; do
      [[ "${choices[$index]}" != "$candidate" ]] || choice_index=$index
    done
    [[ -n "$choice_index" ]] || {
      echo "ERROR: Selected path disappeared from discovery set: $candidate" >&2
      return 1
    }
    delete_one_pagonia_installation "$candidate" \
      "${choice_devices[$choice_index]}" "${choice_inodes[$choice_index]}"
  done
}

if [[ $DELETE_MODE -eq 1 ]]; then
  delete_pagonia_installation
  SUCCESS=1
  exit 0
fi

echo 'Pagonia installer preflight:'
echo '  1/7 Verifying tracked manifests...'
# GPTK requires the user's Apple download. Wine and Wineskin are bundled next
# to this script and must match the pinned archive hashes exactly.
require_hash "$GPTK_HASH_MANIFEST" "$EXPECTED_GPTK_HASH_MANIFEST"
require_hash "$GPTK_LINK_MANIFEST" "$EXPECTED_GPTK_LINK_MANIFEST"
require_hash "$GAME_HASH_MANIFEST" "$EXPECTED_GAME_HASH_MANIFEST"
for helper in "$STEAM_SESSION_HELPER" "$STEAM_LOGIN_LOG_HELPER" \
    "$STEAM_WINDOW_HELPER" "$BOUNDED_COMMAND_HELPER"; do
  require_file "$helper"
  python3 - "$helper" <<'PY'
from pathlib import Path
import sys
compile(Path(sys.argv[1]).read_bytes(), sys.argv[1], 'exec')
PY
done
echo '  2/7 Verifying the Wineskin archive...'
require_hash "$WRAPPER_ARCHIVE" "$EXPECTED_WRAPPER_ARCHIVE"
verify_archive_layout "$WRAPPER_ARCHIVE" 'Wineskin-3.0.6-2.app' 300000000
echo '  3/7 Verifying the Wine 10 gameplay runtime...'
require_hash "$ENGINE_ARCHIVE" "$EXPECTED_ENGINE_ARCHIVE"
verify_archive_layout "$ENGINE_ARCHIVE" 'wswine.bundle' 900000000
echo '  4/7 Verifying the Wine 11.17 Steam downloader runtime...'
require_hash "$DOWNLOADER_ARCHIVE" "$EXPECTED_DOWNLOADER_ARCHIVE"
verify_archive_layout "$DOWNLOADER_ARCHIVE" 'steam-wine11.bundle' 1500000000
echo '  5/7 Locating the read-only GPTK 4.0 beta 3 volume...'
resolve_gptk_lib
echo '  6/7 Verifying every GPTK file, symlink, and Apple signature...'
verify_gptk_lib "$GPTK_LIB"
echo '  7/7 Runtime inputs are pinned and structurally valid.'
echo 'Preflight verification complete.'

if [[ -n "$RESUME_ROOT" ]]; then
  resume_pagonia_staging "$RESUME_ROOT"
elif [[ $FORCE_FRESH -eq 0 ]] && steam_processes_running; then
  ACTIVE_STAGING=()
  while IFS= read -r active_root; do
    [[ -z "$active_root" ]] || ACTIVE_STAGING[${#ACTIVE_STAGING[@]}]="$active_root"
  done < <(find_active_pagonia_staging)
  if [[ ${#ACTIVE_STAGING[@]} -eq 1 ]]; then
    echo 'Detected Steam from an interrupted split-runtime download; resuming it automatically.'
    resume_pagonia_staging "${ACTIVE_STAGING[0]}"
  fi
fi
if [[ -z "$DOWNLOADER_SOURCE_PREFIX" && -z "$RESUME_ROOT" \
      && -z "$SOURCE_PREFIX" && $FORCE_FRESH -eq 0 ]]; then
  DORMANT_STAGING=()
  while IFS= read -r dormant_root; do
    [[ -z "$dormant_root" ]] || DORMANT_STAGING[${#DORMANT_STAGING[@]}]="$dormant_root"
  done < <(find_resumable_downloader_staging)
  if [[ ${#DORMANT_STAGING[@]} -eq 1 ]]; then
    echo 'Detected a dormant interrupted downloader; resuming it automatically.'
    resume_pagonia_staging "${DORMANT_STAGING[0]}"
  elif [[ ${#DORMANT_STAGING[@]} -gt 1 ]]; then
    echo 'ERROR: Multiple dormant downloader deployments exist; use --resume PATH.' >&2
    printf '  %s\n' "${DORMANT_STAGING[@]}" >&2
    exit 1
  fi
fi
stop_if_running

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
    exit 2
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
      exit 2
    fi
  fi
fi

cat <<EOF

Deployment plan
  Gameplay Wine: $ENGINE_ARCHIVE
  Downloader:    $DOWNLOADER_ARCHIVE
  Wineskin:      $WRAPPER_ARCHIVE
  Prefix mode:   $([[ $REUSE_PREFIX -eq 1 ]] && echo "reuse $SOURCE_PREFIX" || echo 'split Wine 11.17 download -> Wine 10 gameplay')
  GPTK library:  $GPTK_LIB
  Destination:   $DESTINATION
  Game build:    $EXPECTED_BUILD_ID
  Steam options: $LAUNCH_OPTIONS
  Launch test:   $([[ $LAUNCH_TEST -eq 1 ]] && echo enabled || echo disabled)
EOF
if [[ $ASSUME_YES -ne 1 ]] && ! yes_no 'Continue?' no; then
  echo 'Cancelled.'
  exit 2
fi

echo 'Preparing a private staging area...'
WORK_ROOT=$(mktemp -d '/private/tmp/Pagonia-GPTK4b3-deployment.XXXXXX')
chmod 700 "$WORK_ROOT"
CLEAN_STEAM_SNAPSHOT="$WORK_ROOT/clean-steam-client"
STEAM_SESSION_SNAPSHOT="$WORK_ROOT/steam-login-session"
STAGING="$WORK_ROOT/Pioneers of Pagonia.app"
mkdir -m 700 "$STAGING"
INPUT_SNAPSHOT="$WORK_ROOT/verified-inputs"
ENGINE_EXTRACT=$(mktemp -d "$WORK_ROOT/engine.XXXXXX")
mkdir -m 700 "$INPUT_SNAPSHOT"
echo '  Copying verified runtime inputs into private staging...'
cp -p "$WRAPPER_ARCHIVE" "$INPUT_SNAPSHOT/$WRAPPER_ARCHIVE_NAME"
cp -p "$ENGINE_ARCHIVE" "$INPUT_SNAPSHOT/$ENGINE_ARCHIVE_NAME"
cp -p "$GAME_HASH_MANIFEST" "$INPUT_SNAPSHOT/$GAME_HASH_MANIFEST_NAME"
if [[ $REUSE_PREFIX -eq 0 ]]; then
  cp -p "$DOWNLOADER_ARCHIVE" "$INPUT_SNAPSHOT/$DOWNLOADER_ARCHIVE_NAME"
fi
echo '  Re-verifying the private runtime snapshots...'
require_hash "$INPUT_SNAPSHOT/$WRAPPER_ARCHIVE_NAME" "$EXPECTED_WRAPPER_ARCHIVE"
require_hash "$INPUT_SNAPSHOT/$ENGINE_ARCHIVE_NAME" "$EXPECTED_ENGINE_ARCHIVE"
require_hash "$INPUT_SNAPSHOT/$GAME_HASH_MANIFEST_NAME" "$EXPECTED_GAME_HASH_MANIFEST"
if [[ $REUSE_PREFIX -eq 0 ]]; then
  require_hash "$INPUT_SNAPSHOT/$DOWNLOADER_ARCHIVE_NAME" "$EXPECTED_DOWNLOADER_ARCHIVE"
  verify_archive_layout "$INPUT_SNAPSHOT/$DOWNLOADER_ARCHIVE_NAME" \
    'steam-wine11.bundle' 1500000000
fi
verify_archive_layout "$INPUT_SNAPSHOT/$WRAPPER_ARCHIVE_NAME" \
  'Wineskin-3.0.6-2.app' 300000000
verify_archive_layout "$INPUT_SNAPSHOT/$ENGINE_ARCHIVE_NAME" \
  'wswine.bundle' 900000000

printf '%s\n' '1/7 Extracting the verified Wineskin and Wine runtime...'
tar -x --strip-components 1 -f "$INPUT_SNAPSHOT/$WRAPPER_ARCHIVE_NAME" -C "$STAGING"
tar -xf "$INPUT_SNAPSHOT/$ENGINE_ARCHIVE_NAME" -C "$ENGINE_EXTRACT"
ditto "$ENGINE_EXTRACT/wswine.bundle" "$STAGING/Contents/SharedSupport/wine"
DOWNLOADER_APP=''
if [[ $REUSE_PREFIX -eq 0 && -z "$DOWNLOADER_SOURCE_PREFIX" ]]; then
  DOWNLOADER_APP="$WORK_ROOT/Steam Downloader.app"
  mkdir -m 700 "$DOWNLOADER_APP"
  tar -x --strip-components 1 -f "$INPUT_SNAPSHOT/$WRAPPER_ARCHIVE_NAME" \
    -C "$DOWNLOADER_APP"
  DOWNLOADER_EXTRACT=$(mktemp -d "$WORK_ROOT/downloader-engine.XXXXXX")
  tar -xf "$INPUT_SNAPSHOT/$DOWNLOADER_ARCHIVE_NAME" -C "$DOWNLOADER_EXTRACT"
  ditto "$DOWNLOADER_EXTRACT/steam-wine11.bundle/Wine" \
    "$DOWNLOADER_APP/Contents/SharedSupport/wine"
  ditto "$DOWNLOADER_EXTRACT/steam-wine11.bundle/DXVK" \
    "$DOWNLOADER_APP/Contents/SharedSupport/dxvk"
  rm -rf "$DOWNLOADER_EXTRACT"
  rm -rf "$DOWNLOADER_APP/Contents/SharedSupport/prefix"
  mkdir -p "$DOWNLOADER_APP/Contents/SharedSupport/prefix/drive_c"
  validate_downloader_runtime "$DOWNLOADER_APP/Contents/SharedSupport/wine"
fi
mv "$INPUT_SNAPSHOT/$GAME_HASH_MANIFEST_NAME" "$WORK_ROOT/$GAME_HASH_MANIFEST_NAME"
GAME_HASH_MANIFEST="$WORK_ROOT/$GAME_HASH_MANIFEST_NAME"
if [[ $REUSE_PREFIX -eq 0 ]]; then
  mv "$INPUT_SNAPSHOT/$DOWNLOADER_ARCHIVE_NAME" \
    "$WORK_ROOT/$DOWNLOADER_ARCHIVE_NAME"
fi
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
  printf '%s\n' '4/7 Running the isolated Wine 11.17 downloader...'
  echo '  Downloading the pinned official SteamSetup.exe...'
  STEAM_SETUP_DOWNLOAD=$(mktemp '/tmp/PagoniaSteamSetup.XXXXXX')
  curl --fail --location --show-error \
    --proto '=https' --proto-redir '=https' \
    --output "$STEAM_SETUP_DOWNLOAD" "$STEAM_INSTALLER_URL"
  require_hash "$STEAM_SETUP_DOWNLOAD" "$EXPECTED_STEAM_SETUP"

  if [[ -z "$DOWNLOADER_SOURCE_PREFIX" ]]; then
    DOWNLOADER_PREFIX="$DOWNLOADER_APP/Contents/SharedSupport/prefix"
    DOWNLOADER_WINE="$DOWNLOADER_APP/Contents/SharedSupport/wine"
    DOWNLOADER_STEAM="$DOWNLOADER_PREFIX/drive_c/Program Files (x86)/Steam"
    DOWNLOADER_PLIST="$DOWNLOADER_APP/Contents/Info.plist"
    plutil -replace CFBundleName -string 'Pagonia Steam Downloader' "$DOWNLOADER_PLIST"
    plutil -replace CFBundleDisplayName -string 'Pagonia Steam Downloader' "$DOWNLOADER_PLIST"
    plutil -replace CFBundleIdentifier -string 'com.soad1337.pagonia.steam-downloader' "$DOWNLOADER_PLIST"
    plutil -replace 'Debug Mode' -bool true "$DOWNLOADER_PLIST"
    plutil -replace 'Symlinks In User Folder' -bool false "$DOWNLOADER_PLIST"
    echo '  Installing Steam only in the private Wine 11.17 prefix...'
    install_steam_in_prefix "$DOWNLOADER_APP" "$DOWNLOADER_PREFIX" \
      "$DOWNLOADER_WINE" "$DOWNLOADER_STEAM" "$DOWNLOADER_PLIST" \
      "$STEAM_SETUP_DOWNLOAD"
    deploy_downloader_graphics "$DOWNLOADER_PREFIX" "$DOWNLOADER_WINE"
    echo 'Opening the Wine 11.17 Steam downloader using normal macOS DNS.'
    echo 'ACTION REQUIRED: Sign in, complete Steam Guard, and install Pioneers of Pagonia.'
    launch_steam_ui "$DOWNLOADER_APP" "$DOWNLOADER_PREFIX" \
      "$DOWNLOADER_WINE" "$DOWNLOADER_STEAM"
    wait_for_steam_authentication "$DOWNLOADER_STEAM"
    request_pagonia_install "$DOWNLOADER_APP" "$DOWNLOADER_PREFIX" \
      "$DOWNLOADER_WINE" "$DOWNLOADER_STEAM"
    GAME_MANIFEST="$DOWNLOADER_STEAM/steamapps/appmanifest_2155180.acf"
    GAME_DOWNLOAD_COMPLETE=0
    for attempt in $(jot 10800); do
      STATE=''; BUILD=''
      if [[ -f "$GAME_MANIFEST" ]]; then
        STATE=$(awk -F'"' '/"StateFlags"/{print $4; exit}' "$GAME_MANIFEST" 2>/dev/null || true)
        BUILD=$(awk -F'"' '/"buildid"/{print $4; exit}' "$GAME_MANIFEST" 2>/dev/null || true)
        if [[ "$STATE" == '4' && "$BUILD" == "$EXPECTED_BUILD_ID" ]]; then
          GAME_DOWNLOAD_COMPLETE=1
          break
        fi
      fi
      ((attempt % 15 != 0)) || echo "  Waiting for download: StateFlags=${STATE:-missing}, build=${BUILD:-missing}"
      "$SLEEP_COMMAND" 2
    done
    [[ $GAME_DOWNLOAD_COMPLETE -eq 1 ]] || {
      echo "ERROR: Pagonia did not complete as build $EXPECTED_BUILD_ID." >&2
      exit 1
    }
    stop_wine_prefix "$DOWNLOADER_PREFIX" "$DOWNLOADER_WINE"
    validate_downloaded_depot "$DOWNLOADER_PREFIX"
    DOWNLOADER_SOURCE_PREFIX=$DOWNLOADER_PREFIX
  else
    validate_downloaded_depot "$DOWNLOADER_SOURCE_PREFIX"
  fi

  echo '  Capturing the authenticated Steam session for the Wine 10 prefix...'
  create_steam_session_snapshot "$DOWNLOADER_SOURCE_PREFIX" \
    "$STEAM_SESSION_SNAPSHOT"
  STEAM_SESSION_ID=$(python3 "$STEAM_SESSION_HELPER" steam-id \
    "$STEAM_SESSION_SNAPSHOT")

  # Create the transferable client only after the authenticated downloader has
  # stopped. Extract another verified runtime so neither its prefix nor any
  # loadable Wine library was exposed to the authenticated Steam process.
  SEED_RUNTIME_EXTRACT=$(mktemp -d "$WORK_ROOT/seed-runtime.XXXXXX")
  require_hash "$WORK_ROOT/$DOWNLOADER_ARCHIVE_NAME" "$EXPECTED_DOWNLOADER_ARCHIVE"
  tar -xf "$WORK_ROOT/$DOWNLOADER_ARCHIVE_NAME" -C "$SEED_RUNTIME_EXTRACT"
  SEED_RUNTIME_LAYOUT=$(mktemp -d "$WORK_ROOT/seed-layout.XXXXXX")
  ditto "$SEED_RUNTIME_EXTRACT/steam-wine11.bundle/Wine" \
    "$SEED_RUNTIME_LAYOUT/wine"
  ditto "$SEED_RUNTIME_EXTRACT/steam-wine11.bundle/DXVK" \
    "$SEED_RUNTIME_LAYOUT/dxvk"
  SEED_WINE="$SEED_RUNTIME_LAYOUT/wine"
  validate_downloader_runtime "$SEED_WINE"
  SEED_PREFIX="$WORK_ROOT/Steam Seed.app/Contents/SharedSupport/prefix"
  mkdir -p "$SEED_PREFIX/drive_c"
  install_clean_steam_seed "$SEED_PREFIX" "$SEED_WINE" \
    "$STEAM_SETUP_DOWNLOAD" "$CLEAN_STEAM_SNAPSHOT"
  rm -rf "$WORK_ROOT/Steam Seed.app" "$SEED_RUNTIME_EXTRACT" \
    "$SEED_RUNTIME_LAYOUT"
  SEED_PREFIX=''
  SEED_WINE=''
  validate_clean_steam_snapshot "$CLEAN_STEAM_SNAPSHOT"
  if steam_processes_running; then
    echo 'ERROR: Downloader Wine processes remain active; refusing cross-runtime import.' >&2
    exit 1
  fi
  echo '  Installing the clean pre-login Steam snapshot in the Wine 10 gameplay prefix...'
  install_clean_steam_snapshot "$CLEAN_STEAM_SNAPSHOT" "$PFX" \
    "$WINE_ROOT" "$STEAM" "$PLIST"
  rm -rf "$CLEAN_STEAM_SNAPSHOT"
  install_steam_session_snapshot "$STEAM_SESSION_SNAPSHOT" "$STEAM"
  [[ "$STEAM_SESSION_ID" == "$(python3 "$STEAM_SESSION_HELPER" steam-id \
    "$STEAM_SESSION_SNAPSHOT")" ]] || {
    echo 'ERROR: Steam session identity changed during transfer.' >&2
    exit 1
  }
  verify_transferred_steam_login "$PFX" "$WINE_ROOT" "$STEAM" \
    "$STEAM_SESSION_ID"
  rm -rf "$STEAM_SESSION_SNAPSHOT"
  STEAM_SESSION_SNAPSHOT=''
  rm -f "$STEAM_SETUP_DOWNLOAD"
  STEAM_SETUP_DOWNLOAD=''
  echo '  Selectively importing only the 856 hash-pinned game files and appmanifest...'
  import_validated_depot "$DOWNLOADER_SOURCE_PREFIX" "$PFX" \
    "$STEAM_SESSION_ID"
  validate_downloaded_depot "$PFX"
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
python3 - "$PFX/system.reg" "$PFX/user.reg" "$STEAM" "$LAUNCH_OPTIONS" "$REUSE_PREFIX" <<'PY'
from pathlib import Path
import re
import sys

system_path, user_path, steam_path = map(Path, sys.argv[1:4])
launch_options = sys.argv[4]
require_localconfig = sys.argv[5] == '1'

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
if require_localconfig and not localconfigs:
    raise SystemExit('No Steam user localconfig.vdf found in reused prefix')
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
FINAL_STEAM_FLAGS='-cef-disable-gpu -no-cef-sandbox -applaunch 2155180'
if [[ $REUSE_PREFIX -eq 0 ]]; then
  FINAL_STEAM_FLAGS="$FINAL_STEAM_FLAGS $LAUNCH_OPTIONS"
fi
plutil -replace 'Program Flags' -string "$FINAL_STEAM_FLAGS" "$PLIST"

# Do not copy downloader appcache artwork into the gameplay prefix. The wrapper
# icon is local, immutable packaging input and keeps the transfer allow-list
# limited to game-manifest files plus the validated appmanifest.
cp -p "$APP/Contents/Resources/Wineskin.icns" \
  "$APP/Contents/Resources/Pagonia.icns"
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
[[ "$(plutil -extract 'Program Flags' raw "$PLIST")" == "$FINAL_STEAM_FLAGS" ]]
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
shopt -s nullglob
LOCALCONFIGS=("$STEAM"/userdata/*/config/localconfig.vdf)
shopt -u nullglob
[[ ${#LOCALCONFIGS[@]} -gt 0 ]] || {
  echo 'ERROR: Final Steam prefix has no account localconfig.vdf.' >&2
  exit 1
}
for localconfig in "${LOCALCONFIGS[@]}"; do
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
Prefix isolation: $([[ $REUSE_PREFIX -eq 1 ]] && echo 'trusted source-prefix snapshot' || echo 'Wine 11.17 downloader -> validated selective import -> Wine 10 gameplay')
EOF

if [[ -n "$DOWNLOADER_APP" ]]; then
  [[ "$DOWNLOADER_APP" == "$WORK_ROOT/Steam Downloader.app" \
     && -d "$DOWNLOADER_APP" && ! -L "$DOWNLOADER_APP" ]] || {
    echo 'ERROR: Unexpected downloader staging path.' >&2
    exit 1
  }
  # Keep the validated downloader until atomic publication succeeds. The
  # private work root is removed immediately after publication.
fi

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
# The atomic rename transaction is complete. Restore signal handling before
# deleting the potentially large private downloader tree.
trap on_signal INT TERM
/bin/rm -x -rf "$WORK_ROOT"
WORK_ROOT=''
DOWNLOADER_APP=''
if ! same_identity "$DESTINATION" "$PUBLISHED_DEVICE" "$PUBLISHED_INODE"; then
  trap on_signal INT TERM
  echo 'ERROR: Published application identity changed during publication.' >&2
  exit 1
fi
BACKUP_MOVED=0
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
remove_stale_wineskin_lock "$DESTINATION"
"$OPEN_COMMAND" -n "$DESTINATION"
echo
echo 'Pioneers of Pagonia is starting through its new application icon.'
echo 'The transferred Steam login was verified before publication.'
echo 'The installer is waiting up to fifteen minutes for the verified game launch.'

GAME_COMMAND=''
for _ in $(jot 450); do
  GAME_COMMAND=$(ps -U "$UID" -o command= \
    | grep '[P]ioneers of Pagonia.exe' | head -1 || true)
  [[ -n "$GAME_COMMAND" ]] && break
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
