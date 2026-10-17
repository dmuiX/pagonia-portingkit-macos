#!/bin/bash
# Exercise installer rejection paths with local fixtures.

set -euo pipefail

ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd -P)
INSTALLER="$ROOT/scripts/install-pagonia-gptk4b3.sh"
REAL_GPTK='/Volumes/Evaluation environment for Windows games 4.0 beta 3/redist/lib'
WORK=$(mktemp -d /tmp/PagoniaSecurityControls.XXXXXX)
WORK_DEVICE=$(stat -f '%d' "$WORK")
WORK_INODE=$(stat -f '%i' "$WORK")
DMG="$WORK/fake-gptk.dmg"
MOUNT=''
RESUME_DECOY=''
RESUME_TRAVERSAL_TEST_ROOT=''
RESUME_DECOY_DEVICE=''
RESUME_DECOY_INODE=''
RESUME_TRAVERSAL_DEVICE=''
RESUME_TRAVERSAL_INODE=''
LOCK_TEST="/private/tmp/Pagonia-GPTK4b3-installer-${UID}.lock"
LOCK_TEST_CREATED=0
LOCK_TEST_DEVICE=''
LOCK_TEST_INODE=''

remove_created_directory() {
  local path=$1 device=$2 inode=$3
  [[ -n "$path" && -n "$device" && -n "$inode" \
        && -d "$path" && ! -L "$path" \
        && "$(stat -f '%d' "$path")" == "$device" \
        && "$(stat -f '%i' "$path")" == "$inode" ]] || return 0
  rm -rf "$path"
}

cleanup() {
  local status=$?
  if [[ -n "$MOUNT" ]]; then
    diskutil unmount force "$MOUNT" >/dev/null 2>&1 || true
  fi
  remove_created_directory "$WORK" "$WORK_DEVICE" "$WORK_INODE"
  remove_created_directory "$RESUME_DECOY" "$RESUME_DECOY_DEVICE" \
    "$RESUME_DECOY_INODE"
  remove_created_directory "$RESUME_TRAVERSAL_TEST_ROOT" \
    "$RESUME_TRAVERSAL_DEVICE" "$RESUME_TRAVERSAL_INODE"
  if [[ $LOCK_TEST_CREATED -eq 1 && -d "$LOCK_TEST" && ! -L "$LOCK_TEST" \
        && "$(stat -f '%d' "$LOCK_TEST")" == "$LOCK_TEST_DEVICE" \
        && "$(stat -f '%i' "$LOCK_TEST")" == "$LOCK_TEST_INODE" ]]; then
    rm -f "$LOCK_TEST/pid"
    rmdir "$LOCK_TEST" 2>/dev/null || true
  fi
  return "$status"
}
on_signal() { exit 130; }
trap cleanup EXIT
trap on_signal INT TERM

# Deletion mode must list broad name matches and work without GPTK. Exact
# selection must preserve every bystander until it is selected separately.
DELETE_FIXTURE="$WORK/home/Applications/Pagonia Delete Control.app"
DELETE_BYSTANDER="$WORK/home/Applications/Pagonia Broad Match.app"
mkdir -p "$DELETE_FIXTURE/Contents/SharedSupport/wine/bin" \
  "$DELETE_FIXTURE/Contents/SharedSupport/prefix" "$DELETE_BYSTANDER/Contents"
printf '#!/bin/bash\ntouch %q\n' "$WORK/untrusted-wineserver-ran" \
  >"$DELETE_FIXTURE/Contents/SharedSupport/wine/bin/wineserver"
chmod +x "$DELETE_FIXTURE/Contents/SharedSupport/wine/bin/wineserver"
printf 'fixture\n' >"$DELETE_FIXTURE/Contents/fixture.txt"
printf 'bystander\n' >"$DELETE_BYSTANDER/Contents/fixture.txt"
DELETE_RESOLVED="$(cd "$(dirname "$DELETE_FIXTURE")" && pwd -P)/$(basename "$DELETE_FIXTURE")"
HOME="$WORK/home" "$INSTALLER" --delete --yes --destination "$DELETE_RESOLVED" \
  >"$WORK/delete.log" 2>&1
[[ ! -e "$DELETE_FIXTURE" && -e "$DELETE_BYSTANDER" \
   && ! -e "$WORK/untrusted-wineserver-ran" ]]
grep -q 'Additional possible Pagonia paths' "$WORK/delete.log"
grep -Fq "Deleted: $DELETE_RESOLVED" "$WORK/delete.log"
DELETE_BYSTANDER_RESOLVED="$(cd "$(dirname "$DELETE_BYSTANDER")" && pwd -P)/$(basename "$DELETE_BYSTANDER")"
HOME="$WORK/home" "$INSTALLER" --delete --yes \
  --destination "$DELETE_BYSTANDER_RESOLVED" >"$WORK/delete-bystander.log" 2>&1
[[ ! -e "$DELETE_BYSTANDER" ]]
grep -Fq "Deleted: $DELETE_BYSTANDER_RESOLVED" "$WORK/delete-bystander.log"

# A second process must never reclaim the empty initialization window between
# another installer's atomic mkdir and PID write.
[[ ! -e "$LOCK_TEST" ]] || {
  echo "Installer lock already exists before concurrency control: $LOCK_TEST" >&2
  exit 1
}
mkdir -m 700 "$LOCK_TEST"
LOCK_TEST_DEVICE=$(stat -f '%d' "$LOCK_TEST")
LOCK_TEST_INODE=$(stat -f '%i' "$LOCK_TEST")
LOCK_TEST_CREATED=1
if HOME="$WORK/home" "$INSTALLER" --delete \
    >"$WORK/empty-lock.log" 2>&1; then
  echo 'Empty installer lock was reclaimed.' >&2
  exit 1
fi
grep -q 'refusing to race it' "$WORK/empty-lock.log"
[[ -d "$LOCK_TEST" && ! -e "$LOCK_TEST/pid" ]]
printf '%s\n' 999999 >"$LOCK_TEST/pid"
if HOME="$WORK/home" "$INSTALLER" --delete \
    >"$WORK/stale-lock.log" 2>&1; then
  echo 'Stale installer lock was reclaimed automatically.' >&2
  exit 1
fi
grep -q 'refusing automatic reclamation' "$WORK/stale-lock.log"
[[ "$(cat "$LOCK_TEST/pid")" == 999999 ]]
rm "$LOCK_TEST/pid"
rmdir "$LOCK_TEST"
LOCK_TEST_CREATED=0

# Resume must canonicalize before trusting or later deleting a staging path.
RESUME_DECOY="/private/tmp/Pagonia-GPTK4b3-deployment.SecurityControl$$"
RESUME_TRAVERSAL_TEST_ROOT="/private/tmp/Pagonia-GPTK4b3-deployment.SecurityTraversal$$"
mkdir -m 700 "$RESUME_DECOY" "$RESUME_TRAVERSAL_TEST_ROOT"
RESUME_DECOY_DEVICE=$(stat -f '%d' "$RESUME_DECOY")
RESUME_DECOY_INODE=$(stat -f '%i' "$RESUME_DECOY")
RESUME_TRAVERSAL_DEVICE=$(stat -f '%d' "$RESUME_TRAVERSAL_TEST_ROOT")
RESUME_TRAVERSAL_INODE=$(stat -f '%i' "$RESUME_TRAVERSAL_TEST_ROOT")
if "$INSTALLER" --resume "$RESUME_DECOY/../$(basename "$RESUME_TRAVERSAL_TEST_ROOT")" \
    >"$WORK/resume-traversal.log" 2>&1; then
  echo 'Non-direct resume path was accepted.' >&2
  exit 1
fi
[[ -d "$RESUME_TRAVERSAL_TEST_ROOT" ]]
remove_created_directory "$RESUME_DECOY" "$RESUME_DECOY_DEVICE" \
  "$RESUME_DECOY_INODE"
remove_created_directory "$RESUME_TRAVERSAL_TEST_ROOT" \
  "$RESUME_TRAVERSAL_DEVICE" "$RESUME_TRAVERSAL_INODE"
RESUME_DECOY=''
RESUME_TRAVERSAL_TEST_ROOT=''
grep -q 'Invalid resume path' "$WORK/resume-traversal.log"

[[ -d "$REAL_GPTK" ]] || {
  echo "Mount the genuine GPTK 4.0 beta 3 DMG first: $REAL_GPTK" >&2
  exit 1
}

# World-writable/symlinked destination parents must be rejected before work.
if "$INSTALLER" --yes --no-launch \
    --destination '/tmp/Pagonia Unsafe Security Test.app' \
    >"$WORK/unsafe-destination.log" 2>&1; then
  echo 'Unsafe destination was accepted.' >&2
  exit 1
fi
grep -Eq 'Destination parent must not (contain symbolic links|be world-writable)' \
  "$WORK/unsafe-destination.log"

# Critical paths in an explicitly supplied prefix must never be symlinks.
mkdir -p "$WORK/prefix"
ln -s /etc/hosts "$WORK/prefix/system.reg"
if "$INSTALLER" --yes --no-launch --source-prefix "$WORK/prefix" \
    --gptk-lib "$REAL_GPTK" \
    --destination '/Applications/Pagonia Prefix Rejection Test.app' \
    >"$WORK/prefix-symlink.log" 2>&1; then
  echo 'Prefix with a critical symlink was accepted.' >&2
  exit 1
fi
grep -q 'Critical prefix path is a symbolic link' "$WORK/prefix-symlink.log"

# A read-only DMG containing every genuine GPTK file plus one extra payload
# must fail the exact manifest check.
mkdir -p "$WORK/source/Evaluation environment for Windows games 4.0 beta 3/redist"
ditto "$REAL_GPTK" \
  "$WORK/source/Evaluation environment for Windows games 4.0 beta 3/redist/lib"
printf 'unexpected payload\n' > \
  "$WORK/source/Evaluation environment for Windows games 4.0 beta 3/redist/lib/wine/x86_64-windows/extra.dll"
hdiutil create -quiet \
  -srcfolder "$WORK/source/Evaluation environment for Windows games 4.0 beta 3" \
  -volname 'Pagonia GPTK Security Controls' -format UDZO "$DMG"
MOUNT=$(diskutil image attach --nobrowse --readOnly "$DMG" \
  | awk '/\/Volumes\//{sub(/^.*\/Volumes\//,"/Volumes/"); print; exit}')
FAKE_LIB="$MOUNT/redist/lib"
if "$INSTALLER" --yes --no-launch --gptk-lib "$FAKE_LIB" \
    --destination '/Applications/Pagonia GPTK Rejection Test.app' \
    >"$WORK/fake-gptk.log" 2>&1; then
  echo 'GPTK tree with an unexpected payload was accepted.' >&2
  exit 1
fi
grep -q 'GPTK file manifest mismatch' "$WORK/fake-gptk.log"

echo 'Security rejection controls: PASS'
