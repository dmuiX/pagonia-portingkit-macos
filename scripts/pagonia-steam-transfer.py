#!/usr/bin/env python3
"""Verified Steam download, session capture and game transfer."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
from hashlib import sha256

ROOT=Path(__file__).resolve().parent
STEAM_INSTALLER_URL="https://cdn.akamai.steamstatic.com/client/installer/SteamSetup.exe"
STEAM_INSTALLER_HASH="7d3654531c32d941b8cae81c4137fc542172bfa9635f169cb392f245a0a12bcb"
STEAM_REL=Path("drive_c/Program Files (x86)/Steam")
DEPOT_OPTIONS=[
    "--manifest",str(ROOT/"pagonia-build-25784167-SHA256SUMS"),
    "--expected-app-id","2155180","--expected-build-id","25784167",
    "--expected-file-count","856","--expected-total-size","7672576380",
    "--expected-depot-id","2155181","--expected-depot-manifest-id","839939076860606424",
    "--expected-shared-depot-id","228989","--expected-shared-depot-app-id","228980",
]

def command(*args):
    subprocess.run([sys.executable,str(ROOT/args[0]),*map(str,args[1:])],check=True)

def steam_folder(prefix):
    return prefix/STEAM_REL

def fetch_setup(destination):
    """Only HTTPS Valve downloads are accepted, including redirects."""
    import ssl
    from urllib.parse import urlsplit

    class HttpsRedirects(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, fp, code, message, headers, newurl):
            if urlsplit(newurl).scheme.lower() != "https":
                raise ValueError("SteamSetup redirect must remain HTTPS")
            return super().redirect_request(request, fp, code, message, headers, newurl)

    if destination.exists() or destination.is_symlink():
        raise ValueError("SteamSetup target already exists")
    opener = urllib.request.build_opener(
        HttpsRedirects(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(STEAM_INSTALLER_URL, timeout=90) as response:
            if urlsplit(response.geturl()).scheme.lower() != "https":
                raise ValueError("SteamSetup requires HTTPS")
            digest = sha256()
            with destination.open("xb") as output:
                while data := response.read(1024 * 1024):
                    digest.update(data)
                    output.write(data)
        if digest.hexdigest() != STEAM_INSTALLER_HASH:
            raise ValueError("SteamSetup SHA-256 mismatch")
    except BaseException:
        destination.unlink(missing_ok=True)
        raise

def wait_for_depot(steam,seconds=21600):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        status=subprocess.run([sys.executable,str(ROOT/"pagonia-depot.py"),
            "status",str(steam),*DEPOT_OPTIONS],capture_output=True)
        if status.returncode==0:
            print("  Pagonia depot metadata ready; validating 856 files...",flush=True)
            command("pagonia-depot.py","validate",steam,*DEPOT_OPTIONS)
            return
        remaining=int(end-time.monotonic())
        if remaining%30<=2:
            print("  Waiting for Steam download (remaining seconds:",remaining,")",flush=True)
        time.sleep(3)
    raise TimeoutError("Pagonia depot did not reach the approved build")

def session_and_client(downloader,staging):
    steam=steam_folder(downloader)
    session=staging/"session-snapshot"
    client=staging/"client-snapshot"
    command("pagonia-steam-session.py","create",steam,session)
    command("pagonia-steam-session.py","client-create",steam,client)
    command("pagonia-steam-session.py","validate",session)
    command("pagonia-steam-session.py","client-validate",client)
    return session,client

def transfer(downloader,gameplay,session,client):
    source=steam_folder(downloader)
    target=steam_folder(gameplay)
    target.mkdir(parents=True,exist_ok=True)
    command("pagonia-steam-session.py","client-install",client,target)
    command("pagonia-steam-session.py","install",session,target)
    result=subprocess.run([sys.executable,str(ROOT/"pagonia-steam-session.py"),
                           "steam-id",str(session)],capture_output=True,text=True,check=True)
    steam_id=result.stdout.strip()
    command("pagonia-depot.py","install",source,target,steam_id,*DEPOT_OPTIONS)
    return steam_id
