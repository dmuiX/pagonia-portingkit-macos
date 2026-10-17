# Steam-Community-Beitrag: Pioneers of Pagonia läuft auf Apple Silicon mit GPTK 4.0b3

Stand: 16.10.2026

> **Archived draft.** Its manual `dxil.dll` and game-local `D3D12Core.dll`
> instructions are obsolete and must not be combined with the current
> split-runtime installer. Use the repository root `README.md` instead.

## Titel

**[macOS/Apple Silicon] Pioneers of Pagonia läuft mit GPTK 4.0 Beta 3 – inklusive Terrain**

## Fertiger Beitrag

Nach ziemlich viel Fehlersuche läuft Pioneers of Pagonia bei mir jetzt unter macOS auf einem M1 Pro über Wine und Apples Game Porting Toolkit 4.0 Beta 3.

**Getestet mit:**

- MacBook Pro 14 Zoll, M1 Pro, 32 GB
- macOS 26.3
- Steam-Build 25784167 von Pioneers of Pagonia
- D3DMetal 4.0b3 mit Metal-4-Backend
- älterem Sikarugir-10.0-Wineskin-Build

Das Spiel startet über Steam, lädt Spielstände und gelangt in die Spielwelt. Im Log werden erfolgreich ein D3D12-Gerät und eine Swapchain erzeugt:

```text
Created D3D12Device
Created D3D12 Swapchain
```

### Warum das erwähnenswert ist

Mit GPTK 4.0 Beta 2 startete das Spiel zwar bereits, aber der Boden beziehungsweise das Terrain wurde nicht korrekt gerendert. D3DMetal meldete dabei reproduzierbar:

```text
irconverter_hull_shader: Failed to materializeAll
Failed to compile a pipeline, marking PSO(...) as no-op
```

Betroffen waren offenbar Paganias Hull-/Tessellation-Shader für das Terrain. Beim aktuellen Lauf mit Beta 3 sind diese Meldungen bislang nicht mehr aufgetreten und die Spielwelt funktioniert.

### Die entscheidende Besonderheit

Nicht jede Wine-Version mit der Bezeichnung „Wine 10.0“ funktioniert. Ein neuerer Sikarugir-10.0.3-Build führte bei mir entweder zu einem nativen Page-Fault oder zum WineD3D-Fallback mit einer angeblichen „NVIDIA GeForce 6800“.

Funktioniert hat erst die vollständige Wine-/Wineskin-Engine aus einer älteren, bereits funktionierenden Porting-Kit-Bottle. Obwohl beide Engines ähnlich heißen, unterscheiden sich `wine64`, `ntdll`, der Mac-Treiber und weitere Module binär. Der komplette Wrapper ist offenbar für die korrekte GPTK-Integration wichtig.

### Benötigte Anpassungen

In Kurzform:

1. kompatiblen älteren Wineskin-/Sikarugir-10.0-Wrapper verwenden;
2. GPTK 4.0b3 als Overlay in den bestehenden Wine-Ordner kopieren, ohne die Engine-spezifischen Dateien zu löschen;
3. `D3DMETAL=1`, `D3DMETAL_FORCE=1` und `D3DM_MTL4=1` setzen;
4. Windows-Buildnummer auf `19045` setzen;
5. GPTK-`dxgi.dll` und `d3d12.dll` verwenden;
6. Paganias `D3D12Core.dll` neben die Spiel-EXE kopieren;
7. `dxil.dll` so patchen, dass `D3D12Core.dll!D3D12SDKVersion` statisch importiert wird;
8. Steam mit `-applaunch 2155180 -NoDX12DeviceFactory` starten.

**Wichtig:** Das ist eine experimentelle und nicht offiziell unterstützte Konfiguration. Der `dxil.dll`-Patch ist versionsabhängig und darf nach einem Spielupdate nicht blind erneut verwendet werden. Steam-Dateiprüfung, Spielupdates, Wine-Updates oder neue GPTK-Versionen können den funktionierenden Zustand überschreiben.

Außerdem dürfen Apples GPTK-Dateien, Steam-Anmeldedaten und Spieldateien natürlich nicht weitergegeben werden. GPTK muss legal über Apple bezogen werden.

Ich dokumentiere den Aufbau mit Hashes und Wiederherstellungsschritten, damit klar ist, welche Engine tatsächlich funktioniert. Entscheidend war am Ende nicht einfach „Wine 10“, sondern die exakte Kombination aus Wineskin-Launcher, Wine-Patchstand, D3DMetal und DLL-Ladereihenfolge.

Falls jemand dasselbe testet, bitte immer Mac-Modell, macOS-Version, Pagonia-Build, GPTK-Version und den exakten Wine-Build nennen. Nur die Ausgabe von `wine --version` reicht für einen belastbaren Vergleich nicht aus.
