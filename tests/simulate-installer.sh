#!/bin/bash
# Simulate the non-human portions of a fresh Pagonia installation.
# This does not authenticate to Steam or download a licensed game depot.

set -euo pipefail

ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd -P)
INSTALLER="$ROOT/scripts/install-pagonia-gptk4b3.sh"
FIXTURE_PREFIX=${PAGONIA_SIM_PREFIX:-"$HOME/Games/Pagonia-GPTK4b3"}
DESTINATION=${PAGONIA_SIM_DESTINATION:-'/Applications/Pagonia Installer Simulation.app'}
RESUME_DESTINATION=${PAGONIA_SIM_RESUME_DESTINATION:-'/Applications/Pagonia Resume Simulation.app'}
RESUME_ROOT="/private/tmp/Pagonia-GPTK4b3-deployment.ResumeSimulation$$"
MOCK_DIR=$(mktemp -d /tmp/PagoniaInstallerMocks.XXXXXX)
MOCK_DEVICE=$(stat -f '%d' "$MOCK_DIR")
MOCK_INODE=$(stat -f '%i' "$MOCK_DIR")
PGREP_STATE="$MOCK_DIR/pgrep-state"
STEAM_UI_STATE="$MOCK_DIR/steam-ui-state"
WINE_CALLS="$MOCK_DIR/wine-calls"
WINDOW_CHECK_STATE="$MOCK_DIR/window-check-state"
RESUME_PGREP_STATE="$MOCK_DIR/resume-pgrep-state"
RESUME_STEAM_UI_STATE="$MOCK_DIR/resume-steam-ui-state"
RESUME_WINE_CALLS="$MOCK_DIR/resume-wine-calls"
RESUME_WINDOW_CHECK_STATE="$MOCK_DIR/resume-window-check-state"
LOG="$MOCK_DIR/installer.log"
SIM_DEVICE=''
SIM_INODE=''
RESUME_DEVICE=''
RESUME_INODE=''
RESUME_ROOT_DEVICE=''
RESUME_ROOT_INODE=''

cleanup() {
  local status=$?
  if [[ -n "$SIM_DEVICE" && -n "$SIM_INODE" \
        && -d "$DESTINATION" && ! -L "$DESTINATION" \
        && "$(stat -f '%d' "$DESTINATION")" == "$SIM_DEVICE" \
        && "$(stat -f '%i' "$DESTINATION")" == "$SIM_INODE" ]]; then
    rm -rf "$DESTINATION"
  elif [[ -e "$DESTINATION" ]]; then
    echo "Refusing to remove changed simulation destination: $DESTINATION" >&2
  fi
  if [[ -n "$RESUME_DEVICE" && -n "$RESUME_INODE" \
        && -d "$RESUME_DESTINATION" && ! -L "$RESUME_DESTINATION" \
        && "$(stat -f '%d' "$RESUME_DESTINATION")" == "$RESUME_DEVICE" \
        && "$(stat -f '%i' "$RESUME_DESTINATION")" == "$RESUME_INODE" ]]; then
    rm -rf "$RESUME_DESTINATION"
  elif [[ -e "$RESUME_DESTINATION" ]]; then
    echo "Refusing to remove changed resume destination: $RESUME_DESTINATION" >&2
  fi
  if [[ -n "$RESUME_ROOT_DEVICE" && -n "$RESUME_ROOT_INODE" \
        && -d "$RESUME_ROOT" && ! -L "$RESUME_ROOT" \
        && "$(stat -f '%d' "$RESUME_ROOT")" == "$RESUME_ROOT_DEVICE" \
        && "$(stat -f '%i' "$RESUME_ROOT")" == "$RESUME_ROOT_INODE" ]]; then
    rm -rf "$RESUME_ROOT"
  fi
  if [[ $status -ne 0 && -f "$LOG" ]]; then
    cp -p "$LOG" /tmp/pagonia-installer-simulation-failure.log
    echo 'Simulation log preserved: /tmp/pagonia-installer-simulation-failure.log' >&2
  fi
  if [[ -d "$MOCK_DIR" && ! -L "$MOCK_DIR" \
        && "$(stat -f '%d' "$MOCK_DIR")" == "$MOCK_DEVICE" \
        && "$(stat -f '%i' "$MOCK_DIR")" == "$MOCK_INODE" ]]; then
    rm -rf "$MOCK_DIR"
  else
    echo "Refusing to remove changed mock directory: $MOCK_DIR" >&2
  fi
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
[[ ! -e "$RESUME_DESTINATION" && ! -e "$RESUME_ROOT" ]] || {
  echo 'Resume simulation destination or staging already exists.' >&2
  exit 1
}

cat >"$MOCK_DIR/pgrep" <<'EOF'
#!/bin/bash
set -euo pipefail
state=${PAGONIA_SIM_PGREP_STATE:?}
ui_state=${PAGONIA_SIM_STEAM_UI_STATE:?}
if [[ " $* " == *' SteamSetup\.exe '* ]]; then
  if [[ -f "$state.setup-done" ]]; then
    /bin/rm -f "$state.setup-done"
    exit 1
  fi
  exit 0
elif [[ " $* " == *'steamwebhelper\.exe.*-+steamid=76561197987380524'* \
       && -e "$state.auth-ready" ]]; then
  exit 0
elif [[ " $* " == *'steamwebhelper\.exe'* && -e "$ui_state" ]]; then
  exit 0
fi
exit 1
EOF

cat >"$MOCK_DIR/sleep" <<'EOF'
#!/bin/bash
set -euo pipefail
state=${PAGONIA_SIM_PGREP_STATE:?}
if [[ -e "$state.auth-ready" && ! -e "$state.auth-completed" \
      && -f "$state.auth-log-path" ]]; then
  log=$(<"$state.auth-log-path")
  /usr/bin/printf '%s\n' \
    '[Logged On, 3, 0] [U:1:27114796] RecvMsgClientLogOnResponse() : processing complete' \
    >>"$log"
  : >"$state.auth-completed"
fi
exit 0
EOF

cat >"$MOCK_DIR/window-checker" <<'EOF'
#!/bin/bash
set -euo pipefail
state=${PAGONIA_SIM_WINDOW_CHECK_STATE:?}
if [[ ! -e "$state" ]]; then
  : >"$state"
  exit 1
fi
exit 0
EOF

cat >"$MOCK_DIR/wine-runner" <<'EOF'
#!/bin/bash
set -euo pipefail
prefix=$1
app=${prefix%/Contents/SharedSupport/prefix}
executable=$4
case "$(basename "$executable")" in
  SteamSetup.exe) program='/SteamSetup.exe' ;;
  steam.exe|Steam.exe) program='/Program Files (x86)/Steam/steam.exe' ;;
  wineboot) program='wineboot' ;;
  wineserver) program='wineserver' ;;
  steamservice.exe) program='steamservice' ;;
  *) exit 0 ;;
esac
/usr/bin/printf '%s\t%s\t%s\t%s\n' "$prefix" "$2" "$program" "${*:5}" \
  >>"${PAGONIA_SIM_WINE_CALLS:?}"
if [[ "$program" == 'steamservice' ]]; then
  :
elif [[ "$program" == 'wineserver' ]]; then
  /bin/rm -f "${PAGONIA_SIM_STEAM_UI_STATE:?}" \
    "${PAGONIA_SIM_PGREP_STATE:?}.auth-ready"
elif [[ "$program" == 'wineboot' ]]; then
  /bin/mkdir -p "$prefix/drive_c/windows/system32" "$prefix/drive_c/windows/syswow64"
  /usr/bin/printf '%s\n' 'WINE REGISTRY Version 2' >"$prefix/user.reg"
  /usr/bin/printf '%s\n' \
    'WINE REGISTRY Version 2' \
    '"CurrentBuild"="19043"' \
    '"CurrentBuildNumber"="19043"' >"$prefix/system.reg"
elif [[ "$program" == '/SteamSetup.exe' ]]; then
  target=$prefix
  if [[ "$app" == */'Steam Downloader.app' ]]; then
    /usr/bin/ditto "${PAGONIA_SIM_PREFIX:?}" "$target"
    /usr/bin/printf '%s\n' 'DOWNLOADER_REGISTRY_SENTINEL' >>"$target/system.reg"
    /bin/mkdir -p \
      "$target/drive_c/Program Files (x86)/Steam/config" \
      "$target/drive_c/Program Files (x86)/Steam/userdata/999/config" \
      "$target/drive_c/Program Files (x86)/Steam/appcache"
    /usr/bin/printf 'account sentinel\n' >"$target/downloader-account-sentinel"
    /usr/bin/printf 'config sentinel\n' >"$target/drive_c/Program Files (x86)/Steam/config/downloader-sentinel"
    /usr/bin/printf 'userdata sentinel\n' >"$target/drive_c/Program Files (x86)/Steam/userdata/999/config/downloader-sentinel"
    /usr/bin/printf 'cache sentinel\n' >"$target/drive_c/Program Files (x86)/Steam/appcache/downloader-sentinel"
    /usr/bin/printf 'extra depot sentinel\n' >"$target/drive_c/Program Files (x86)/Steam/steamapps/common/Pioneers of Pagonia/downloader-extra.txt"
    /usr/bin/printf 'root log sentinel\n' >"$target/drive_c/Program Files (x86)/Steam/unexpected-auth.log"
    /usr/bin/printf 'root config sentinel\n' >"$target/drive_c/Program Files (x86)/Steam/unexpected-auth.cfg"
    /usr/bin/printf 'root vdf sentinel\n' >"$target/drive_c/Program Files (x86)/Steam/unexpected-auth.vdf"
    /usr/bin/printf 'auth sentinel\n' >"$target/drive_c/Program Files (x86)/Steam/ssfn-unexpected"
    /bin/mkdir -p \
      "$target/drive_c/Program Files (x86)/Steam/future-depot-state" \
      "$target/drive_c/Program Files (x86)/Steam/clientui" \
      "$target/drive_c/Program Files (x86)/Steam/resource" \
      "$target/drive_c/Program Files (x86)/Steam/steam"
    /usr/bin/printf 'future depot sentinel\n' >"$target/drive_c/Program Files (x86)/Steam/future-depot-state/sentinel"
    /usr/bin/printf 'nested account sentinel\n' >"$target/drive_c/Program Files (x86)/Steam/clientui/account.cfg"
    /usr/bin/printf 'nested session sentinel\n' >"$target/drive_c/Program Files (x86)/Steam/resource/session.vdf"
    /usr/bin/printf 'nested depot sentinel\n' >"$target/drive_c/Program Files (x86)/Steam/steam/depot-state.json"
    /usr/bin/printf '%s\n' \
      '"users"' '{' \
      '  "76561197987380524"' '  {' \
      '    "AccountName" "fixture"' \
      '    "RememberPassword" "1"' \
      '    "MostRecent" "1"' \
      '    "AllowAutoLogin" "1"' \
      '  }' '}' >"$target/drive_c/Program Files (x86)/Steam/config/loginusers.vdf"
    /usr/bin/printf '%s\n' \
      '"InstallConfigStore"' '{' \
      '  "Software"' '  {' \
      '    "Valve"' '    {' \
      '      "Steam"' '      {' \
      '      }' '    }' '  }' '}' \
      >"$target/drive_c/Program Files (x86)/Steam/config/config.vdf"
    localconfig="$target/drive_c/Program Files (x86)/Steam/userdata/27114796/config/localconfig.vdf"
    /bin/mkdir -p "$(dirname "$localconfig")"
    /usr/bin/printf '%s\n' \
      '"UserLocalConfigStore"' '{' \
      '  "AuthData"' '  {' '    "fixture" "value"' '  }' \
      '  "SharedAuth"' '  {' '    "fixture" "value"' '  }' \
      '  "Software"' '  {' \
      '    "Valve"' '    {' \
      '      "Steam"' '      {' \
      '        "apps"' '        {' \
      '        }' '      }' '    }' '  }' '}' >"$localconfig"
  else
    # Model a clean Wine 11 seed installation. The snapshot builder must use
    # Steam's installed-package manifests rather than copying mutable state.
    /usr/bin/ditto "${PAGONIA_SIM_PREFIX:?}" "$target"
  fi
  [[ -f "$target/drive_c/SteamSetup.exe" ]] || : >"$target/drive_c/SteamSetup.exe"
  : >"${PAGONIA_SIM_PGREP_STATE:?}.setup-done"
elif [[ "$program" == '/Program Files (x86)/Steam/steam.exe' ]]; then
  logs="$app/Contents/SharedSupport/prefix/drive_c/Program Files (x86)/Steam/logs"
  /bin/mkdir -p "$logs"
  /usr/bin/printf '%s\n' \
    'PopupHTMLWindow: idx:131073 handle:65536' \
    'BrowserReady: handle:131073' >"$logs/steamui_html.txt"
  /usr/bin/printf '%s\n' 'Verification complete' >"$logs/bootstrap_log.txt"
  : >"${PAGONIA_SIM_STEAM_UI_STATE:?}"
  if [[ "$app" == */'Steam Downloader.app' ]]; then
    /usr/bin/printf '%s\n' \
      '[ WaitingForServerResponse ] Received logon success response' \
      '[ WaitingForLibraryReady ] SetLoginState: Success - OK' \
      >"$logs/steamui_login.txt"
  elif [[ "$app" == */'Pioneers of Pagonia.app' ]]; then
    loginusers="$prefix/drive_c/Program Files (x86)/Steam/config/loginusers.vdf"
    localconfig="$prefix/drive_c/Program Files (x86)/Steam/userdata/27114796/config/localconfig.vdf"
    grep -q '76561197987380524' "$loginusers"
    grep -q 'AuthData' "$localconfig"
    grep -q 'SharedAuth' "$localconfig"
    /usr/bin/printf '%s\n' \
      "[Logging On, 3, 0] [U:1:27114796] RecvMsgClientLogOnResponse() : [U:1:27114796] 'OK'" \
      >"$logs/connection_log.txt"
    /usr/bin/printf '%s\n' "$logs/connection_log.txt" \
      >"${PAGONIA_SIM_PGREP_STATE:?}.auth-log-path"
    /bin/rm -f "${PAGONIA_SIM_PGREP_STATE:?}.auth-completed"
    : >"${PAGONIA_SIM_PGREP_STATE:?}.auth-ready"
  fi
fi
EOF
chmod 700 "$MOCK_DIR/pgrep" "$MOCK_DIR/sleep" "$MOCK_DIR/window-checker" \
  "$MOCK_DIR/wine-runner"

# Negative check: publication below a world-writable parent must fail.
if "$INSTALLER" --yes --no-launch \
    --destination '/tmp/Pagonia Unsafe Simulation.app' \
    >"$MOCK_DIR/unsafe-destination.log" 2>&1; then
  echo 'Unsafe destination test unexpectedly succeeded.' >&2
  exit 1
fi
grep -Eq 'Destination parent must not (contain symbolic links|be world-writable)' \
  "$MOCK_DIR/unsafe-destination.log"

# Full control-flow simulation of the fresh branch. The Wine runner injects a
# known local fixture only after the real, pinned SteamSetup download succeeds.
PAGONIA_SIM_PREFIX="$FIXTURE_PREFIX" \
PAGONIA_SIM_PGREP_STATE="$PGREP_STATE" \
PAGONIA_SIM_STEAM_UI_STATE="$STEAM_UI_STATE" \
PAGONIA_SIM_WINE_CALLS="$WINE_CALLS" \
PAGONIA_TEST_MODE=1 \
PAGONIA_SIM_WINDOW_CHECK_STATE="$WINDOW_CHECK_STATE" \
PAGONIA_STEAM_WINDOW_CHECKER="$MOCK_DIR/window-checker" \
PAGONIA_WINE_RUNNER="$MOCK_DIR/wine-runner" \
PAGONIA_PGREP_COMMAND="$MOCK_DIR/pgrep" \
PAGONIA_SLEEP_COMMAND="$MOCK_DIR/sleep" \
  "$INSTALLER" --fresh --yes --no-launch --destination "$DESTINATION" \
  >"$LOG" 2>&1

SIM_DEVICE=$(stat -f '%d' "$DESTINATION")
SIM_INODE=$(stat -f '%i' "$DESTINATION")
grep -q "Deployment installed: $DESTINATION" "$LOG"
grep -q 'Launch test skipped' "$LOG"
grep -q 'Steam UI is visibly rendered.' "$LOG"
[[ $(grep -c 'Wine prefix shutdown confirmed:' "$LOG") -ge 3 ]]
[[ $(grep -c $'\t/SteamSetup.exe\t/S$' "$WINE_CALLS") -eq 2 ]]
[[ $(grep -c $'\tsteamservice\t/Install$' "$WINE_CALLS") -eq 1 ]]
[[ $(grep -c $'\t/Program Files (x86)/Steam/steam.exe\tsteam://install/2155180$' \
     "$WINE_CALLS") -eq 1 ]]
grep -Eq '/Steam Downloader\.app/Contents/SharedSupport/prefix[[:space:]]+.*/Steam Downloader\.app/Contents/SharedSupport/wine[[:space:]]+/SteamSetup\.exe[[:space:]]+/S$' "$WINE_CALLS"
grep -Eq '/Steam Seed\.app/Contents/SharedSupport/prefix[[:space:]]+.*/seed-layout\.[^/]+/wine[[:space:]]+/SteamSetup\.exe[[:space:]]+/S$' "$WINE_CALLS"
if grep -Eq '/Pioneers of Pagonia\.app/Contents/SharedSupport/(prefix|wine).*[[:space:]]+/SteamSetup\.exe[[:space:]]' "$WINE_CALLS"; then
  echo 'SteamSetup was incorrectly executed with the Wine 10 gameplay runtime.' >&2
  exit 1
fi
grep -Eq '/Pioneers of Pagonia\.app/Contents/SharedSupport/prefix[[:space:]]+.*/Pioneers of Pagonia\.app/Contents/SharedSupport/wine[[:space:]]+wineboot[[:space:]]*$' "$WINE_CALLS"

plist="$DESTINATION/Contents/Info.plist"
[[ "$(/usr/bin/plutil -extract 'Program Name and Path' raw "$plist")" \
   == '/Program Files (x86)/Steam/steam.exe' ]]
[[ "$(/usr/bin/plutil -extract 'Program Flags' raw "$plist")" \
   == '-cef-disable-gpu -no-cef-sandbox -applaunch 2155180 -NoDX12DeviceFactory -NoDX12SDKVersionCheck' ]]
[[ "$(/usr/bin/plutil -extract WINEESYNC raw "$plist")" == '0' ]]
[[ "$(/usr/bin/plutil -extract WINEMSYNC raw "$plist")" == '0' ]]
[[ "$(/usr/bin/plutil -extract WINEFSYNC raw "$plist")" == '0' ]]

game="$DESTINATION/Contents/SharedSupport/prefix/drive_c/Program Files (x86)/Steam/steamapps/common/Pioneers of Pagonia"
system32="$DESTINATION/Contents/SharedSupport/prefix/drive_c/windows/system32"
[[ -f "$game/Pioneers of Pagonia.exe" ]]
[[ ! -e "$game/D3D12Core.dll" ]]
[[ ! -e "$game/downloader-extra.txt" ]]
prefix="$DESTINATION/Contents/SharedSupport/prefix"
steam="$prefix/drive_c/Program Files (x86)/Steam"
appmanifest="$steam/steamapps/appmanifest_2155180.acf"
[[ -f "$appmanifest" ]]
grep -q '"LastOwner".*"76561197987380524"' "$appmanifest"
grep -q '"AccountName" "fixture"' "$steam/config/loginusers.vdf"
grep -q '"AuthData"' "$steam/userdata/27114796/config/localconfig.vdf"
grep -q '"SharedAuth"' "$steam/userdata/27114796/config/localconfig.vdf"
grep -q 'RecvMsgClientLogOnResponse() : processing complete' \
  "$steam/logs/connection_log.txt"
grep -q '"InstalledDepots"' "$appmanifest"
grep -q '"839939076860606424"' "$appmanifest"
if grep -Eq '"(UserConfig|MountedConfig)"' "$appmanifest"; then
  echo 'Downloader configuration metadata reached the gameplay appmanifest.' >&2
  exit 1
fi
[[ ! -e "$prefix/downloader-account-sentinel" ]]
[[ ! -e "$steam/config/downloader-sentinel" ]]
[[ ! -e "$steam/userdata/999/config/downloader-sentinel" ]]
[[ ! -e "$steam/appcache/downloader-sentinel" ]]
for forbidden in unexpected-auth.log unexpected-auth.cfg unexpected-auth.vdf \
                 ssfn-unexpected future-depot-state clientui/account.cfg \
                 resource/session.vdf steam/depot-state.json; do
  [[ ! -e "$steam/$forbidden" ]]
done
if grep -q 'DOWNLOADER_REGISTRY_SENTINEL' "$prefix/system.reg"; then
  echo 'Downloader registry sentinel reached the gameplay prefix.' >&2
  exit 1
fi
[[ "$(shasum -a 256 "$system32/dxgi.dll" | awk '{print $1}')" \
   == 'd53d9ea91935f0de126ba528264fc4c9b4dfea8bfe43f3f1256bd3e8963d67ee' ]]
[[ "$(shasum -a 256 "$system32/d3d12.dll" | awk '{print $1}')" \
   == '3174fac027d3ff10971645ac41b665cd53949c87d6d2d7d53b0073bf4bb36981' ]]
[[ "$(shasum -a 256 "$system32/d3d12core.dll" | awk '{print $1}')" \
   == 'b8cabb79a3f0a14babcbfd575cca70814e4d1d3e71606dfc1670421aaa39b97e' ]]

# Build a valid interrupted downloader and exercise the public --resume seam.
# The resumed installer must selectively import into a new Wine 10 prefix and
# remove the identity-checked downloader root only after publication succeeds.
mkdir -m 700 "$RESUME_ROOT" "$RESUME_ROOT/Steam Downloader.app"
RESUME_ROOT_DEVICE=$(stat -f '%d' "$RESUME_ROOT")
RESUME_ROOT_INODE=$(stat -f '%i' "$RESUME_ROOT")
tar -x --strip-components 1 -f "$ROOT/scripts/Wineskin-3.0.6-2.app.tar.xz" \
  -C "$RESUME_ROOT/Steam Downloader.app"
resume_extract="$MOCK_DIR/resume-runtime"
mkdir "$resume_extract"
tar -xf "$ROOT/scripts/WineCX-11.17-SteamDownloader-4.7.3.tar.xz" \
  -C "$resume_extract"
rm -rf "$RESUME_ROOT/Steam Downloader.app/Contents/SharedSupport/wine" \
  "$RESUME_ROOT/Steam Downloader.app/Contents/SharedSupport/prefix"
ditto "$resume_extract/steam-wine11.bundle/Wine" \
  "$RESUME_ROOT/Steam Downloader.app/Contents/SharedSupport/wine"
ditto "$resume_extract/steam-wine11.bundle/DXVK" \
  "$RESUME_ROOT/Steam Downloader.app/Contents/SharedSupport/dxvk"
ditto "$FIXTURE_PREFIX" \
  "$RESUME_ROOT/Steam Downloader.app/Contents/SharedSupport/prefix"
resume_prefix="$RESUME_ROOT/Steam Downloader.app/Contents/SharedSupport/prefix"
resume_steam="$resume_prefix/drive_c/Program Files (x86)/Steam"
mkdir -p "$resume_steam/config" "$resume_steam/userdata/27114796/config" \
  "$resume_steam/userdata/999/config"
printf 'resume account sentinel\n' >"$resume_prefix/downloader-account-sentinel"
printf 'resume config sentinel\n' >"$resume_steam/config/downloader-sentinel"
printf 'resume userdata sentinel\n' \
  >"$resume_steam/userdata/999/config/downloader-sentinel"
mkdir -p "$resume_steam/appcache" "$resume_steam/future-depot-state" \
  "$resume_steam/clientui" "$resume_steam/resource" "$resume_steam/steam"
printf 'resume cache sentinel\n' >"$resume_steam/appcache/downloader-sentinel"
printf 'resume root log\n' >"$resume_steam/unexpected-auth.log"
printf 'resume root config\n' >"$resume_steam/unexpected-auth.cfg"
printf 'resume root vdf\n' >"$resume_steam/unexpected-auth.vdf"
printf 'resume auth\n' >"$resume_steam/ssfn-unexpected"
printf 'resume nested depot\n' >"$resume_steam/future-depot-state/sentinel"
printf 'resume nested account\n' >"$resume_steam/clientui/account.cfg"
printf 'resume nested session\n' >"$resume_steam/resource/session.vdf"
printf 'resume depot state\n' >"$resume_steam/steam/depot-state.json"
printf 'RESUME_REGISTRY_SENTINEL\n' >>"$resume_prefix/system.reg"
printf 'resume depot extra\n' \
  >"$resume_steam/steamapps/common/Pioneers of Pagonia/resume-extra.txt"
printf '%s\n' \
  '"users"' '{' \
  '  "76561197987380524"' '  {' \
  '    "AccountName" "fixture"' \
  '    "RememberPassword" "1"' \
  '    "MostRecent" "1"' \
  '    "AllowAutoLogin" "1"' \
  '  }' '}' >"$resume_steam/config/loginusers.vdf"
printf '%s\n' \
  '"InstallConfigStore"' '{' '  "Software"' '  {' '  }' '}' \
  >"$resume_steam/config/config.vdf"
printf '%s\n' \
  '"UserLocalConfigStore"' '{' \
  '  "AuthData"' '  {' '    "fixture" "value"' '  }' \
  '  "SharedAuth"' '  {' '    "fixture" "value"' '  }' \
  '  "Software"' '  {' '    "Valve"' '    {' \
  '      "Steam"' '      {' '        "apps"' '        {' '        }' \
  '      }' '    }' '  }' '}' \
  >"$resume_steam/userdata/27114796/config/localconfig.vdf"
cp -p "$ROOT/scripts/pagonia-build-25784167-SHA256SUMS" "$RESUME_ROOT/"
resume_plist="$RESUME_ROOT/Steam Downloader.app/Contents/Info.plist"
plutil -replace 'Program Name and Path' -string '/Program Files (x86)/Steam/steam.exe' "$resume_plist"
plutil -replace 'Program Flags' -string '-no-cef-sandbox' "$resume_plist"
rm -f "$RESUME_PGREP_STATE"* "$RESUME_STEAM_UI_STATE" \
  "$RESUME_WINE_CALLS" "$RESUME_WINDOW_CHECK_STATE"
PAGONIA_SIM_PREFIX="$FIXTURE_PREFIX" \
PAGONIA_SIM_PGREP_STATE="$RESUME_PGREP_STATE" \
PAGONIA_SIM_STEAM_UI_STATE="$RESUME_STEAM_UI_STATE" \
PAGONIA_SIM_WINE_CALLS="$RESUME_WINE_CALLS" \
PAGONIA_TEST_MODE=1 \
PAGONIA_SIM_WINDOW_CHECK_STATE="$RESUME_WINDOW_CHECK_STATE" \
PAGONIA_STEAM_WINDOW_CHECKER="$MOCK_DIR/window-checker" \
PAGONIA_WINE_RUNNER="$MOCK_DIR/wine-runner" \
PAGONIA_PGREP_COMMAND="$MOCK_DIR/pgrep" \
PAGONIA_SLEEP_COMMAND="$MOCK_DIR/sleep" \
  "$INSTALLER" --resume "$RESUME_ROOT" --yes --no-launch \
  --destination "$RESUME_DESTINATION" >>"$LOG" 2>&1
RESUME_DEVICE=$(stat -f '%d' "$RESUME_DESTINATION")
RESUME_INODE=$(stat -f '%i' "$RESUME_DESTINATION")
[[ ! -e "$RESUME_ROOT" ]]
grep -q "Deployment installed: $RESUME_DESTINATION" "$LOG"
[[ $(grep -c $'\t/SteamSetup.exe\t/S$' "$RESUME_WINE_CALLS") -eq 1 ]]
if grep -q $'\tsteamservice\t' "$RESUME_WINE_CALLS" \
   || grep -q 'steam://install/2155180' "$RESUME_WINE_CALLS"; then
  echo 'Completed resume unexpectedly relaunched downloader setup.' >&2
  exit 1
fi
[[ $(grep -c $'\t.*/steam.exe\t' "$RESUME_WINE_CALLS" || true) -eq 2 ]]
grep -Eq '/Steam Seed\.app/Contents/SharedSupport/prefix[[:space:]]+.*/seed-layout\.[^/]+/wine[[:space:]]+.*/steam\.exe[[:space:]]+-silent$' "$RESUME_WINE_CALLS"
grep -Eq '/Pioneers of Pagonia\.app/Contents/SharedSupport/prefix[[:space:]]+.*/Pioneers of Pagonia\.app/Contents/SharedSupport/wine[[:space:]]+.*/steam\.exe[[:space:]]+-no-cef-sandbox' "$RESUME_WINE_CALLS"
if grep -Eq '/Steam Downloader\.app/Contents/SharedSupport/prefix[[:space:]].*/steam\.exe[[:space:]]' "$RESUME_WINE_CALLS"; then
  echo 'Completed resume relaunched the authenticated downloader UI.' >&2
  exit 1
fi
[[ ! -e "$RESUME_WINDOW_CHECK_STATE" ]]
if grep -Eq '/Pioneers of Pagonia\.app/Contents/SharedSupport/(prefix|wine).*[[:space:]]+/SteamSetup\.exe[[:space:]]' "$RESUME_WINE_CALLS"; then
  echo 'Resume executed SteamSetup with the Wine 10 gameplay runtime.' >&2
  exit 1
fi
resume_steam="$RESUME_DESTINATION/Contents/SharedSupport/prefix/drive_c/Program Files (x86)/Steam"
resume_manifest="$resume_steam/steamapps/appmanifest_2155180.acf"
[[ -f "$resume_manifest" ]]
grep -q '"LastOwner".*"76561197987380524"' "$resume_manifest"
grep -q '76561197987380524' "$resume_steam/config/loginusers.vdf"
grep -q 'AuthData' "$resume_steam/userdata/27114796/config/localconfig.vdf"
grep -q 'SharedAuth' "$resume_steam/userdata/27114796/config/localconfig.vdf"
grep -q 'RecvMsgClientLogOnResponse() : processing complete' \
  "$resume_steam/logs/connection_log.txt"
resume_prefix="$RESUME_DESTINATION/Contents/SharedSupport/prefix"
[[ ! -e "$resume_prefix/downloader-account-sentinel" ]]
[[ ! -e "$resume_steam/config/downloader-sentinel" ]]
[[ ! -e "$resume_steam/userdata/999/config/downloader-sentinel" ]]
[[ ! -e "$resume_steam/appcache/downloader-sentinel" ]]
[[ ! -e "$resume_steam/steamapps/common/Pioneers of Pagonia/resume-extra.txt" ]]
for forbidden in unexpected-auth.log unexpected-auth.cfg unexpected-auth.vdf \
                 ssfn-unexpected future-depot-state clientui/account.cfg \
                 resource/session.vdf steam/depot-state.json; do
  [[ ! -e "$resume_steam/$forbidden" ]]
done
if grep -q 'RESUME_REGISTRY_SENTINEL' "$resume_prefix/system.reg"; then
  echo 'Resumed downloader registry state reached the gameplay prefix.' >&2
  exit 1
fi
if grep -Eq '"(UserConfig|MountedConfig)"' "$resume_manifest"; then
  echo 'Resumed appmanifest retained downloader configuration metadata.' >&2
  exit 1
fi

echo 'Fresh-install packaging/control-flow smoke test: PASS'
echo 'Simulated: SteamSetup lifecycle, sign-in-complete state, depot completion, configuration, and publication.'
echo 'Not simulated: Steam authentication, Steam Guard, license authorization, or network depot transfer.'
