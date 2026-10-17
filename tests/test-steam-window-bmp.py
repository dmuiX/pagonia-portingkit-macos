#!/usr/bin/env python3
"""Regression checks for black Steam-window detection."""

from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/check-steam-window-bmp.py"


def bmp32(path: Path, pixels: list[tuple[int, int, int, int]], width: int) -> None:
    height = len(pixels) // width
    payload = b"".join(bytes((blue, green, red, alpha)) for red, green, blue, alpha in pixels)
    header = (
        b"BM"
        + struct.pack("<IHHI", 54 + len(payload), 0, 0, 54)
        + struct.pack("<IiiHHIIiiII", 40, width, height, 1, 32, 0, len(payload), 0, 0, 0, 0)
    )
    path.write_bytes(header + payload)


def bmp32_bitfields(
    path: Path, pixels: list[tuple[int, int, int, int]], width: int
) -> None:
    height = len(pixels) // width
    payload = b"".join(
        bytes((blue, green, red, alpha)) for red, green, blue, alpha in pixels
    )
    dib = (
        struct.pack(
            "<IiiHHIIiiII", 124, width, -height, 1, 32, 3, len(payload), 0, 0, 0, 0
        )
        + struct.pack("<IIII", 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
        + bytes(68)
    )
    offset = 14 + len(dib)
    path.write_bytes(b"BM" + struct.pack("<IHHI", offset + len(payload), 0, 0, offset) + dib + payload)


def bmp24(path: Path, pixels: list[tuple[int, int, int]], width: int, *, top_down: bool = False) -> None:
    height = len(pixels) // width
    stride = ((width * 24 + 31) // 32) * 4
    rows = []
    for row in range(height):
        values = pixels[row * width : (row + 1) * width]
        payload = b"".join(bytes((blue, green, red)) for red, green, blue in values)
        rows.append(payload + bytes(stride - len(payload)))
    payload = b"".join(rows)
    signed_height = -height if top_down else height
    header = (
        b"BM"
        + struct.pack("<IHHI", 54 + len(payload), 0, 0, 54)
        + struct.pack("<IiiHHIIiiII", 40, width, signed_height, 1, 24, 0, len(payload), 0, 0, 0, 0)
    )
    path.write_bytes(header + payload)


def accepted(path: Path) -> bool:
    return subprocess.run(
        ["python3", str(CHECKER), str(path)], check=False
    ).returncode == 0


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        opaque_black = root / "opaque-black.bmp"
        transparent_black = root / "transparent-black.bmp"
        rendered = root / "rendered.bmp"
        padded_24_black = root / "padded-24-black.bmp"
        top_down_24 = root / "top-down-24.bmp"
        malformed = root / "malformed.bmp"
        alpha_only = root / "alpha-only.bmp"
        exactly_three_percent = root / "exactly-three-percent.bmp"
        above_threshold = root / "above-threshold.bmp"
        channel_at_cutoff = root / "channel-at-cutoff.bmp"
        bitfields_black = root / "bitfields-black.bmp"
        bitfields_rendered = root / "bitfields-rendered.bmp"
        bmp32(opaque_black, [(0, 0, 0, 255)] * 100, 10)
        bmp32(transparent_black, [(0, 0, 0, 0)] * 100, 10)
        bmp32(rendered, [(0, 0, 0, 255)] * 90 + [(40, 80, 160, 255)] * 10, 10)
        bmp32(alpha_only, [(0, 0, 0, 255)] * 90 + [(0, 0, 0, 128)] * 10, 10)
        bmp32(exactly_three_percent, [(0, 0, 0, 255)] * 97 + [(13, 0, 0, 255)] * 3, 10)
        bmp32(above_threshold, [(0, 0, 0, 255)] * 96 + [(13, 0, 0, 255)] * 4, 10)
        bmp32(channel_at_cutoff, [(0, 0, 0, 255)] * 90 + [(12, 0, 0, 255)] * 10, 10)
        bmp32_bitfields(bitfields_black, [(0, 0, 0, 255)] * 100, 10)
        bmp32_bitfields(
            bitfields_rendered,
            [(0, 0, 0, 255)] * 90 + [(40, 80, 160, 255)] * 10,
            10,
        )
        bmp24(padded_24_black, [(0, 0, 0)] * 9, 3)
        bmp24(top_down_24, [(0, 0, 0)] * 90 + [(255, 40, 20)] * 10, 10, top_down=True)
        malformed.write_bytes(b"BM" + bytes(20))
        assert not accepted(opaque_black)
        assert not accepted(transparent_black)
        assert not accepted(alpha_only)
        assert not accepted(exactly_three_percent)
        assert not accepted(channel_at_cutoff)
        assert not accepted(padded_24_black)
        assert not accepted(bitfields_black)
        assert not accepted(malformed)
        assert accepted(above_threshold)
        assert accepted(rendered)
        assert accepted(bitfields_rendered)
        assert accepted(top_down_24)


if __name__ == "__main__":
    main()
