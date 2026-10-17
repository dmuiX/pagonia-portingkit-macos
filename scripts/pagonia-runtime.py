#!/usr/bin/env python3
"""Isolated Wine runtime extraction and Wineskin app assembly."""
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parent
ARCHIVES={
    "wrapper": ("Wineskin-3.0.6-2.app.tar.xz", 300000000, "Wineskin-3.0.6-2.app"),
    "downloader": ("WineCX-11.17-SteamDownloader-4.7.3.tar.xz", 1500000000, "steam-wine11.bundle"),
    "gameplay": ("WS12WineSikarugir10.0_2-20251028-pagonia.tar.xz", 900000000, "wswine.bundle"),
}

def verified_extract(key, parent):
    from pagonia_preflight import PINS, regular_sha256
    filename, maximum, dirname=ARCHIVES[key]
    archive=ROOT/filename
    if regular_sha256(archive)!=PINS[filename]:
        raise ValueError("Untrusted archive: "+filename)
    subprocess.run([sys.executable,str(ROOT/"pagonia-inputs.py"),"verify-archive",
                    str(archive),"--max-expanded-size",str(maximum)],check=True)
    directory=Path(tempfile.mkdtemp(prefix="verified-",dir=parent))
    subprocess.run(["/usr/bin/tar","-xf",str(archive),"-C",str(directory)],check=True)
    return directory, directory/dirname

def configure(app,name,bundle,flags):
    target=app/"Contents/Info.plist"
    with target.open("rb") as stream:
        info=plistlib.load(stream)
    info.update({"CFBundleName":name,"CFBundleDisplayName":name,
        "CFBundleIdentifier":bundle,"Program Name and Path":"/Program Files (x86)/Steam/steam.exe",
        "Program Flags":flags,"WINEESYNC":0,"WINEMSYNC":0,"WINEFSYNC":0,
        "Symlinks In User Folder":False})
    if name=="Pioneers of Pagonia":
        info.update({"D3DMETAL":1,"D3DMETAL_FORCE":1,
                     "LSEnvironment":{"D3DM_MTL4":"1"}})
    with target.open("wb") as stream:
        plistlib.dump(info,stream)

def build_app(staging,kind):
    if kind not in ("downloader","gameplay"):
        raise ValueError("Unknown runtime")
    app=staging/("Steam Downloader.app" if kind=="downloader" else "Pioneers of Pagonia.app")
    wrapper_dir,wrapper=verified_extract("wrapper",staging)
    try:
        shutil.copytree(wrapper,app,symlinks=True)
    finally:
        shutil.rmtree(wrapper_dir)
    engine_dir,engine=verified_extract(kind,staging)
    shared=app/"Contents/SharedSupport"
    wine=shared/"wine"
    try:
        if kind=="downloader":
            shutil.copytree(engine/"Wine",wine,symlinks=True,dirs_exist_ok=True)
            shutil.copytree(engine/"DXVK",shared/"dxvk",symlinks=True)
        else:
            shutil.copytree(engine,wine,symlinks=True,dirs_exist_ok=True)
            original=wine/"bin/wine"
            if original.exists() and not (wine/"bin/wine64").exists():
                original.rename(wine/"bin/wine64")
    finally:
        shutil.rmtree(engine_dir)
    prefix=shared/"prefix"
    if prefix.is_symlink():
        raise ValueError("Linked prefix")
    if prefix.exists():
        shutil.rmtree(prefix)
    (prefix/"drive_c").mkdir(parents=True,mode=0o700)
    configure(app,"Pagonia Steam Downloader" if kind=="downloader" else "Pioneers of Pagonia",
              "com.soad1337.pagonia.steam-downloader" if kind=="downloader"
              else "com.soad1337.pioneersofpagonia.gptk4b3",
              "-no-cef-sandbox -vgui" if kind=="downloader" else "-applaunch 2155180")
    return app,prefix,wine
