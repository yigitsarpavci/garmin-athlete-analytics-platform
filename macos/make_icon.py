#!/usr/bin/env python3
"""Generate a clean 1024x1024 PNG app icon with pure stdlib (no Pillow required)."""

import math
import struct
import sys
import zlib


def write_png(path: str, size: int = 1024) -> None:
    bg = (13, 19, 15, 255)        # #0D130F
    card = (20, 31, 24, 255)      # #141F18
    border = (74, 124, 99, 255)   # #4A7C63
    pulse = (94, 143, 116, 255)   # #5E8F74
    highlight = (232, 238, 233, 255)

    # Pulse polyline points in normalized [0..1] coordinates
    pts = [
        (0.14, 0.54),
        (0.32, 0.54),
        (0.40, 0.34),
        (0.48, 0.72),
        (0.57, 0.24),
        (0.65, 0.60),
        (0.73, 0.48),
        (0.86, 0.48),
    ]

    def dist_to_seg(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
        vx, vy = bx - ax, by - ay
        wx, wy = px - ax, py - ay
        c1 = vx * wx + vy * wy
        if c1 <= 0:
            return math.hypot(px - ax, py - ay)
        c2 = vx * vx + vy * vy
        if c2 <= c1:
            return math.hypot(px - bx, py - by)
        b = c1 / c2
        return math.hypot(px - (ax + b * vx), py - (ay + b * vy))

    rows = []
    radius = 0.20 * size
    pad = 0.06 * size
    inner_min = pad
    inner_max = size - pad
    stroke_w = 0.024 * size

    for y in range(size):
        row = bytearray([0])  # filter type 0
        ny = (y + 0.5) / size
        for x in range(size):
            nx = (x + 0.5) / size
            # Rounded-rect signed distance
            cx = max(inner_min + radius, min(inner_max - radius, x + 0.5))
            cy = max(inner_min + radius, min(inner_max - radius, y + 0.5))
            d_edge = math.hypot((x + 0.5) - cx, (y + 0.5) - cy) - radius

            if d_edge > 2.0:
                row.extend((0, 0, 0, 0))
                continue

            if d_edge > -4.0:
                c = border
            else:
                c = card

            # Subtle inner highlight for pulse line
            min_d = 999.0
            for i in range(len(pts) - 1):
                d = dist_to_seg(nx, ny, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]) * size
                if d < min_d:
                    min_d = d

            if min_d <= stroke_w * 0.65:
                c = highlight
            elif min_d <= stroke_w:
                c = pulse

            # Soft outer alpha antialias
            if d_edge > 0.0:
                alpha = max(0, min(255, int(255 * (1.0 - d_edge / 2.0))))
                row.extend((c[0], c[1], c[2], alpha))
            else:
                row.extend(c)
        rows.append(bytes(row))

    raw = b"".join(rows)
    compressed = zlib.compress(raw, 6)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack("!I", len(data)) + tag + data + struct.pack("!I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack("!IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png_bytes = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png_bytes)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "icon_1024.png"
    write_png(out, 1024)
