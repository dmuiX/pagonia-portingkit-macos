# Pagonia macOS Installer Specification

## 1. Design directive

Implement this specification **as simply, narrowly, and slimly as possible**.

Use a small orchestration script rather than a monolith. Put independently testable parsing, inventory, and process-control logic in focused helpers. Keep one source of truth for every rule. Fresh and Resume must converge on the same state machine.

The implementation has these structural acceptance rules:

- no embedded Python or other programs in Bash heredocs;
- one responsibility per helper;
- every production function maps directly to a requirement in this specification;
- no duplicate Fresh and Resume implementations;
- no historical experiments, obsolete compatibility paths, or speculative fallbacks.

Do not optimize for an arbitrary line count. Optimize for the smallest implementation whose responsibilities and trust boundaries remain explicit.

## 2. Goal

Create a standalone application at:

```text
/Applications/Pioneers of Pagonia.app
```

The application must run Pioneers of Pagonia on Apple Silicon using:

- Wine 11.17 only for Steam login, Steam client maintenance, and game download;
- the pinned historical Sikarugir Wine 10 runtime only for gameplay;
- user-supplied, authenticated GPTK 4.0 beta 3 files for D3DMetal;
- the currently approved Steam build `25784167` of App ID `2155180`.

Game-build support is manifest-driven. Build `25784167` is the only currently
approved build; supporting another build requires a separately reviewed depot
manifest and acceptance run, not an automatic version relaxation.

The normal path requires one Steam sign-in. The authenticated session is transferred selectively from Wine 11 to Wine 10. The two Wine versions never share a prefix.

## 3. Non-goals

The installer does not:

- bundle GPTK, D3DMetal, Steam credentials, or game files;
- depend on Porting Kit, Whisky, GTA wrappers, or another installed Wineskin app;
- run `SteamSetup.exe` with Wine 10;
- migrate an entire authenticated Wine 11 prefix into Wine 10;
- copy downloader registry state, caches, logs, package downloads, unrelated userdata, or mutable depot metadata;
- automate credentials, Steam Guard secrets, or QR approval;
- choose a Steam Cloud conflict on the user's behalf unless Steam itself applies its normal default;
- modify DNS or embed a LANCache address;
- import or reuse an arbitrary external Wine prefix.

## 4. Inputs and pinned identities

The repository supplies:

- the Wine 10 gameplay runtime archive;
- the Wine 11.17 downloader runtime archive;
- the Wineskin wrapper archive;
- the complete GPTK file and symlink manifests;
- the complete 856-file Pagonia depot manifest;
- hashes for SteamSetup, runtime binaries, DXVK/DXGI files, GPTK manifests, and the expected game executable.

The user supplies GPTK 4.0 beta 3 by mounting its DMG or placing the DMG in `~/Downloads` after accepting Apple's license.

Every bundled archive and pinned executable must be verified before execution. The GPTK volume must be read-only, match both manifests exactly, and pass the required Apple signature checks.

## 5. Command-line behavior

### Default invocation

```bash
./scripts/install-pagonia-gptk4b3.sh
```

The default invocation performs deterministic state selection:

1. If exactly one valid managed staging deployment exists, resume it automatically.
2. If that staging has orphaned Wine or Steam processes, terminate them only after proving that every targeted process belongs to that staging; then resume it as dormant state.
3. If no valid managed staging deployment exists, start a Fresh deployment.
4. If multiple valid managed staging deployments exist, fail closed and list them; require `--resume PATH`.
5. If process ownership is ambiguous, fail closed without terminating anything.

### Explicit modes

- `--fresh`: remove existing managed installation and staging state, then create a new deployment.
- `--resume PATH`: resume exactly the validated managed staging path.
- `--delete`: display and remove managed installation and staging state, then exit.
- `--yes`: accept the single global managed-state deletion confirmation for `--fresh` or `--delete`; it does not bypass Steam interaction or any validation.

The installer refuses root execution and concurrent installer instances.

## 6. State machine

Use one explicit state machine with durable checkpoints. Resume continues from the highest fully validated state; it never trusts a marker without validating the corresponding files.

### State A: state selection and just-in-time verification

Every invocation validates CLI arguments, lock ownership, managed-state identities, and the fixed `/Applications` destination before mutation.

A Fresh deployment then performs the complete immutable-input preflight: repository helpers, manifests, archives, hashes, GPTK location and authentication, same-filesystem publication requirements, and Screen Recording permission.

A Resume does not repeat the complete Fresh preflight. It first validates only the selected staging deployment, its durable state, and any associated processes. Each immutable input is verified just before the resumed state first consumes it. A prior durable result such as a fully validated depot is reused without repeating acquisition.

Completion criterion: Fresh has authenticated every immutable input before execution; Resume has authenticated its staging and every input needed by the next state.

### State B: Wine 11 downloader preparation

1. Create a private `0700` staging root under `/private/tmp/Pagonia-GPTK4b3-deployment.*`.
2. Extract the Wine 11 runtime and wrapper from pinned archives.
3. Initialize a new Wine 11 prefix.
4. Download and hash-check the official `SteamSetup.exe`.
5. Run SteamSetup only with Wine 11.
6. Install or repair `steamservice.exe /Install` inside that Wine prefix.
7. Deploy the verified DXVK/native-DXGI configuration.

An incomplete Resume validates the existing Wine 11 runtime against a complete runtime manifest. An exact match is reused; any mismatch causes complete replacement from the pinned archive before execution.

Completion criterion: the current Steam client exists in the isolated Wine 11 prefix and the runtime configuration validates.

### State C: one interactive Steam login

1. Start Steam directly with Wine using:

   ```text
   -no-cef-sandbox -vgui
   ```

2. Keep CEF GPU rendering enabled.
3. Confirm Screen Recording permission immediately before checking that a current on-screen Wine window named `Sign in to Steam` or `Steam` contains rendered pixels. Fresh may satisfy this check during preflight; Resume must recheck it here.
4. BMP validation must support the actual macOS `sips` output, including 32-bit `BI_BITFIELDS` BMPs with standard BGRA masks.
5. Wait for a successful Steam login and persisted automatic-login state.
6. Accept current Steam persistence formats. Account selection rules are:
   - one explicit `MostRecent=1` account, or
   - exactly one stored account when current Steam omits `MostRecent`.
7. Require persisted authentication data in the active account's `localconfig.vdf` (`AuthData` and `SharedAuth`). Do not require obsolete `config.vdf/ConnectCache`.

Completion criterion: Steam reports login success and the persisted session can be captured without another credential prompt.

### State D: game installation and validation

1. Send:

   ```text
   steam://install/2155180
   ```

   after authentication succeeds.
2. Ask the user to confirm Steam's preselected install dialog only when Steam requires that confirmation.
3. Wait for App ID `2155180` to reach `StateFlags=4` and build `25784167`.
4. Stop every process belonging to the Wine 11 prefix and wait for its wineserver.
5. Validate all 856 manifest-listed files and total size `7672576380` bytes.
6. Reject missing, changed, linked, non-regular, or unexpected transfer inputs.

Completion criterion: the stopped downloader contains the exact pinned depot.

### State E: disjoint Steam snapshots

Create two disjoint snapshots from the stopped downloader.

The session snapshot captures only:

- `config/loginusers.vdf`;
- `config/config.vdf`;
- optional `config/SteamAppData.vdf`;
- the active account's `userdata/<account>/config/localconfig.vdf`;
- valid root-level `ssfn<digits>` files when present.

Requirements:

- every source component is unlinked, owner-controlled, size-bounded, and contained beneath the Steam root;
- the snapshot has an exact SHA-256 inventory;
- unlisted files are rejected;
- the snapshot records exactly one selected Steam ID;
- no registry hive, cache, log, package cache, unrelated userdata, or game-depot state enters the snapshot.

The clean client snapshot uses `package/steam_client_win64.installed` from the stopped authenticated downloader as Valve's installed-file inventory. Parse it strictly, reject unsafe or duplicate paths, and validate every non-negative entry against the corresponding regular file by size and CRC. Copy only those validated Steam program files plus the validated inventory file itself, which is an explicit metadata exception needed to prevent a redundant client reinstall. Record every copied file, including that exception, in an exact SHA-256 snapshot inventory. Exclude authentication, registry, userdata, config, logs, cache, other package contents, package downloads, and depot state.

No source file may appear in both snapshots. Neither snapshot may contain a file omitted from its own SHA-256 inventory.

Completion criterion: self-contained, inventory-validated session and clean-client snapshots exist after Wine 11 has stopped.

### State F: Wine 10 gameplay prefix

1. Create the final app in private staging using the pinned wrapper and Wine 10 runtime.
2. Initialize Wine 10 with `wineboot`; never run SteamSetup under Wine 10.
3. Install the clean Steam client snapshot.
4. Immediately remove the temporary clean snapshot after consumption.
5. Install the validated Steam session snapshot.
6. Copy only the 856 manifest-listed game files into a newly created game directory.
7. Generate a sanitized `appmanifest_2155180.acf` with the transferred Steam ID as `LastOwner`.
8. Install authenticated GPTK 4.0 beta 3 components and configure only the required DLL overrides.
9. Set launch options:

   ```text
   -NoDX12DeviceFactory -NoDX12SDKVersionCheck
   ```

10. Verify Wine 10 accepts the transferred account online using correlated, ordered Steam log records for that Steam ID.

Completion criterion: the Wine 10 prefix contains only validated program, session, and game inputs and has proven online Steam authentication.

### State G: publication and acceptance

1. Validate the complete staged application.
2. Recheck same-filesystem publication requirements immediately before publishing, then publish atomically to the destination without replacing an identity-changed path.
3. Preserve or restore the previous destination on publication failure.
4. Launch the published application.
5. Gameplay acceptance requires:
   - the expected Pagonia command line;
   - `Created D3D12Device`;
   - `Created D3D12 Swapchain`;
   - visibly rendered terrain.

Completion criterion: the published application passes the real gameplay acceptance criteria.

## 7. Resume behavior

Resume paths must be direct children of `/private/tmp`, private, owner-controlled, non-symlinked, and identity-stable.

A completed and validated depot Resume:

- does not reopen the authenticated downloader;
- does not request another login;
- proceeds directly to session capture and final construction.

An incomplete Resume:

- terminates orphaned Wine and Steam processes only when every target is proven to belong to that staging;
- fails closed when process ownership is ambiguous;
- treats the staging as dormant after confirmed termination;
- reuses Wine 11 and DXVK only after a complete runtime-manifest match, otherwise replaces them from the pinned archive;
- repairs SteamSetup or Steam Client Service state when necessary;
- restarts Steam and continues through the same state machine.

A Resume failure preserves the downloader staging when it remains safe and useful.

## 8. Delete behavior

`--delete` displays every managed installation and managed staging deployment, requests one global confirmation, removes that managed state, then exits. `--fresh` performs the same confirmed managed-state removal before creating a new deployment. `--yes` may supply only this global confirmation.

Deletion must:

1. recognize managed state through installer-owned identity markers and structural validation, never through a broad name match alone;
2. report broad unverified name matches but leave them untouched;
3. record and recheck device/inode identity before removal;
4. refuse symlinks and changed paths;
5. require Wine, Steam, and Pagonia processes to be exited first;
6. never execute `wineserver` or any code from a deletion candidate;
7. require no per-path selection once managed ownership has been proven.

## 9. Failure and cleanup behavior

- Signals produce status `130`.
- Child commands use bounded TERM/KILL shutdown.
- No Steam/Wine process may be left running after a failed controlled shutdown.
- Sensitive window captures are private and deleted on success, failure, and signals.
- Failed final publication is quarantined or rolled back without destroying the previous application.
- The downloader staging is preserved only when Resume can safely use it.
- Temporary session and clean-client snapshots are deleted immediately after use.

## 10. Output contract

Keep the existing concise, operator-friendly output style.

Requirements:

- announce every major numbered phase;
- print a progress line before any operation that may be silent for more than five seconds;
- distinguish checks from retries and report elapsed seconds, not ambiguous “attempt” counts;
- state exactly when user action is required;
- state what is being waited for: Steam window, login, install confirmation, depot state, shutdown, validation, or publication;
- avoid per-two-second message spam; periodic status every 20–30 seconds is sufficient;
- print the preserved Resume path after a recoverable failure;
- never print credentials, tokens, session values, private registry data, or full sensitive logs.

Representative output:

```text
Fresh preflight:
  1/7 Verifying tracked manifests...
  ...
Fresh preflight verification complete.

# A Resume starts here instead of repeating Fresh preflight:
Resume 1/3: Validating the preserved downloader staging...
Resume 2/3: Verifying the existing Wine 11.17 runtime...
Resume 3/3: Continuing from the last validated state...
  Starting Steam UI directly with Wine...
  Steam UI retry after 30 elapsed seconds...
  Steam may need a while to create its first window after a client update; the installer is still monitoring it.
  Steam UI is visibly rendered.
ACTION REQUIRED: Sign in and complete Steam Guard or QR confirmation.
  Steam sign-in completed.
  Opening the Pioneers of Pagonia installation dialog in Steam...
ACTION REQUIRED: Confirm the preselected Steam installation dialog once.
  Waiting for download: StateFlags=..., build=...
```

## 11. Implementation structure

Create a new implementation from this specification. Treat the current monolithic installer only as a behavioral and evidence source; do not incrementally refactor it into the replacement. Keep the old installer available until the replacement passes all automated and real acceptance gates.

Target a shallow replacement:

- one small Bash entry point for CLI parsing and state transitions;
- one focused helper for bounded process execution;
- one helper for Steam session parsing/inventory;
- one helper for Steam login-log correlation;
- one helper for image validation;
- declarative hash manifests for immutable inventories.

Do not embed large Python programs inside Bash. Move a parser or validator into a helper when it has independent inputs and outputs. Do not duplicate validation between Fresh and Resume. Remove obsolete paths rather than retaining compatibility branches that are not required by this specification.

## 12. Test requirements

Before a real deployment, all of the following must pass:

- `bash -n` and ShellCheck;
- Python compilation;
- unit tests for BMP variants, including real `BI_BITFIELDS` output;
- unit tests for current and legacy `loginusers.vdf` account selection;
- unit tests for `AuthData`/`SharedAuth` session capture and tamper rejection;
- ordered Steam login-log correlation tests;
- bounded child success, failure, TERM, and KILL tests;
- deletion security controls;
- Fresh and completed/incomplete Resume simulations;
- `git diff --check`.

Development commits are allowed before real acceptance when they are clearly unreleased and their available automated checks pass. Replacing the old installer or publishing a release additionally requires one uninterrupted real Fresh run through login, download, transfer, publication, final online Steam validation, D3D12 device creation, D3D12 swapchain creation, and visible terrain.

## 13. Definition of done

The implementation is done only when:

1. every state and failure rule in this specification is covered;
2. the default invocation selects Fresh or Resume correctly;
3. one Wine 11 login reaches authenticated Wine 10 without copying an entire prefix;
4. no untrusted runtime is executed by Resume or Delete;
5. all automated tests pass;
6. a real Fresh deployment passes the gameplay acceptance criteria;
7. the production implementation is the smallest maintainable design that satisfies items 1–6.
