# Pioneers of Pagonia with Wine 11.16/11.17 and GPTK 4.0 beta 3

## Test dates

- Initial Wine 11 gameplay investigation: 2026-10-16
- Standalone Wine 11.17 Steam downloader and LANCache follow-up: 2026-10-17

## Purpose

Determine whether the historical Sikarugir Wine 10.0 runtime can be replaced with a current Wine runtime while retaining Apple D3DMetal 4.0 beta 3 support.

This was an isolated experiment. It did not modify the existing working Pagonia application or its historical Wine runtime.

## Executive summary

Whisky's experimental GPTK-capable Wine 11.16 runtime is a substantial improvement over the previously tested Sikarugir Wine 11.0 revision 1 runtime:

- the current Steam client started;
- Steam CEF rendered when launched with `-cef-disable-gpu`;
- Steam authentication completed successfully;
- Steam launched Pagonia with the required command-line options;
- Pagonia displayed its startup screen and produced audio.

It was not a successful replacement:

- Pagonia did not reach its usable main menu or a loaded map;
- two early attempts stopped at the same startup stage;
- the corrected Metal 4 attempt exited after approximately 38 seconds with Windows status `0xC0000005` (`STATUS_ACCESS_VIOLATION`);
- the required success messages `Created D3D12Device` and `Created D3D12 Swapchain` were not captured for Wine 11.16;
- terrain rendering was therefore not tested;
- one restart also crashed `steamwebhelper.exe`, although that CEF crash was caused by restarting Steam without the required CEF workaround and must not be confused with the Pagonia failure.

The historical Sikarugir Wine 10.0 runtime remains the only configuration that has passed the complete Pagonia acceptance criteria. A later fresh-prefix test established that Wine 11.17 can nevertheless provide a usable current Steam client when Steam is routed through pinned DXVK and native Wine DXGI. This does not change the gameplay verdict; it supports using Wine 11.17 only as an isolated downloader.

## Components tested

### Whisky application

Source:

- repository: `frankea/Whisky`
- application release: `app-v3.7.0`
- artifact: `Whisky-3.7.0.dmg`
- SHA-256: `8232b3b96be09b56e8f4e6b091c34a89c74b27c63ccfce92aa8ffe6ce3fbfee2`

Verification:

- GitHub release digest matched;
- macOS `codesign --verify --deep --strict` passed;
- Gatekeeper accepted the application as a notarized Developer ID application;
- signing identity: `Developer ID Application: Adam Franke (Z7JS58F8U3)`.

The original `Whisky-App/Whisky` project is archived. This test used the active but unofficial `frankea/Whisky` community fork.

### Stable Whisky runtime checked but not used for the game test

Whisky's default runtime `v3.1.1` contains Wine 11.0:

- artifact SHA-256: `01f3a1b43b98065fe20c529c1023b61dd79a6d2ad93bba6040865f646481ccf3`
- Wine executable SHA-256: `28d421328194cf9e7013d14295b74e06e7c4a8c70be65ff1e4f9d63a5556b337`
- Wineserver SHA-256: `482c06e172324468d4f2fe48987073f520bf6e478e5d609968c7199e133505d5`

Its `WhiskyWineVersion.plist` does not contain `gptkCapable=true`. Whisky's source treats a missing capability field as false and deliberately refuses to deploy GPTK into that runtime. It was therefore not a valid D3DMetal test candidate.

### Experimental Whisky runtime used

Release:

- runtime: `v4.6.4-beta.1`
- Wine version: `wine-11.16`
- artifact: `Libraries.tar.gz`
- size: 481,348,675 bytes
- SHA-256: `c8e6a10dfeb54fc16d3dd3382ee2e9d2cec3eb1f5641613cad8b07903818cb12`
- source project: `frankea/winecx-gptk`
- source commit stated by the release: `50a54af`
- Wine/CrossOver source revision stated by the release: `7dbc5b5`

Verification:

- GitHub release digest matched;
- archive paths and special file types were checked before extraction;
- `WhiskyWineVersion.plist` explicitly contained `gptkCapable=true`;
- the extracted runtime reported `wine-11.16`.

The release is explicitly a beta engine and is not Whisky's default runtime.

### Apple graphics payload

- Game Porting Toolkit 4.0 beta 3
- source: the user's read-only mounted Apple disk image
- `dxgi.dll` SHA-256: `d53d9ea91935f0de126ba528264fc4c9b4dfea8bfe43f3f1256bd3e8963d67ee`
- `d3d12.dll` SHA-256: `3174fac027d3ff10971645ac41b665cd53949c87d6d2d7d53b0073bf4bb36981`

The already established complete GPTK manifest and Apple-signature checks had previously passed for this mounted payload.

### Game and Steam

- Steam application ID: `2155180`
- Pagonia build ID: `25784167`
- game executable SHA-256: `a4c8aa367a7164e3621ff86819bd5135616da0b1a4afea6b14f0eeb5e9901f46`
- Steam client build: `1791918634`
- launch options: `-NoDX12DeviceFactory -NoDX12SDKVersionCheck`

The test used an APFS clone of an existing complete test prefix. The source prefix and working application were not modified.

## GPTK deployment used for the isolated runtime

The test mirrored Whisky's deployment layout for GPTK 4.0 beta 3:

1. Preserve Wine's original `d3d10.dll`, `d3d11.dll`, `d3d12.dll`, and `dxgi.dll`.
2. Install Apple's corresponding PE forwarders into `Wine/lib/wine/x86_64-windows`.
3. Copy Apple's authenticated `external` directory into `Wine/lib/external`.
4. Create `d3d10.so`, `d3d11.so`, `d3d12.so`, and `dxgi.so` links to `../../external/libd3dshared.dylib`.
5. Preserve the Wine runtime's own `d3d12core.dll`, matching the working GPTK 4.0 beta 3 configuration.

Whisky's optional D3D12 and DXGI interposers were intentionally not installed. The checked source allows them only for D3DMetal version `4.0b2`; the test payload was `4.0b3`. Installing those interposers would have violated the project's own fail-closed compatibility policy.

## Test timeline and results

### Attempt 1: direct Wine launch without the complete Whisky environment

Steam was started with:

```text
-cef-disable-gpu -applaunch 2155180 -NoDX12DeviceFactory -NoDX12SDKVersionCheck
```

What worked:

- Wine 11.16 initialized the cloned prefix.
- Steam started.
- `steamwebhelper.exe` remained alive with GPU rendering disabled.
- After correcting the profile mapping described below, Steam authenticated successfully.
- Steam launched Pagonia.
- Pagonia displayed its startup screen and produced audio.

What did not work:

- Pagonia remained at the startup stage.
- The launch options appeared twice because they were already stored in Steam and were also supplied on the command line.
- The test omitted `D3DM_MTL4=1`, which is required by the known-working Pagonia configuration.
- This attempt was therefore not a valid final Wine 11.16 compatibility verdict.

Steam recorded that the game ran for approximately two minutes and was removed with exit code `1`. The process had been terminated as part of the controlled restart, so that exit code does not identify the original hang's root cause.

### Profile compatibility correction

The cloned Wineskin prefix used a profile mapping incompatible with the Wine 11.16 CrossOver lineage. That mapping was corrected only inside the isolated clone, after which Steam authentication completed. The report intentionally omits local profile names, paths, account identifiers, authentication details, and tokens.

### Attempt 2: direct game restart while Steam state was changing

A direct Pagonia invocation caused Steam to process a `steam://run/2155180` request. During this transition a new Steam process was created without `-cef-disable-gpu`.

Observed failure:

```text
wine: Unhandled page fault on write access to 0000000000110000
```

The debugger module list identified the faulting process as `steamwebhelper.exe`, not `Pioneers of Pagonia.exe`.

This result proves that current Steam CEF still needs the established GPU-disable workaround under this runtime. It does not prove that Pagonia itself crashed at this point.

Pagonia was also launched during this attempt and again reached the same visible startup stage, but did not become usable.

### Steam Networking Sockets assertions

Steam generated two assertion dumps named for the Pagonia process. Both contain this assertion:

```text
Assert( No control data returned even though we asked for TOS? ):
steamnetworkingsockets_socketthread.cpp:2492
```

This indicates a mismatch in the Wine socket/control-message path used by Steam Networking Sockets. It is relevant because the same old/new Wine distinction also affects Steam downloading. However, the evidence does not establish that this assertion is what blocked the Pagonia startup sequence. Steam assertions can produce dumps without immediately terminating the game.

### Attempt 3: corrected Metal 4 environment

The final controlled attempt added the settings required by the known-working configuration:

```text
D3DMETAL=1
D3DMETAL_FORCE=1
D3DM_MTL4=1
LC_ALL=en_US.UTF-8
LANG=en_US.UTF-8
```

Steam was again launched with:

```text
-cef-disable-gpu -applaunch 2155180
```

The Pagonia switches were supplied only by Steam's stored launch options, avoiding duplicates.

What worked:

- Steam and its primary CEF process remained alive.
- Steam launched Pagonia with exactly:

```text
Pioneers of Pagonia.exe -NoDX12DeviceFactory -NoDX12SDKVersionCheck
```

What failed:

- Pagonia exited approximately 38 seconds after launch.
- Steam recorded exit code `-1073741819`.
- Interpreted as an unsigned Windows status, this is `0xC0000005`, or `STATUS_ACCESS_VIOLATION`.
- No Wine 11.16 log containing `Created D3D12Device` or `Created D3D12 Swapchain` was captured.
- No map or terrain was reached.

This is the strongest failure signal from the test. Unlike the manually terminated first attempt, the corrected attempt ended with a Windows access violation.

## What definitely worked

- Release downloads and SHA-256 verification
- Apple signature and mounted GPTK payload verification inherited from the existing installer work
- Wine 11.16 startup
- Wine prefix initialization
- current Steam build `1791918634`
- Steam CEF with `-cef-disable-gpu`
- Steam authentication after correcting the cloned profile mapping
- Steam launching App ID `2155180`
- correct Pagonia executable and official launch options
- visible Pagonia startup rendering
- Pagonia audio output

## What definitely did not work

- reaching a stable Pagonia menu
- loading a saved game or map
- confirming `Created D3D12Device`
- confirming `Created D3D12 Swapchain`
- confirming correct terrain rendering
- running Pagonia to a usable state with Wine 11.16
- running Steam CEF reliably when the GPU-disable switch was lost during an uncontrolled restart

## What is not yet proven

The available evidence does not identify the exact instruction or Wine subsystem responsible for Pagonia's final `0xC0000005`.

The following remain hypotheses rather than conclusions:

1. **Wine 11.16 regression or missing behavior used by Pagonia.** The historical Wine 10.0 runtime succeeds with the same game and GPTK payload, making a Wine behavioral difference the leading category.
2. **Incomplete replication of Whisky's per-program graphics routing.** The test used Whisky's runtime and deployment layout but invoked Wine directly. Whisky normally scopes Steam/CEF to a non-D3DMetal backend while allowing the game to use D3DMetal. The direct test did not reproduce that complete orchestration.
3. **Steam Networking Sockets control-message incompatibility.** The repeated TOS assertion shows a real Winesock discrepancy, but causality for the startup failure is unproven.
4. **Prefix migration effects.** The test cloned a Wineskin-created prefix and adapted its user profile for the CrossOver-style runtime. A completely fresh Whisky-created bottle could behave differently.
5. **A D3DMetal/Wine exception or loader boundary.** Wine 11.16 advertises the exception-unwind capability required by Whisky, but Pagonia may exercise another path not covered by the runtime's existing D3D12 tests.

## Comparison with the known-working baseline

The historical Sikarugir Wine 10.0 configuration, using the same Pagonia executable and GPTK 4.0 beta 3 payload, previously produced:

```text
Enabled MTL4 backend - options=RTV
Created D3D12Device
Created D3D12 Swapchain
```

It reached the game and rendered terrain correctly.

Earlier Sikarugir Wine 11.0 revision 1 experiments were worse than the new Wine 11.16 beta: they repeatedly produced a null-read page fault at `0x00007FF8123471E3` under several configurations, including with Metal 4 disabled and with different DXIL choices. Wine 11.16 advanced to visible startup rendering and audio before its later access violation.

## Standalone per-executable routing follow-up

The remaining relevant Whisky graphics orchestration was reproduced directly in the isolated prefix without launching Whisky or adopting its bottle format:

- Steam, Steam WebHelper, Steam Service, and the overlay received application-specific `native,builtin` overrides for the available DXVK `dxgi`, `d3d10core`, and `d3d11` path.
- `d3d12` was disabled for those Steam processes.
- `Pioneers of Pagonia.exe` received application-specific `builtin` overrides for `dxgi`, `d3d10core`, `d3d11`, `d3d12`, and `d3d12core`, retaining GPTK/D3DMetal.
- Metal 4 and esync were enabled with `D3DM_MTL4=1` and `WINEESYNC=1`.

Steam and CEF remained operational, but Pagonia again failed to advance from the same startup screen. One normal-logging run exited after 34 seconds with `-1073741819` (`0xC0000005`). A subsequent `+seh,+module` run remained alive while consuming approximately one CPU core.

A five-second macOS sample of that live hang captured stable stacks for all 599 samples:

- A D3DMetal command-queue worker was blocked in `D3DMCommandQueueWorker::DoPresent` on an unfair lock.
- Another D3DMetal command-queue worker was in `D3DMCommandQueueWorker::DoExecute`, below `IOGPUMetalResidencySet commit`, a Wine `segv_handler`, and Wine debug logging.
- The sampled frame immediately above execution was `IMTLD3DDevice::Version() const + 6`, followed by a null frame.
- The D3D12 asynchronous transfer thread and many other threads were waiting.

This is substantially stronger evidence that the hang is an exception loop or failed synchronization at the Wine 11.16/D3DMetal command-queue boundary. It also explains the high CPU usage and blocked presentation. It does not identify which component first supplied invalid state, so it is not sufficient to assign the defect exclusively to Wine or D3DMetal.

The separate Steam Networking Sockets TOS assertion still occurred, but the sampled hang itself was inside D3DMetal command execution rather than a networking stack.

### Esync-disabled control

The same standalone routing was tested once more with `WINEESYNC=0`. Pagonia remained stuck at the same visible startup phase for more than one minute, consumed approximately 320% CPU, and produced neither `Created D3D12Device` nor `Created D3D12 Swapchain` in the captured output.

Unlike the debug-instrumented esync run, a three-second sample showed active D3DMetal command encoding across concurrent workers, including indexed draws, mesh draws, texture copies, command replay, and residency-set commits. It did not show one stable exception-loop stack. Disabling esync therefore changes scheduling and CPU behavior but does not resolve the user-visible startup failure. The isolated Wine server was stopped after evidence collection.

### Direct launch without Steam `-applaunch` or overlay

A static string inspection found no evidenced Pagonia command-line option for disabling asynchronous compute or command queues. An additional isolation run therefore started Steam silently, then invoked `Pioneers of Pagonia.exe` directly with the required DX12 options, `SteamAppId=2155180`, and `SteamNoOverlayUIDrawing=1`. This bypassed Steam's `-applaunch` path and overlay launch injection.

The game initialized D3DMetal far enough to enumerate the GPU and emit `Evict`/`MakeResident` unsupported notices, but it again produced neither required D3D12 success marker and remained at the same visible startup phase until the run was manually aborted by the user. A Pagonia assert dump was also created during the run, but it must not be interpreted as the cause of process termination. Steam launch injection and the overlay are therefore not the root cause of the persistent visible hang.

The runtime also carries D3D12 and DXGI interposers, but its source deliberately permits them only with GPTK `4.0b2`. The policy explicitly fails closed for other builds; installing them over GPTK `4.0b3` would be unsupported and was not attempted.

## Wine 11.17 follow-up

A later GPTK-capable runtime was tested after explicit approval:

- source project: `dappermint/winecx-gptk`
- release: `runtime-v4.7.3`
- Wine version: `wine-11.17`
- artifact: `Libraries.tar.gz`
- SHA-256: `a4b5d63493f80698cce5cad8e7212d9a51c8292037b00c478f4652636fcfd331`
- game executable SHA-256: `a4c8aa367a7164e3621ff86819bd5135616da0b1a4afea6b14f0eeb5e9901f46`

The release hash matched. Archive paths, links, and hard-link absence were checked before extraction. A new private test directory received an APFS clone of the test prefix, not the working application. The authenticated GPTK 4.0 beta 3 payload was deployed in the same layout as the Wine 11.16 test, Wine 11.17's own `d3d12core.dll` was preserved, and the Steam/DXVK versus Pagonia/D3DMetal application overrides remained in place.

Wine 11.17 started the current Steam client and CEF with `-cef-disable-gpu`. The cloned Steam session did not automatically return to a logged-in state during this run, so the initial `-applaunch 2155180` request did not launch the game. A direct launch was then used only to exercise game initialization. It reported that Steam API initialization was unavailable, initialized D3DMetal far enough to enumerate the GPU, emitted the same `Evict` and `MakeResident` unsupported notices, and remained at the same visible startup phase. It produced neither `Created D3D12Device` nor `Created D3D12 Swapchain` before the user manually aborted it.

This was not a complete authenticated gameplay test, but it showed no rendering-startup improvement over Wine 11.16. The isolated Wine 11.17 server was stopped, and no existing installation was modified.

## Standalone Wine 11.17 Steam downloader follow-up

A fresh standalone downloader was tested on 2026-10-17 using direct Wine invocation rather than Whisky or the Wineskin launcher. The pinned downloader archive has SHA-256 `064de70024679010b65b3619c0de9f2993b432dc511bb018a55fc3b31aefece9` and contains Wine 11.17 plus the required DXVK-macOS 1.10.3 files; it contains no Steam, game, prefix, account, or Apple GPTK data.

### Failed approaches and misleading signals

The first fresh-prefix attempts did not produce a usable login interface:

- `BrowserReady` appeared in `steamui_html.txt` even while the captured Steam window was entirely black. `BrowserReady` therefore proved CEF object creation, not successful presentation.
- Running with `-cef-disable-gpu` avoided one historical webhelper crash mode but left the new standalone login UI black.
- Launching the temporary application through macOS `open` invoked the Wineskin launcher, triggered Gatekeeper verification and Wineskin lock behavior, and did not provide a reliable downloader path.
- Removing extended attributes did not solve the rendering problem.
- Ad-hoc signing changed the hash-pinned `wineskinlauncher`; the installer correctly rejected that modified staging instead of updating its expected hash.
- Wine 11.17 alone was insufficient. A fresh prefix did not reproduce the earlier Whisky result until the graphics payload, DLL routing, and environment were reproduced together.

No hash was weakened or adjusted to accept a locally modified executable. Experimental staging directories were treated as untrusted and discarded.

### Working Steam configuration

The successful downloader configuration uses:

- pinned DXVK-macOS 1.10.3 `d3d10core.dll` and `d3d11.dll` for x86 and x64;
- Wine 11.17's native `dxgi.dll` with its Wine builtin marker removed, SHA-256 `f72fe1c82373fe3e2f198df7affb527b0d2117392f5f46577e856efa97a8d024`;
- per-executable `native,builtin` overrides for `dxgi`, `d3d10core`, and `d3d11` on Steam, Steam WebHelper, Steam Service, and both overlay executables;
- `LC_ALL=en_US.UTF-8`, `LANG=en_US.UTF-8`, `LC_TIME=C`, `LC_NUMERIC=C`, `CEF_DISABLE_SANDBOX=1`, `STEAM_DISABLE_CEF_SANDBOX=1`, `STEAM_RUNTIME=0`, and extended WinHTTP timeouts;
- direct `wine64` startup with `-no-cef-sandbox -vgui`;
- CEF GPU rendering enabled: `-cef-disable-gpu` is deliberately absent.

A later clean installer run with Steam client build `1791918634` reproduced an
indefinitely black 500×500 login surface without `-vgui`, despite successful
DXVK initialization and live CEF GPU/renderer processes. Adding `-vgui`
produced the titled 700×440 `Sign in to Steam` window with pixel-validated
content. The installer therefore treats `-vgui` as required downloader
compatibility behavior, not as an optional presentation preference.

The login popup took approximately one minute to complete its first CEF load. It was initially possible to observe blank Wine windows during that startup interval. The final acceptance gate required the actual `Sign in to Steam` window to contain non-black rendered pixels; a `BrowserReady` log line alone was no longer accepted. The user then authenticated through the visible QR interface, and Steam began downloading App ID `2155180` in the fresh Wine 11.17 prefix.

This result proves that Wine 11.17 is suitable for the current Steam login/download role. It does not prove that Wine 11.17 is suitable for Pagonia gameplay, and none of the negative D3D12 findings above changed.

### LANCache result and performance diagnosis

The real downloader used operating-system DNS and initially reached the configured LANCache. Steam recorded the local cache endpoint, the Pagonia depot manifest request returned HTTP 200, and server access logs showed repeated real `HIT` responses for depot `2155181`. This proves functional LANCache routing.

The cache was nevertheless slower than the direct Steam CDN in this environment. Read-only server measurements during cache-hit traffic showed:

- cache storage on `/dev/sda`, model `ST4000LM024-2AN17V`, a rotational 4 TB 2.5-inch SMR disk;
- encrypted Btrfs storage with `relatime`;
- 100% disk utilization while delivering only about 17 MB/s;
- approximately 40–46 ms read latency and a deep I/O queue;
- multiple NGINX workers blocked in uninterruptible I/O wait;
- low cache-container CPU use and valid SMART health with no reallocated, pending, or uncorrectable sectors.

The disk can still be fast for sequential reads. Steam's many parallel, hash-distributed chunk files produce random reads and seek latency instead. General host I/O pressure was also high during the observation, but the saturated cache disk and blocked NGINX workers identify the immediate bottleneck. Disabling the cache DNS allowed Steam to use the direct CDN and improved observed download speed. The download may contain both cache and direct-CDN traffic during DNS transition; final depot integrity is independent because the installer validates every game file against the pinned manifest.

LANCache is therefore optional, not a prerequisite or guaranteed optimization. With unrestricted download volume and a 400-Mbit/s Internet connection, direct Steam CDN access is preferable to this HDD-backed cache. A cache intended to improve speed should use SSD/NVMe or another storage tier with adequate random-read performance.

## Manual termination note

The user manually stopped the earlier hanging Wine 11.16 and Wine 11.17 gameplay runs after observing that they made no progress. Their process disappearance or final exit status must not be treated as evidence of an automatic crash. The valid negative evidence from those runs is the persistent visible startup hang and absence of the required D3D12 success markers. Earlier explicitly captured exceptions remain separate observations.

## Recommended split-runtime architecture

The test results support separating Steam maintenance from gameplay instead of replacing the working game runtime:

1. Use a modern Wine runtime in a dedicated Steam/download prefix for login, updates, and depot downloads.
2. Stop that prefix's complete Wine server before reading or transferring files.
3. Transfer only the completed Pagonia installation directory and the corresponding `appmanifest_2155180.acf` after validating App ID, build ID `25784167`, completion state, and expected game executable hash.
4. Publish the transferred files into a separate gameplay prefix that is used only with the pinned historical Sikarugir Wine 10.0 runtime and GPTK 4.0 beta 3.
5. Never run two Wine versions against the same prefix and never share mutable registry, user-profile, compatdata, or Steam-client state between the two prefixes.
6. Stop the gameplay prefix before a later atomic game update is imported. Preserve the previous game copy until the replacement has passed integrity and launch checks.

This design is now implemented by the standalone installer. The 2026-10-17 fresh run validated visible Wine 11.17 Steam rendering, QR authentication, licensed depot startup, and both LANCache-hit and direct-CDN traffic. A later full depot download validated all 856 pinned files, while subsequent real runs exposed and corrected seed, cleanup, and first-launch lifecycle defects. The current design transfers a narrowly scoped, integrity-inventoried Steam session from the stopped downloader and verifies an online `LogOnResponse 'OK'` in Wine 10 before publication, eliminating the second interactive login. A complete fresh gameplay acceptance run remains required before release.

## Final result matrix

| Runtime and variant | Observed result | Termination | Verdict |
| --- | --- | --- | --- |
| Historical Sikarugir Wine 10.0 revision 2, GPTK 4.0b3 | Created D3D12 device and swapchain; loaded map with visible terrain | Normal verified gameplay | Supported project baseline |
| Wine 11.16, Metal 4, per-executable Steam/DXVK and Pagonia/D3DMetal routing | Same visible startup hang; no required D3D12 success markers | Recent instrumented run manually stopped after evidence capture | No improvement |
| Wine 11.16 with `WINEESYNC=0` | Same visible startup hang; approximately 320% CPU; active D3DMetal command encoding | Manually stopped after sampling | esync is not the fix |
| Wine 11.16, direct game launch without Steam `-applaunch` or overlay injection | Same visible startup hang; no required D3D12 success markers | Manually stopped by the user | Steam launch injection and overlay are not the cause |
| Wine 11.17 `runtime-v4.7.3`, GPTK 4.0b3 gameplay test | Same visible startup phase; no required D3D12 success markers | Manually stopped by the user | No observed gameplay improvement; Steam session was not authenticated in that game test |
| Wine 11.17 standalone Steam downloader with DXVK/native DXGI | Visible pixel-validated login, QR authentication, and Pagonia depot download | Active downloader role; game not launched with this runtime | Successful Steam/download runtime |

Additional final observations:

- Static inspection found no evidenced Pagonia command-line switch for disabling asynchronous compute or command queues; invented switches were not tested.
- Wine 11.16/11.17 emitted D3DMetal `Unsupported: Evict` and `Unsupported: MakeResident` notices. Their causal role is unproven.
- The available runtime interposers are explicitly allowlisted only for GPTK `4.0b2`; they were correctly not installed over GPTK `4.0b3`.
- All isolated Wine 11.16 and Wine 11.17 processes were stopped after testing.
- The working application and pinned historical gameplay runtime were not modified.

## Current conclusion

The tests do not show that modern Wine plus GPTK is impossible. They show that the tested Wine 11.16 and Wine 11.17 runtimes do not improve Pagonia over the known-working historical runtime.

Reproducing the relevant per-executable Steam/DXVK and Pagonia/D3DMetal routing, disabling esync, bypassing Steam's launch/overlay path, and moving to Wine 11.17 did not resolve the visible startup hang. The historical Sikarugir Wine 10.0 build therefore remains the selected gameplay runtime. The later successful Steam downloader validation changes only Wine 11.17's maintenance role, not this gameplay conclusion.

The pass condition remains:

```text
Created D3D12Device
Created D3D12 Swapchain
```

followed by a loaded map with visible terrain and no `Failed to materializeAll` error.

## Private evidence handling

The isolated runtimes, cloned prefixes, logs, screenshots, and dumps remain local. They contain authenticated account state and are not part of this repository. This report intentionally excludes account identifiers, authentication data, tokens, hardware identifiers, and absolute user-specific paths.
