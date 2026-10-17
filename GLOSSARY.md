# Pagonia macOS Installer

Terms for the standalone Pioneers of Pagonia deployment workflow.

## Language

**Managed installation**:
A published Pagonia application whose identity is proven by installer-owned markers and validated structure.
_Avoid_: Candidate, possible installation

**Staging deployment**:
A private, unpublished deployment state that can be validated, resumed, or discarded as a unit.
_Avoid_: Temp folder, partial app

**Fresh deployment**:
A deployment that begins after all managed installation and staging state has been removed.
_Avoid_: Clean-ish install, forced install

**Resume**:
Continuation of one validated staging deployment from its highest proven durable state.
_Avoid_: Prefix reuse, migration

**Orphaned downloader**:
Wine or Steam processes that still belong to a managed staging deployment after its controlling installer has exited.
_Avoid_: Active Resume, unrelated Steam

**Downloader prefix**:
The isolated Steam environment used for authentication and acquisition, never for gameplay.
_Avoid_: Source prefix, Steam prefix

**Gameplay prefix**:
The isolated final Steam environment used to launch Pagonia, never to execute SteamSetup.
_Avoid_: Final downloader, migrated prefix

**Session snapshot**:
The allowlisted, integrity-inventoried Steam authentication state transferred from the stopped downloader prefix to the gameplay prefix.
_Avoid_: Prefix copy, account backup

**Clean client snapshot**:
The package-manifest-validated Steam program payload created without authentication state.
_Avoid_: Steam backup, client cache

**Managed state**:
The union of managed installations and staging deployments that `--fresh` and `--delete` may remove.
_Avoid_: Everything named Pagonia
