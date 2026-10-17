#!/usr/bin/env python3
"""Confirm that a Steam connection log completed an online account login."""

from pathlib import Path
import re
import sys


def authenticated(log: Path, account_id: str) -> bool:
    if not re.fullmatch(r"[1-9][0-9]{0,9}", account_id):
        return False
    escaped = re.escape(account_id)
    response = re.compile(
        rf"^.*\[Logging On,(?P<attempt>[^]]*)\] \[U:1:{escaped}\] "
        rf"RecvMsgClientLogOnResponse\(\) : \[U:1:{escaped}\] '(?P<result>[^']+)'$"
    )
    completed = re.compile(
        rf"^.*\[Logged On,(?P<attempt>[^]]*)\] \[U:1:{escaped}\] "
        r"RecvMsgClientLogOnResponse\(\) : processing complete$"
    )
    pending_attempt = None
    logged_on = False
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        response_match = response.fullmatch(line)
        if response_match:
            logged_on = False
            pending_attempt = (
                response_match.group("attempt")
                if response_match.group("result") == "OK"
                else None
            )
            continue
        completed_match = completed.fullmatch(line)
        if completed_match:
            logged_on = False
            if pending_attempt == completed_match.group("attempt"):
                logged_on = True
            pending_attempt = None
    return logged_on


def main() -> int:
    if len(sys.argv) != 3:
        print(f"Usage: {Path(sys.argv[0]).name} CONNECTION_LOG ACCOUNT_ID", file=sys.stderr)
        return 2
    try:
        return 0 if authenticated(Path(sys.argv[1]), sys.argv[2]) else 1
    except OSError:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
