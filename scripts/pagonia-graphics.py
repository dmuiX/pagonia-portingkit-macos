#!/usr/bin/env python3
"""Wine DXVK and GPTK graphics setup for isolated runtimes."""

from pathlib import Path
import hashlib
import shutil


def verify_digest(path: Path, digest: str) -> None:
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError(f"Runtime binary hash mismatch: {path}")
