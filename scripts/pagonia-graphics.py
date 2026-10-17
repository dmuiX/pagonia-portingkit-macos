#!/usr/bin/env python3
"""Wine DXVK and GPTK graphics setup for isolated runtimes."""

from pathlib import Path
import hashlib
import shutil


def verify_digest(path: Path, digest: str) -> None:
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError(f"Runtime binary hash mismatch: {path}")

def downloader_graphics(prefix: Path, wine: Path) -> None:
    """Install pinned DXVK and Wine-native DXGI in the downloader only."""
    root = wine.parent / "dxvk"
    for architecture, directory in (("x64", "system32"), ("x32", "syswow64")):
        target = prefix / "drive_c/windows" / directory
        target.mkdir(parents=True, exist_ok=True)
        for name in ("d3d10core.dll", "d3d11.dll"):
            shutil.copy2(root / architecture / name, target / name)
    target = prefix / "drive_c/windows/system32/dxgi.dll"
    source = wine / "lib/wine/x86_64-windows/dxgi.dll"
    data = bytearray(source.read_bytes())
    if len(data) < 80:
        raise ValueError("Invalid DXGI source")
    data[64:80] = bytes.fromhex("0e1fba0e00b409cd21b8014ccd219090")
    target.write_bytes(data)
    verify_digest(target, "f72fe1c82373fe3e2f198df7affb527b0d2117392f5f46577e856efa97a8d024")


def gameplay_graphics(prefix: Path, wine: Path, gptk: Path) -> None:
    """Overlay approved GPTK while preserving Wine 10's pinned D3D12Core."""
    library = wine / "lib"
    core_path = library / "wine/x86_64-windows/d3d12core.dll"
    verify_digest(core_path, "b8cabb79a3f0a14babcbfd575cca70814e4d1d3e71606dfc1670421aaa39b97e")
    core = core_path.read_bytes()
    external = library / "external"
    if external.is_symlink():
        raise ValueError("Linked graphics overlay")
    if external.exists():
        shutil.rmtree(external)
    shutil.copytree(gptk / "external", external, symlinks=True)
    shutil.copytree(gptk / "wine", library / "wine", dirs_exist_ok=True, symlinks=True)
    system = prefix / "drive_c/windows/system32"
    system.mkdir(parents=True, exist_ok=True)
    for name in ("dxgi.dll", "d3d12.dll"):
        shutil.copy2(gptk / "wine/x86_64-windows" / name, system / name)
    (system / "d3d12core.dll").write_bytes(core)
