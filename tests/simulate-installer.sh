#!/bin/bash
# Simulate the non-human portions of a fresh Pagonia installation.
# This does not authenticate to Steam or download a licensed game depot.

set -euo pipefail

ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd -P)
INSTALLER="$ROOT/scripts/install-pagonia-gptk4b3.sh"
FIXTURE_PREFIX=${PAGONIA_SIM_PREFIX:?Set PAGONIA_SIM_PREFIX to an explicit disposable test fixture}
DESTINATION=${PAGONIA_SIM_DESTINATION:-'/Applications/Pagonia Installer Simulation.app'}
MOCK_DIR=$(mktemp -d /tmp/PagoniaInstallerMocks.XXXXXX)
PGREP_STATE="$MOCK_DIR/pgrep-state"
LOG="$MOCK_DIR/installer.log"
SIM_DEVICE=''
SIM_INODE=''

cleanup() {
  local status=$?
  if [[ -n "$SIM_DEVICE" && -n "$SIM_INODE" \
        && -d "$DESTINATION" && ! -L "$DESTINATION" \
        && "$(stat -f '%d' "$DESTINATION")" == "$SIM_DEVICE" \
        && "$(stat -f '%i' "$DESTINATION")" == "$SIM_INODE" ]]; then
    wine="$DESTINATION/Contents/SharedSupport/wine/bin/wineserver"
    prefix="$DESTINATION/Contents/SharedSupport/prefix"
    [[ ! -x "$wine" ]] || WINEPREFIX="$prefix" "$wine" -k 2>/dev/null || true
    rm -rf "$DESTINATION"
  elif [[ -e "$DESTINATION" ]]; then
    echo "Refusing to remove changed simulation destination: $DESTINATION" >&2
  fi
  if [[ $status -ne 0 && -f "$LOG" ]]; then
    cp -p "$LOG" /tmp/pagonia-installer-simulation-failure.log
    echo 'Simulation log preserved: /tmp/pagonia-installer-simulation-failure.log' >&2
  fi
  rm -rf "$MOCK_DIR"
  return "$status"
}
on_signal() { exit 130; }
trap cleanup EXIT
trap on_signal INT TERM

[[ -x "$INSTALLER" ]] || { echo "Missing installer: $INSTALLER" >&2; exit 1; }
[[ -d "$FIXTURE_PREFIX" ]] || {
  echo "Missing simulation fixture prefix: $FIXTURE_PREFIX" >&2
  exit 1
}
[[ ! -e "$DESTINATION" ]] || {
  echo "Simulation destination already exists: $DESTINATION" >&2
  exit 1
}

cat >"$MOCK_DIR/pgrep" <<'EOF'
#!/bin/bash
set -euo pipefail
state=${PAGONIA_SIM_PGREP_STATE:?}
if [[ " $* " == *' SteamSetup\.exe '* ]]; then
  if [[ ! -e "$state" ]]; then
    : >"$state"
    exit 0
  fi
fi
exit 1
EOF

cat >"$MOCK_DIR/sleep" <<'EOF'
#!/bin/bash
exit 0
EOF

cat >"$MOCK_DIR/open" <<'EOF'
#!/bin/bash
set -euo pipefail
app=${!#}
[[ "$app" == *.app && -d "$app" ]] || exit 0
plist="$app/Contents/Info.plist"
program=$(/usr/bin/plutil -extract 'Program Name and Path' raw "$plist" 2>/dev/null || true)
if [[ "$program" == '/SteamSetup.exe' ]]; then
  target="$app/Contents/SharedSupport/prefix"
  /usr/bin/ditto "${PAGONIA_SIM_PREFIX:?}" "$target"
  # Preserve the installer artifact that the real Steam setup would consume.
  [[ -f "$target/drive_c/SteamSetup.exe" ]] || : >"$target/drive_c/SteamSetup.exe"
fi
EOF
chmod 700 "$MOCK_DIR/pgrep" "$MOCK_DIR/sleep" "$MOCK_DIR/open"

# Negative check: publication below a world-writable parent must fail.
if "$INSTALLER" --yes --no-launch \
    --destination '/tmp/Pagonia Unsafe Simulation.app' \
    >"$MOCK_DIR/unsafe-destination.log" 2>&1; then
  echo 'Unsafe destination test unexpectedly succeeded.' >&2
  exit 1
fi
grep -Eq 'Destination parent must not (contain symbolic links|be world-writable)' \
  "$MOCK_DIR/unsafe-destination.log"

# Full control-flow simulation of the fresh branch. The open(1) mock injects a
# known local fixture only after the real, pinned SteamSetup download succeeds.
PAGONIA_SIM_PREFIX="$FIXTURE_PREFIX" \
PAGONIA_SIM_PGREP_STATE="$PGREP_STATE" \
PAGONIA_OPEN_COMMAND="$MOCK_DIR/open" \
PAGONIA_PGREP_COMMAND="$MOCK_DIR/pgrep" \
PAGONIA_SLEEP_COMMAND="$MOCK_DIR/sleep" \
  "$INSTALLER" --fresh --yes --no-launch --destination "$DESTINATION" \
  >"$LOG" 2>&1

SIM_DEVICE=$(stat -f '%d' "$DESTINATION")
SIM_INODE=$(stat -f '%i' "$DESTINATION")
grep -q "Deployment installed: $DESTINATION" "$LOG"
grep -q 'Launch test skipped' "$LOG"

plist="$DESTINATION/Contents/Info.plist"
[[ "$(/usr/bin/plutil -extract 'Program Name and Path' raw "$plist")" \
   == '/Program Files (x86)/Steam/steam.exe' ]]
[[ "$(/usr/bin/plutil -extract 'Program Flags' raw "$plist")" \
   == '-applaunch 2155180' ]]
[[ "$(/usr/bin/plutil -extract WINEESYNC raw "$plist")" == '0' ]]
[[ "$(/usr/bin/plutil -extract WINEMSYNC raw "$plist")" == '0' ]]
[[ "$(/usr/bin/plutil -extract WINEFSYNC raw "$plist")" == '0' ]]

scripts="$DESTINATION/Contents/Resources/Scripts"
[[ -x "$scripts/PagoniaFinalizer" && ! -L "$scripts/PagoniaFinalizer" ]]
cmp -s "$ROOT/scripts/PagoniaFinalizer" "$scripts/PagoniaFinalizer"
grep -q 'PagoniaFinalizer.*watch' "$scripts/WineskinStartupScript"
grep -q 'PagoniaFinalizer.*quit' "$scripts/WineskinQuitScript"
grep -q 'PagoniaFinalizer.*quit' "$scripts/WineskinShutdownScript"

game="$DESTINATION/Contents/SharedSupport/prefix/drive_c/Program Files (x86)/Steam/steamapps/common/Pioneers of Pagonia"
system32="$DESTINATION/Contents/SharedSupport/prefix/drive_c/windows/system32"
[[ -f "$game/Pioneers of Pagonia.exe" ]]
[[ ! -e "$game/D3D12Core.dll" ]]
[[ "$(shasum -a 256 "$system32/dxgi.dll" | awk '{print $1}')" \
   == 'd53d9ea91935f0de126ba528264fc4c9b4dfea8bfe43f3f1256bd3e8963d67ee' ]]
[[ "$(shasum -a 256 "$system32/d3d12.dll" | awk '{print $1}')" \
   == '3174fac027d3ff10971645ac41b665cd53949c87d6d2d7d53b0073bf4bb36981' ]]
[[ "$(shasum -a 256 "$system32/d3d12core.dll" | awk '{print $1}')" \
   == 'b8cabb79a3f0a14babcbfd575cca70814e4d1d3e71606dfc1670421aaa39b97e' ]]

echo 'Fresh-install packaging/control-flow smoke test: PASS'
echo 'Simulated: SteamSetup lifecycle, sign-in-complete state, depot completion, configuration, and publication.'
echo 'Not simulated: Steam authentication, Steam Guard, license authorization, or network depot transfer.'
