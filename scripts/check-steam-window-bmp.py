#!/usr/bin/env python3
"""Exit successfully only when a BMP contains enough visibly non-black pixels."""

from pathlib import Path
import struct
import sys


def has_visible_pixels(path: Path) -> bool:
    data = path.read_bytes()
    if len(data) < 54 or data[:2] != b"BM":
        return False

    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    dib_size = struct.unpack_from("<I", data, 14)[0]
    if dib_size < 40 or len(data) < 14 + dib_size:
        return False

    width, signed_height = struct.unpack_from("<ii", data, 18)
    planes, bits_per_pixel = struct.unpack_from("<HH", data, 26)
    compression = struct.unpack_from("<I", data, 30)[0]
    height = abs(signed_height)
    if (
        width <= 0
        or height <= 0
        or planes != 1
        or bits_per_pixel not in (24, 32)
        or compression not in (0, 3)
    ):
        return False
    if compression == 3:
        if bits_per_pixel != 32 or dib_size < 56:
            return False
        red_mask, green_mask, blue_mask, alpha_mask = struct.unpack_from(
            "<IIII", data, 54
        )
        if (red_mask, green_mask, blue_mask, alpha_mask) != (
            0x00FF0000,
            0x0000FF00,
            0x000000FF,
            0xFF000000,
        ):
            return False

    bytes_per_pixel = bits_per_pixel // 8
    row_stride = ((width * bits_per_pixel + 31) // 32) * 4
    required_size = pixel_offset + row_stride * height
    if pixel_offset < 14 + dib_size or required_size > len(data):
        return False

    visible = 0
    total = width * height
    for row in range(height):
        row_start = pixel_offset + row * row_stride
        for column in range(width):
            pixel_start = row_start + column * bytes_per_pixel
            blue, green, red = data[pixel_start : pixel_start + 3]
            if max(red, green, blue) > 12:
                visible += 1

    return visible / total > 0.03


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {Path(sys.argv[0]).name} IMAGE.bmp", file=sys.stderr)
        return 2
    try:
        return 0 if has_visible_pixels(Path(sys.argv[1])) else 1
    except (OSError, struct.error, ValueError):
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
