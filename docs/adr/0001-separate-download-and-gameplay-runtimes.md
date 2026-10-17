# Separate download and gameplay runtimes

Use Wine 11.17 only for the current Steam client, authentication, and acquisition, while the pinned historical Sikarugir Wine 10 runtime remains the sole gameplay runtime. The current Steam client does not work reliably under the validated Wine 10 gameplay environment, while Wine 11.17 does not produce Pagonia's required D3D12 device and swapchain; separate prefixes and a selective transfer preserve both working properties without allowing either Wine version to open the other's prefix.
