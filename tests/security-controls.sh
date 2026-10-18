#!/bin/bash
# Exercise installer rejection paths with local fixtures.

set -euo pipefail

ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd -P)
INSTALLER="$ROOT/scripts/install-pagonia-gptk4b3.sh"
REAL_GPTK='/Volumes/Evaluation environment for Windows games 4.0 beta 3/redist/lib'
WORK=$(mktemp -d /tmp/PagoniaSecurityControls.XXXXXX)
DMG="$WORK/fake-gptk.dmg"
MOUNT=''

cleanup() {
  local status=$?
  if [[ -n "$MOUNT" ]]; then
    diskutil unmount force "$MOUNT" >/dev/null 2>&1 || true
  fi
  rm -rf "$WORK"
  return "$status"
}
on_signal() { exit 130; }
trap cleanup EXIT
trap on_signal INT TERM

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

# External prefix import was removed and must remain unsupported.
if "$INSTALLER" --yes --no-launch --source-prefix "$WORK/prefix" \
    >"$WORK/source-prefix.log" 2>&1; then
  echo 'Removed --source-prefix option was accepted.' >&2
  exit 1
fi
grep -q 'Unknown option: --source-prefix' "$WORK/source-prefix.log"

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
