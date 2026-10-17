#!/usr/bin/env python3
"""Behavior tests for immutable input, archive, and runtime verification."""

from __future__ import annotations

from hashlib import sha256
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/pagonia-inputs.py"


def run(*arguments: object, success: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["python3", str(HELPER), *(str(argument) for argument in arguments)],
        check=False,
        text=True,
        capture_output=True,
    )
    if success and result.returncode != 0:
        raise AssertionError(result.stderr)
    if not success and result.returncode == 0:
        raise AssertionError("Command unexpectedly succeeded")
    return result


def add_file(archive: tarfile.TarFile, name: str, data: bytes = b"payload\n") -> None:
    entry = tarfile.TarInfo(name)
    entry.size = len(data)
    archive.addfile(entry, io.BytesIO(data))


def add_entry(
    archive: tarfile.TarFile,
    name: str,
    entry_type: bytes,
    target: str = "",
) -> None:
    entry = tarfile.TarInfo(name)
    entry.type = entry_type
    entry.linkname = target
    archive.addfile(entry)


def make_archive(path: Path, entries) -> None:
    with tarfile.open(path, "w") as archive:
        for entry in entries:
            entry(archive)


def digest(value: bytes) -> str:
    return sha256(value).hexdigest()


def write_runtime_manifest(path: Path, entries: list[tuple[str, bytes, str]]) -> None:
    path.write_text(
        "".join(f"{kind} {digest(value)}  {relative}\n" for kind, value, relative in entries),
        encoding="utf-8",
    )


def main() -> None:
    # verify-file accepts only the exact, owner-controlled regular file requested.
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        input_file = root / "input.bin"
        input_file.write_bytes(b"trusted input\n")
        expected = digest(b"trusted input\n")
        assert run("verify-file", expected, input_file).stdout.strip() == "verified file"
        run("verify-file", "0" * 64, input_file, success=False)
        linked = root / "linked"
        linked.symlink_to(input_file)
        run("verify-file", expected, linked, success=False)
        hardlink = root / "hardlink"
        hardlink.hardlink_to(input_file)
        run("verify-file", expected, input_file, success=False)

    # A safe archive is inspected without extraction and bounded by expanded bytes.
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        archive_path = root / "safe.tar"
        make_archive(
            archive_path,
            [
                lambda archive: add_entry(archive, "Runtime", tarfile.DIRTYPE),
                lambda archive: add_file(archive, "Runtime/bin/wine", b"wine"),
                lambda archive: add_entry(
                    archive, "Runtime/bin/wine64", tarfile.SYMTYPE, "wine"
                ),
                lambda archive: add_entry(
                    archive, "Runtime/bin/wine-copy", tarfile.LNKTYPE, "Runtime/bin/wine"
                ),
            ],
        )
        assert run(
            "verify-archive", archive_path, "--max-expanded-size", 4
        ).stdout.strip() == "verified archive (4 expanded bytes)"
        run("verify-archive", archive_path, "--max-expanded-size", 3, success=False)

    # Archive names, entry types, links, and normalized identities fail closed.
    unsafe_archives = [
        ("absolute", lambda archive: add_file(archive, "/etc/passwd")),
        ("traversal", lambda archive: add_file(archive, "Runtime/../escape")),
        (
            "duplicate",
            lambda archive: (
                add_file(archive, "Runtime/file", b"one"),
                add_file(archive, "Runtime/file", b"two"),
            ),
        ),
        (
            "device",
            lambda archive: add_entry(archive, "Runtime/device", tarfile.CHRTYPE),
        ),
        (
            "absolute-link",
            lambda archive: add_entry(
                archive, "Runtime/link", tarfile.SYMTYPE, "/private/tmp/escape"
            ),
        ),
        (
            "traversing-link",
            lambda archive: add_entry(
                archive, "Runtime/link", tarfile.SYMTYPE, "../../escape"
            ),
        ),
        (
            "missing-hardlink-target",
            lambda archive: add_entry(
                archive, "Runtime/link", tarfile.LNKTYPE, "Runtime/missing"
            ),
        ),
        (
            "late-nondirectory-parent",
            lambda archive: (
                add_file(archive, "Runtime/bin/wine"),
                add_file(archive, "Runtime/bin"),
            ),
        ),
    ]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for name, entry in unsafe_archives:
            archive_path = root / f"{name}.tar"
            make_archive(archive_path, [entry])
            run(
                "verify-archive",
                archive_path,
                "--max-expanded-size",
                1024,
                success=False,
            )

    # Runtime manifests distinguish files from symlinks and require an exact inventory.
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        runtime = base / "Runtime"
        (runtime / "bin").mkdir(parents=True)
        (runtime / "bin/wine").write_bytes(b"wine runtime\n")
        (runtime / "bin/wine64").symlink_to("wine")
        manifest = base / "runtime.manifest"
        entries = [
            ("file", b"wine runtime\n", "bin/wine"),
            ("symlink", b"wine", "bin/wine64"),
        ]
        write_runtime_manifest(manifest, entries)
        assert run("verify-runtime", manifest, runtime).stdout.strip() == (
            "verified runtime (2 entries)"
        )

        (runtime / "unexpected").write_bytes(b"extra")
        run("verify-runtime", manifest, runtime, success=False)
        (runtime / "unexpected").unlink()
        (runtime / "bin/wine").write_bytes(b"tampered")
        run("verify-runtime", manifest, runtime, success=False)

    # Unsafe runtime links, hardlinks, special entries, and malformed manifests fail.
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        runtime = base / "Runtime"
        runtime.mkdir()
        manifest = base / "runtime.manifest"

        (runtime / "escape").symlink_to("../outside")
        write_runtime_manifest(manifest, [("symlink", b"../outside", "escape")])
        run("verify-runtime", manifest, runtime, success=False)
        (runtime / "escape").unlink()

        (runtime / "file").write_bytes(b"data")
        (base / "other-link").hardlink_to(runtime / "file")
        write_runtime_manifest(manifest, [("file", b"data", "file")])
        run("verify-runtime", manifest, runtime, success=False)
        (base / "other-link").unlink()
        (runtime / "file").unlink()

        os.mkfifo(runtime / "fifo")
        manifest.write_text("", encoding="utf-8")
        run("verify-runtime", manifest, runtime, success=False)
        (runtime / "fifo").unlink()

        (runtime / "file").write_bytes(b"data")
        manifest.write_text(
            f"file {digest(b'data')}  file\nfile {digest(b'data')}  file\n",
            encoding="utf-8",
        )
        run("verify-runtime", manifest, runtime, success=False)


if __name__ == "__main__":
    main()
