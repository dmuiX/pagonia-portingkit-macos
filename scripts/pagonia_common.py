#!/usr/bin/env python3
"""Shared identity rules for Pagonia installer-managed staging state."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

STAGING_MARKER_NAME = ".pagonia-state.json"
STAGING_SCHEMA = 1
STAGING_KIND = "staging-deployment"
STAGING_OWNER = "pagonia-gptk4b3-installer"
STAGING_PRODUCT = "pioneers-of-pagonia"
STAGING_STATES = ("downloader-incomplete", "depot-complete")


def staging_marker(state: str) -> dict[str, object]:
    """Return the one canonical staging marker representation."""
    if state not in STAGING_STATES:
        raise ValueError(f"Invalid staging state: {state}")
    return {
        "schema": STAGING_SCHEMA,
        "kind": STAGING_KIND,
        "owner": STAGING_OWNER,
        "product": STAGING_PRODUCT,
        "state": state,
    }


def staging_marker_state(value: Any) -> str:
    """Validate the strict canonical staging marker and return its state."""
    if type(value) is not dict:
        raise ValueError("Staging marker must be an object")
    state = value.get("state")
    if type(state) is not str or state not in STAGING_STATES:
        raise ValueError("Invalid staging marker state")
    expected = staging_marker(state)
    if value.keys() != expected.keys() or any(
        type(value[key]) is not type(item) or value[key] != item
        for key, item in expected.items()
    ):
        raise ValueError("Invalid staging marker schema or identity")
    return state


def owner_controlled(path: Path, *, private: bool = False) -> bool:
    """Return whether a non-symlink path is controlled by the current uid."""
    try:
        info = path.lstat()
    except OSError:
        return False
    mode = stat.S_IMODE(info.st_mode)
    return (
        not stat.S_ISLNK(info.st_mode)
        and info.st_uid == os.getuid()
        and mode & 0o022 == 0
        and (not private or mode & 0o077 == 0)
    )
