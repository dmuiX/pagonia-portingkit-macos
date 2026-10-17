#!/usr/bin/env python3
"""Regression tests for Steam online-login log acceptance."""

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/check-steam-login-log.py"
ACCOUNT_ID = "27114796"
ACCEPTED = (
    "[Logging On, 4, 7] [U:1:27114796] "
    "RecvMsgClientLogOnResponse() : [U:1:27114796] 'OK'"
)
COMPLETED = (
    "[Logged On, 4, 7] [U:1:27114796] "
    "RecvMsgClientLogOnResponse() : processing complete"
)


def accepts(path: Path) -> bool:
    return subprocess.run(
        ["python3", str(CHECKER), str(path), ACCOUNT_ID], check=False
    ).returncode == 0


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        log = Path(directory) / "connection_log.txt"
        log.write_text(ACCEPTED + "\n")
        assert not accepts(log)
        log.write_text(COMPLETED + "\n")
        assert not accepts(log)
        log.write_text(ACCEPTED + " trailing failure\n" + COMPLETED + "\n")
        assert not accepts(log)
        log.write_text(COMPLETED + "\n" + ACCEPTED + "\n")
        assert not accepts(log)
        cross_attempt = COMPLETED.replace("4, 7", "4, 2")
        log.write_text(ACCEPTED + "\n" + cross_attempt + "\n")
        assert not accepts(log)
        later_mismatched_completion = COMPLETED.replace("4, 7", "4, 2")
        log.write_text(
            ACCEPTED + "\n" + COMPLETED + "\n" + later_mismatched_completion + "\n"
        )
        assert not accepts(log)
        failed_new_attempt = ACCEPTED.replace("4, 7", "4, 2").replace("'OK'", "'Fail'")
        log.write_text(ACCEPTED + "\n" + COMPLETED + "\n" + failed_new_attempt + "\n")
        assert not accepts(log)
        log.write_text(
            "[2026-10-17 12:00:00] " + ACCEPTED + "\n"
            "[2026-10-17 12:00:00] " + COMPLETED + "\n"
        )
        assert accepts(log)
        assert subprocess.run(
            ["python3", str(CHECKER), str(log), "invalid"], check=False
        ).returncode != 0


if __name__ == "__main__":
    main()
