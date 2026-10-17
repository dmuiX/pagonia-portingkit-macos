# Separate download and gameplay runtimes

Pagonia's D3D12 device, swapchain, and visible terrain have only ever been produced by the pinned historical Sikarugir Wine 10 runtime, while the current Steam client only works acceptably on Wine 11.17. We therefore keep two strictly separated prefixes: Wine 11.17 for authentication and acquisition, the pinned Wine 10 build for gameplay, joined by a selective session and depot transfer rather than a shared prefix.

## Why the downloader must be Wine 11

Running everything on Wine 10 was attempted and rejected: under Wine 10 the current Steam client is unusably slow, which made acquisition impractical rather than merely inconvenient. Wine 11.17 provides the two capabilities the download phase needs and Wine 10 does not:

- the current Steam client runs and authenticates, including QR and Steam Guard;
- Steam's CEF UI renders **with GPU acceleration**, so no `-cef-disable-gpu` workaround is needed and the login window is visibly usable.

Wine 11.17 never becomes the gameplay runtime: it reaches Pagonia's visible startup phase but produces neither `Created D3D12Device` nor `Created D3D12 Swapchain`.

## Rejected rationale

Steam cache / LANCache is **not** a reason for this design. It was evaluated and does not deliver a usable speedup here, so the depot is acquired over Steam's normal CDN. Do not reintroduce LANCache as a justification, and do not configure DNS or embed a cache address for it.

## Consequences

- Two Wine versions must never open the same prefix.
- `SteamSetup.exe` runs only under Wine 11; the Wine 10 prefix is seeded from validated snapshots instead.
- A working installation depends on the transferred session being accepted online by Wine 10, which is the one link that has not yet been proven end to end.
