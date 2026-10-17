#!/usr/bin/env python3
"""Prove that an on-screen Steam window has visible, non-black pixels."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
WINDOW_IDS = r'''
import CoreGraphics
let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as! [[String: Any]]
for item in windows {
    let owner = item[kCGWindowOwnerName as String] as? String ?? ""
    let name = item[kCGWindowName as String] as? String ?? ""
    if owner == "wine" && (name == "Sign in to Steam" || name == "Steam") {
        print(item[kCGWindowNumber as String]!)
    }
}
'''


def visible_window() -> bool:
    listing = subprocess.run(["/usr/bin/swift", "-e", WINDOW_IDS],
                             capture_output=True, text=True, timeout=40, check=True)
    ids = [value for value in listing.stdout.splitlines() if re.fullmatch(r"[0-9]+", value)]
    for window_id in ids:
        with tempfile.TemporaryDirectory(prefix="pagonia-window-", dir="/private/tmp") as temp:
            os.chmod(temp, 0o700)
            png, bmp = Path(temp) / "window.png", Path(temp) / "window.bmp"
            grab = subprocess.run(["/usr/sbin/screencapture", "-x", "-l", window_id, str(png)],
                                  capture_output=True, timeout=15)
            if grab.returncode:
                continue
            convert = subprocess.run(["/usr/bin/sips", "-s", "format", "bmp",
                                      str(png), "--out", str(bmp)],
                                     capture_output=True, timeout=15)
            if convert.returncode:
                continue
            check = subprocess.run([sys.executable, str(ROOT / "check-steam-window-bmp.py"),
                                    str(bmp)], timeout=15)
            if check.returncode == 0:
                return True
    return False


def wait_for_window(steam_root: Path, timeout: int = 180) -> None:
    # Screen capture access can change between Fresh and Resume.
    permission = subprocess.run(
        ["/usr/bin/swift", "-e",
         "import CoreGraphics; import Darwin; exit(CGPreflightScreenCaptureAccess() ? 0 : 1)"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    if permission.returncode:
        raise RuntimeError("Terminal needs Screen Recording permission for Steam UI verification")
    log = steam_root / "logs/steamui_html.txt"
    deadline = time.monotonic() + timeout
    last_status = time.monotonic()
    while time.monotonic() < deadline:
        if log.exists() and "Timed out waiting for webhelper init" in log.read_text(errors="replace"):
            raise RuntimeError("Steam webhelper timed out")
        if visible_window():
            print("  Steam UI is visibly rendered.", flush=True)
            return
        if time.monotonic() - last_status >= 25:
            print("  Waiting for visible Steam login window...", flush=True)
            last_status = time.monotonic()
        time.sleep(2)
    raise TimeoutError("Steam login window was not visibly rendered")
