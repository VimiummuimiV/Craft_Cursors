"""
Generator for a unified cursor set.

Usage:   python cursors.py [output_folder]
Result: svg/, png/, cur/, preview.html, cursors.json

Cursor geometry and shared style settings live in cursor_definitions.py. Each cursor is
described on a 32x32 grid, so changing shared thickness/colors rebuilds the entire set.

Dependency for PNG/.cur and preview: PyQt6 (pip install PyQt6)
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

from cursors import (
    CURSORS,
    CUR_SIZES,
    GRID,
    H,
    PNG_SIZE,
    SW,
    THEME,
    THEMES,
    canvas_size,
    render,
)

# ============================== BUILD ======================================

def build_svg(name: str, size: int = GRID, theme: str | None = None) -> str:
    """size = pixels per GRID units, so the scale is the same for every canvas.
    Width/height are integers when size is integer so the rasterizer hits whole pixels."""
    hot, factory = CURSORS[name]
    cw, ch = canvas_size(name)
    body = render(factory(), theme=theme)
    w = round(cw * size / GRID)
    h = round(ch * size / GRID)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {cw:g} {ch:g}" shape-rendering="geometricPrecision">\n'
            f'<!-- hotspot: {hot[0]},{hot[1]} -->\n{body}\n</svg>\n')


def hotspot(name: str, px: int) -> tuple[int, int]:
    hx, hy = CURSORS[name][0]
    return round(hx * px / GRID), round(hy * px / GRID)


# --------------------------- Qt: PNG, .cur, QCursor ------------------------

def _qt():
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PyQt6.QtGui import QGuiApplication, QImage, QPainter
    from PyQt6.QtSvg import QSvgRenderer
    if QGuiApplication.instance() is None:
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        global _app
        _app = QGuiApplication([])
    return QBuffer, QByteArray, QIODevice, Qt, QImage, QPainter, QSvgRenderer


def image_side(name: str, px: int) -> int:
    """Side of the square image: px pixels per GRID units, the larger canvas side decides."""
    return round(max(canvas_size(name)) * px / GRID)


def render_image(name: str, px: int, theme: str | None = None):
    """Returns a square QImage; the cursor sits in its top left corner at px pixels per GRID units
    (a bigger canvas stays transparent below/right, so the hotspot position is the same).
    Sizes and the paint rect are integers so the result stays pixel-aligned."""
    QBuffer, QByteArray, QIODevice, Qt, QImage, QPainter, QSvgRenderer = _qt()
    from PyQt6.QtCore import QRectF
    cw, ch = canvas_size(name)
    r = QSvgRenderer(QByteArray(build_svg(name, theme=theme).encode("utf-8")))
    side = image_side(name, px)
    img = QImage(side, side, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # integer pixel bounds (QRectF required by the API)
    w = round(cw * px / GRID)
    h = round(ch * px / GRID)
    r.render(p, QRectF(0, 0, w, h))
    p.end()
    return img


def png_bytes(img) -> bytes:
    QBuffer, QByteArray, QIODevice, *_ = _qt()
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def write_cur(path: Path, entries: list[tuple[int, int, int, bytes]]) -> None:
    """entries: (px, hotspot_x, hotspot_y, png_bytes). PNG inside .cur - Vista+."""
    n = len(entries)
    head = struct.pack("<HHH", 0, 2, n)
    offset = 6 + 16 * n
    dirs, blobs = b"", b""
    for px, hx, hy, png in entries:
        dim = px if px < 256 else 0
        dirs += struct.pack("<BBBBHHII", dim, dim, 0, 0, hx, hy, len(png), offset + len(blobs))
        blobs += png
    path.write_bytes(head + dirs + blobs)


def qcursor(name: str, size: int = 32):
    """Ready-to-use QCursor for PyQt6: widget.setCursor(qcursor("pen_add"))"""
    from PyQt6.QtGui import QCursor, QPixmap
    hx, hy = hotspot(name, size)
    return QCursor(QPixmap.fromImage(render_image(name, size)), hx, hy)


def main() -> None:
    from preview import contact_sheet, preview_html

    out = Path(sys.argv[1] if len(sys.argv) > 1 else "cursors_out")
    for d in ("svg", "png", "cur"):
        (out / d).mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name in CURSORS:
        (out / "svg" / f"{name}.svg").write_text(build_svg(name), encoding="utf-8")
        entries = []
        for px in CUR_SIZES:
            png = png_bytes(render_image(name, px))
            if px == PNG_SIZE:
                (out / "png" / f"{name}_{px}.png").write_bytes(png)
            else:
                stale_png = out / "png" / f"{name}_{px}.png"
                if stale_png.exists():
                    stale_png.unlink()
            hx, hy = hotspot(name, px)
            entries.append((image_side(name, px), hx, hy, png))
        write_cur(out / "cur" / f"{name}.cur", entries)
        manifest[name] = {
            "hotspot_32": CURSORS[name][0],
            "canvas": canvas_size(name),
        }
    manifest["_meta"] = {"theme": THEME, "themes": list(THEMES)}
    (out / "cursors.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "preview.html").write_text(
        preview_html(CURSORS, canvas_size, build_svg, GRID, THEME),
        encoding="utf-8",
    )
    contact_sheet(out / "sheet.png", CURSORS, image_side, render_image, _qt)
    print(f"ready: {len(CURSORS)} cursors (theme={THEME}) -> {out.resolve()}")


if __name__ == "__main__":
    main()