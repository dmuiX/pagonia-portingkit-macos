# Pioneers of Pagonia unter Porting Kit – Dokumentation

Stand: 17. Oktober 2026
Gerät: MacBook Pro 14" (MacBookPro18,3), Apple M1 Pro, 32 GB RAM
System: macOS 26.3
Ursprünglicher Porting-Kit-Test: 6.7.0
Aktuelles Spiel: Steam-App 2155180, Build 25784167

## Aktueller Status

The earlier GPTK 4.0b2 terrain issue was no longer observed with GPTK/D3DMetal 4.0b3 and the reconstructed historical Wineskin engine. The only currently supported setup is the verified split-runtime installer documented in [`../README.md`](../README.md) and implemented by [`../scripts/install-pagonia-gptk4b3.sh`](../scripts/install-pagonia-gptk4b3.sh).

The former [GPTK 4.0b3 working guide](gptk-4.0b3-working-guide.md) and [German Steam Community post](steam-community-post-de.md) are retained only as historical experiment records. Their `dxil.dll` and game-local `D3D12Core.dll` patching steps must not be applied to the current installer.

The remaining sections likewise document historical states and their investigation.

## 1. Historisches Ergebnis mit GPTK 4.0b2

Pioneers of Pagonia ließ sich unter Porting Kit starten. Folgende Startbarrieren wurden überwunden:

1. GPU-/D3D12-Fähigkeitsprüfung durch D3DMetal 4 und Metal-4-Backend.
2. Fehlendes `D3D12GetInterface` durch `-NoDX12DeviceFactory`.
3. Agility-SDK-/D3D12Core-Präsenzprüfung durch einen zusätzlichen Import in `dxil.dll`.

Das Spiel startete und lud Spielstände. Unter Beta 2 war es trotzdem praktisch nicht spielbar, weil Terrain/Boden unter D3DMetal fehlerhaft beziehungsweise teilweise gar nicht gerendert wurde.

## 2. Porting-Kit-Port

Anwendung:

```text
/Applications/Pioneers of Pagonia.app
```

Der Port wurde als eigenständige Kopie einer bereits funktionierenden Porting-Kit-Steam-Bottle angelegt. Die GTA-Spieldateien und ein versehentlich eingebetteter Benutzer-Cache wurden beim Kopieren ausgeschlossen.

Der Port wurde zusätzlich in folgender Porting-Kit-Datei als lokale Anwendung registriert:

```text
~/Library/Application Support/portingkit/userData.json
```

Sicherung der vorherigen Datei:

```text
~/Library/Application Support/portingkit/userData.json.backup-before-pagonia
```

## 3. Wrapper-Konfiguration

Geändert wurde:

```text
/Applications/Pioneers of Pagonia.app/Contents/Info.plist
```

Wichtige Werte:

```text
CFBundleName = Pioneers of Pagonia
CFBundleIdentifier = com.soad1337.pioneersofpagonia.portingkit
Program Name and Path = /Program Files (x86)/Steam/steam.exe
Program Flags = -applaunch 2155180 -NoDX12DeviceFactory
D3DMETAL = 1
D3DMETAL_FORCE = 1
```

Das globale Metal-4-Backend wurde aktiviert mit:

```bash
launchctl setenv D3DM_MTL4 1
```

Kontrolle:

```bash
launchctl getenv D3DM_MTL4
```

Erwarteter Wert:

```text
1
```

## 4. GPTK-/D3DMetal-Overlay

Verwendet wurde:

```text
Evaluation environment for Windows games 4.0 beta 2
D3DMetal 4.0b2
```

Quelle:

```text
/Volumes/Evaluation environment for Windows games 4.0 beta 2/redist/lib
```

Ziel:

```text
/Applications/Pioneers of Pagonia.app/Contents/SharedSupport/wine/lib
```

Vorgehen:

```bash
mv external external.portingkit-2.1-backup
ditto GPTK-4.0b2/redist/lib/external external
ditto GPTK-4.0b2/redist/lib/wine wine
```

Wichtig: Der bestehende `wine`-Ordner wurde nur überlagert, nicht vollständig ersetzt. Dadurch bleiben Porting-Kit-spezifische Dateien wie `ntdll.so` erhalten.

Sicherung der vorherigen D3DMetal-Version 2.1:

```text
/Applications/Pioneers of Pagonia.app/Contents/SharedSupport/wine/lib/external.portingkit-2.1-backup
```

Installierte D3DMetal-Kennung:

```text
@(#)PROGRAM:D3DMetal  PROJECT:D3DMetal-4.0b2
```

## 5. Steam-Installation

Pagonia wurde innerhalb des separaten Ports über folgende Steam-URI installiert:

```text
steam://install/2155180
```

Danach wurde der Wrapper wieder auf den normalen Spielstart gesetzt:

```text
-applaunch 2155180 -NoDX12DeviceFactory
```

Installationsstatus:

```text
StateFlags = 4
BuildID = 24071646
BytesDownloaded = 6035121424
```

Spielverzeichnis:

```text
/Applications/Pioneers of Pagonia.app/Contents/SharedSupport/prefix/drive_c/Program Files (x86)/Steam/steamapps/common/Pioneers of Pagonia
```

## 6. Agility-SDK-/D3D12Core-Patch

### 6.1 Ausgangsfehler

Nach dem Start erschien:

```text
DirectX 12 Agility SDK could not be loaded.
Please update your Operating System to Windows 10 Version 1909 or newer.
```

Das war keine echte Betriebssystemmeldung. D3DMetal stellte bereits ein D3D12-Gerät bereit, lud aber Paganias lokale Agility-Runtime nicht. Paganias Prüfung auf ein geladenes `D3D12Core`-Modul schlug deshalb fehl.

### 6.2 Windows-Buildnummer

In folgender Datei wurden alle Vorkommen von Build 19043 auf 19045 geändert:

```text
/Applications/Pioneers of Pagonia.app/Contents/SharedSupport/prefix/system.reg
```

Werte:

```text
CurrentBuild = 19045
CurrentBuildNumber = 19045
```

### 6.3 D3D12Core neben der Spiel-EXE

Kopiert wurde:

```text
D3D12/D3D12Core.dll
```

nach:

```text
D3D12Core.dll
```

im Hauptverzeichnis des Spiels.

SHA-256 der verwendeten `D3D12Core.dll`:

```text
625bd40005b1c3708695d5256ecf230d278e6b8edba5a88af70f3d91324f3052
```

### 6.4 DLL-Overrides

In folgender Datei wurden Einträge ergänzt:

```text
/Applications/Pioneers of Pagonia.app/Contents/SharedSupport/prefix/user.reg
```

Einträge:

```text
"*d3d12"="native,builtin"
"*dxgi"="native,builtin"
"*d3d12core"="native,builtin"
```

Zusätzlich wurden die GPTK-4.0b2-Versionen von `dxgi.dll` und `d3d12.dll` aus dem Wine-Engine-Verzeichnis nach `windows/system32` kopiert.

### 6.5 Statischer Import in dxil.dll

Geänderte Datei:

```text
Pioneers of Pagonia/dxil.dll
```

Ergänzter Import:

```text
D3D12Core.dll!D3D12SDKVersion
```

Technische Umsetzung:

1. Die vorhandenen zehn `IMAGE_IMPORT_DESCRIPTOR`-Einträge wurden bytegenau gelesen.
2. In der bereits vorhandenen Null-Auffüllung am Ende der `.rdata`-Sektion wurde eine neue Importtabelle angelegt.
3. Alle zehn ursprünglichen Deskriptoren wurden unverändert übernommen.
4. Ein elfter Deskriptor für `D3D12Core.dll` wurde angehängt.
5. Danach folgen ein Null-Deskriptor, Import Lookup Table, Import Address Table, DLL-Name und Symbolname.
6. Die PE-Import-Directory-Adresse wurde von `0x1456fc` auf `0x1466a0` gesetzt.
7. Alle ursprünglichen IAT-Adressen blieben unverändert.
8. Es wurde keine neue PE-Sektion angelegt und die bestehende Raw-Section-Größe wurde nicht verändert.

Importprüfung nach dem Patch:

```text
D3D12Core.dll -> D3D12SDKVersion
```

SHA-256 der gepatchten `dxil.dll`:

```text
844f55227c67036f9466f25f655ee9156355cac04de21a35b230579649010190
```

Dieser Import zwingt den Windows-Loader, `D3D12Core.dll` zu laden und referenziert zu halten. Dadurch besteht das Spiel seinen D3D12Core-Präsenzcheck.

### 6.6 Sicherung vor dem Patch

Komplette Sicherung der betroffenen Dateien:

```text
/Applications/Pioneers of Pagonia.app/Contents/SharedSupport/Pagonia-patch-backup-20260826-143512
```

Enthalten sind:

```text
game/dxil.dll
system32/dxgi.dll
system32/d3d12.dll
wine/dxgi.dll
wine/d3d12.dll
system.reg
user.reg
```

## 7. Terrain-Minimaltest

Ein Minimalprofil wurde getestet, um optionale Grafikstufen als Ursache auszuschließen. Der Test ist abgeschlossen; die ursprünglichen Einstellungen und der Shadercache sind wiederhergestellt.

Geänderte Datei:

```text
prefix/drive_c/users/Wineskin/AppData/Local/Pioneers of Pagonia/settings.ini
```

Aktive Testwerte:

```text
AAQUALITY=0
ANIMATIONQUALITY=0
BLOOM=False
DISTANCEFOGQUALITY=0
FSR1=0
GRASS=False
LIGHTING QUALITY=0
SHADOWMAPQUALITY=0
TERRAINQUALITY=0
TEXTUREFILTERQUALITY=0
TEXTUREQUALITY=0
VIEW DISTANCE=150
LOD=0
SSAOQUALITY=0
```

Der Steam-Shadercache für App 2155180 wurde nicht gelöscht, sondern in das Test-Backup verschoben.

Sicherung:

```text
/Applications/Pioneers of Pagonia.app/Contents/SharedSupport/Pagonia-render-test-20260826-144555
```

Enthalten:

```text
settings.ini.original
shadercache-2155180.original/
launcher.log
```

### Ursprüngliche relevante Grafikwerte

```text
BLOOM=True
DISTANCEFOGQUALITY=1
FSR1=1
GRASS=True
LIGHTING QUALITY=3
SHADOWMAPQUALITY=2
TERRAINQUALITY=2
TEXTUREFILTERQUALITY=4
TEXTUREQUALITY=0
VIEW DISTANCE=650
LOD=2
SSAOQUALITY=1
```

## 8. Wiederherstellung der ursprünglichen Grafikoptionen

Spiel und Steam im Pagonia-Port zuerst beenden. Danach:

```bash
APP='/Applications/Pioneers of Pagonia.app'
TEST="$APP/Contents/SharedSupport/Pagonia-render-test-20260826-144555"
PFX="$APP/Contents/SharedSupport/prefix"

cp -p "$TEST/settings.ini.original" \
  "$PFX/drive_c/users/Wineskin/AppData/Local/Pioneers of Pagonia/settings.ini"

rm -rf "$PFX/drive_c/Program Files (x86)/Steam/steamapps/shadercache/2155180"
cp -a "$TEST/shadercache-2155180.original" \
  "$PFX/drive_c/Program Files (x86)/Steam/steamapps/shadercache/2155180"
```

## 9. Wichtige Update-Hinweise

Folgende Aktionen können den Patch überschreiben:

- Steam: „Dateien auf Fehler überprüfen“
- ein Pagonia-Update, das `dxil.dll` ersetzt
- Neuinstallation des Spiels

Das erkennt man daran, dass wieder die Agility-SDK-/Windows-1909-Meldung erscheint. Dann muss der Importpatch auf die neue `dxil.dll` erneut angewendet werden. Eine alte gepatchte DLL sollte nach einem Spielupdate nicht blind zurückkopiert werden, weil sich die DLL-Version geändert haben kann.

Ein GPTK-/Porting-Kit-Update kann außerdem das D3DMetal-Overlay ersetzen. Danach muss geprüft werden, welche D3DMetal-Version tatsächlich aktiv ist.

## 10. D3DMetal-Diagnose und Vergleichstests

### 10.1 Historisch mit D3DMetal 4.0b2 reproduzierte Renderzustände

- Historischer Beta-2-Zustand: Gebäude, Einheiten, Wasser und UI werden gerendert; Terrain/Bodenmaterial und Gras fehlen.
- Das spielinterne Vorschauvideo im Menü ist vollständig weiß. Dieser Zustand bestand bereits vor den Diagnosetests.
- Beim früheren Cache-/Minimalprofiltest verschwand zeitweise fast die gesamte Szene. Nach Wiederherstellung der Einstellungen und des Shadercaches trat wieder der ursprüngliche Zustand ein.

### 10.2 Pipeline-Compilerfehler unter D3DMetal 4.0b2

Mit folgenden Diagnosevariablen wurde der Fehler im Unified Log sichtbar gemacht:

```text
D3DM_LOGLEVEL_INFO=1
D3DM_DXIL_PROCESS_DEBUG_INFORMATION=1
MTL_DEBUG_LAYER=1
```

D3DMetal meldet wiederholt. Mit `OS_ACTIVITY_DT_MODE=YES` konnten die zuvor als `<private>` maskierten Argumente sichtbar gemacht werden:

```text
[ExtractDXILFunctions:1814][ERROR]
Compilation of function 'irconverter_hull_shader' failed with
Error Domain=MTLLibraryErrorDomain Code=3 "Failed to materializeAll."

[D3DMGraphicsPipelineState:347][ERROR]
Failed to compile a pipeline, marking PSO(...) as no-op
```

Damit ist präzisiert: Apples IRConverter scheitert beim Materialisieren von Paganias D3D12-Hull-Shadern. Diese Shader bilden den Tessellationspfad des Terrains.

Je nach Start und Reihenfolge der Pipelineerzeugung wurden mindestens folgende Pipeline-State-Objects als No-op ersetzt:

```text
115, 119, 140, 155, 156, 158, 161, 165, 169, 171,
177, 185, 186, 188, 189, 190, 191, 192, 193, 194, 227, 228
```

Damit ist die unmittelbare technische Ursache des fehlenden Renderings nachgewiesen: D3DMetal kann mehrere DXIL-Funktionen nicht in Metal kompilieren und verwirft die betroffenen Draw-Pipelines vollständig. Das passt zu den im Spiel enthaltenen Terrain-Pipeline-Namen, unter anderem:

```text
D3D12PhoenixTerrainMaterialPipeline
D3D12PhoenixTerrainMeadowsMaterialPipeline
D3D12PhoenixTerrainMeadowsGeneratorMaterialPipeline
D3D12PhoenixTerrainDecalMaterialPipeline
```

Eine direkte Zuordnung der internen PSO-Nummern zu diesen Namen ist in den verfügbaren Spiel-Logs nicht enthalten.

Die Editor-Assembly `Editor/MaterialLib.dll` enthält eingebettete HLSL-/DXBC-/DXIL-Ressourcen, darunter `PhoenixTerrain.shaderobj` und die Funktionen `CalculateTessellationFactors`. Die Spiel-EXE ist jedoch eine native, symbolbereinigte x64-Datei und bindet ihre Runtime-Daten separat ein. Sie enthält zwar Namen wie `CheckForTessellation`, aber ohne sichere Code-Referenz. Ein Blindpatch der EXE oder der Editor-DLL ist daher kein belastbarer Fix.

### 10.3 Metal-4-A/B-Test

D3DMetal 4.0b2 wurde sowohl mit `D3DM_MTL4=1` als auch mit vollständig entfernter Variable gestartet. In beiden Fällen bleiben das spielinterne Vorschauvideo weiß und Boden sowie Gras fehlen. Der Fehler ist daher nicht allein auf den neuen Metal-4-Schalter beschränkt.

Die globale Standardeinstellung wurde anschließend wiederhergestellt:

```text
D3DM_MTL4=1
```

### 10.4 Diagnosedaten

Die Mitschnitte liegen unter:

```text
/Applications/Pioneers of Pagonia.app/Contents/SharedSupport/Pagonia-diagnostics/
```

Wichtiger Lauf:

```text
4.0b2-metal-validation-20260826-152128
```

### 10.5 Linux-/vkd3d-proton-Referenz

Nach einem Neustart des Linux-Hosts wurde Pagonia mit Proton Hotfix und vkd3d-proton protokolliert:

```text
vkd3d-proton 3.1.0
build 66da249279ea280
GPU: AMD Radeon Graphics (RADV RENOIR)
Mesa/RADV 25.0.7
```

vkd3d-proton erkennt das Spiel automatisch:

```text
Detected game Pioneers of Pagonia.exe, adding shader quirks for specific shaders.
```

Im vkd3d-proton-Quellcode ist Pagonia fest dem Workaround `VKD3D_SHADER_QUIRK_DESCRIPTOR_HEAP_ROBUSTNESS` zugeordnet. Dieser schützt vor einem bekannten fehlerhaften Descriptor-Zugriff des Spiels, der auf RADV GPU-Hänger verursachen kann. Er ist vom D3DMetal-Hull-Shaderfehler zu unterscheiden.

Der Benutzer bestätigte visuell: Boden, Terrain und Gras werden unter Linux vollständig und korrekt gerendert. Im Log erscheinen keine Hull-Shader- oder Grafikpipeline-Compilerfehler. Damit ist belegt, dass Paganias Shader grundsätzlich übersetzbar sind und der fehlende Boden auf dem Mac spezifisch im D3DMetal-/IRConverter-Pfad entsteht.

Gesicherter Logauszug:

```text
/Users/admin/Projects/pagonia-portingkit-macos/analysis/linux-vkd3d-reference-20260826.log
```

### 10.6 vkd3d-proton/MoltenVK-Test auf macOS

Für diesen Versuch wurde eine getrennte APFS-Kopie angelegt:

```text
/Applications/Pioneers of Pagonia VKD3D.app
```

Der Originalport blieb unverändert. In der Testkopie wurden D3DMetal deaktiviert und die x64-DLLs von Proton Hotfix installiert:

- vkd3d-proton 3.1.0: `d3d12.dll`, `d3d12core.dll`
- DXVK 3.0.2: `dxgi.dll`
- MoltenVK zunächst 1.2.5 aus Porting Kit, danach offizielles MoltenVK 1.4.2

Ergebnisse:

1. MoltenVK 1.2.5 meldet nur Vulkan 1.2; DXVK 3 verlangt Vulkan 1.3 und lehnt den Adapter ab.
2. MoltenVK 1.4.2 erfüllt Vulkan 1.3, unterstützt auf Apple Metal aber keine nativen Geometry Shader. Standard-DXVK lehnt den Adapter mit `Device does not support required feature 'geometryShader'` ab.
3. Ein lokaler DXVK-3.0.2-Testbuild machte `geometryShader` optional. Danach fehlte als nächste Pflichtfunktion `shaderCullDistance`.
4. Ein letzter Diagnosebuild machte alle pauschalen DXVK-Adapterpflichten optional. Damit wurde der Apple-M1-Pro-Adapter erkannt, Steam blieb jedoch vor dem Start von App 2155180 hängen. Pagonia erreichte vkd3d-proton nicht; es wurde kein D3D12-Gerät des Spiels erstellt.

Der Pfad

```text
D3D12 → vkd3d-proton → Vulkan → MoltenVK → Metal
```

ist mit den derzeit verfügbaren Standardkomponenten daher nicht praktikabel. Metal/MoltenVK fehlen Funktionen, die DXVK beziehungsweise eine vollständige D3D12-Kompatibilitätsschicht voraussetzen. Das Abschalten der Prüfungen erzeugt keine fehlenden GPU-Funktionen und ist kein nutzbarer Workaround.

Backups und Logs liegen ausschließlich in der VKD3D-Testkopie unter:

```text
Contents/SharedSupport/Pagonia-vkd3d-test-backup-20260826-161217
Contents/SharedSupport/Pagonia-vkd3d-diagnostics
```

Alle lokalen Testprozesse wurden beendet. `D3DM_MTL4=1` wurde global wiederhergestellt.

### 10.7 Zum Zeitpunkt des Beta-2-Berichts noch ausstehend

1. Eine zukünftige D3DMetal-Version auf eine Korrektur von `irconverter_hull_shader` / `Failed to materializeAll` testen. Dieser Test wurde am 16. Oktober 2026 mit D3DMetal 4.0b3 erfolgreich durchgeführt; see the [archived experiment record](gptk-4.0b3-working-guide.md) for historical evidence and the [repository README](../README.md) for the current supported installer.
2. Optional einen vom Spieleentwickler bereitgestellten Non-Tessellation-Terrainpfad testen.

D3DMetal 4.0b1 war für den historischen Vergleich nicht mehr verfügbar.

## 11. steam-headless-Zustand

Auf `nasadmin@192.168.1.5` wurde bestätigt:

- Pagonia ist vollständig installiert.
- App 2155180, Build 24071646, `StateFlags=4`.
- GPU: AMD Cezanne / Radeon Vega 8.
- Spielgröße: etwa 6,8 GB.

Ein früherer Lauf verursachte einen globalen AMDGPU-Hänger:

```text
amdgpu: ring comp_1.1.1 timeout
process GameThread
thread dxvk-submit
```

Der Host wurde anschließend vom Benutzer neu gestartet. Danach funktionieren AMDGPU, Xorg `:55`, VNC/Sunshine, Vulkan und `docker exec` wieder. vkd3d-proton 3.1.0 aktiviert inzwischen automatisch den Pagonia-spezifischen Descriptor-Heap-Robustness-Workaround, der genau solche RADV-Hänger verhindern soll.

Containerstarts und -stopps erfolgen ausschließlich durch den Benutzer über OMV; Diagnosezugriffe sind auf ausdrücklich erlaubtes `docker exec` beschränkt.

## 12. Quelle des Workarounds

Steam-Diskussion:

```text
https://steamcommunity.com/app/2155180/discussions/0/3758852882969018374/?ctp=5
```

Entscheidende Erkenntnisse:

- Entwickleroption `-NoDX12DeviceFactory`
- D3DMetal lädt die lokale Agility-Runtime nicht automatisch
- `D3D12Core.dll` muss im Prozess präsent sein
- Import in `dxil.dll` ist sicherer als Import in EXE oder D3DMetal-`d3d12.dll`
- Terrainfehler sind ein von der Startproblematik unabhängiger D3DMetal-Übersetzungsfehler
