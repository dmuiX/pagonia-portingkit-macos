#!/usr/bin/env python3
"""Set Pagonia launch options in the transferred account's Steam localconfig."""

from __future__ import annotations

from pathlib import Path
import re

STEAM_BASE = 76561197960265728
OPTIONS = "-NoDX12DeviceFactory -NoDX12SDKVersionCheck"


def depth(line: str) -> int:
    in_string = escaped = False
    change = 0
    for char in line:
        if escaped:
            escaped = False
        elif char == "\\" and in_string:
            escaped = True
        elif char == '"':
            in_string = not in_string
        elif not in_string:
            change += int(char == "{") - int(char == "}")
    return change


def find_blocks(lines: list[str], key: str, start: int, end: int) -> list[tuple[int, int, int]]:
    matches = []
    for index in range(start, end):
        if lines[index].strip() != f'"{key}"':
            continue
        opening = index + 1
        while opening < end and not lines[opening].strip():
            opening += 1
        if opening >= end or lines[opening].strip() != "{":
            continue
        nesting = 0
        for close in range(opening, end):
            nesting += depth(lines[close])
            if nesting == 0:
                matches.append((index, opening, close))
                break
    return matches


def launch_options(steam: Path, steam_id: str) -> None:
    if not re.fullmatch(r"7656119[0-9]{10}", steam_id):
        raise ValueError("Invalid authenticated Steam ID")
    account = int(steam_id) - STEAM_BASE
    file = steam / f"userdata/{account}/config/localconfig.vdf"
    current = steam
    for component in file.relative_to(steam).parts:
        current = current / component
        if current.is_symlink():
            raise ValueError("Linked Steam localconfig path")
    lines = file.read_text(errors="surrogateescape").splitlines(keepends=True)
    start, end = 0, len(lines)
    apps_open = 0
    for key in ("UserLocalConfigStore", "Software", "Valve", "Steam", "apps"):
        blocks = find_blocks(lines, key, start, end)
        if len(blocks) != 1:
            raise ValueError(f"Expected exactly one Steam localconfig block: {key}")
        _, apps_open, close = blocks[0]
        start, end = apps_open + 1, close
    matches = find_blocks(lines, "2155180", start, end)
    if len(matches) > 1:
        raise ValueError("Duplicate Pagonia application blocks")
    if not matches:
        indentation = re.match(r"\s*", lines[apps_open]).group() + "\t"
        lines[end:end] = [
            f'{indentation}"2155180"\n', f"{indentation}{{\n",
            f'{indentation}\t"LaunchOptions"\t\t"{OPTIONS}"\n',
            f"{indentation}}}\n",
        ]
    else:
        _, opening, closing = matches[0]
        body = [line for line in lines[opening + 1:closing]
                if not re.match(r'^\s*"LaunchOptions"(?:\s|$)', line)]
        indentation = re.match(r"\s*", lines[opening]).group() + "\t"
        body.insert(0, f'{indentation}"LaunchOptions"\t\t"{OPTIONS}"\n')
        lines[opening + 1:closing] = body
    result = "".join(lines)
    if result.count(f'"LaunchOptions"\t\t"{OPTIONS}"') != 1:
        raise ValueError("Unable to verify Pagonia Steam launch options")
    file.write_text(result, errors="surrogateescape")
