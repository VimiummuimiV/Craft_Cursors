"""
Generator for a unified cursor set.

Usage:   python main.py [output_folder]
Result: svg/, png/{dark,light}/, cur/{dark,light}/, preview.html, sheet_*.png, cursors.json

Cursor geometry and shared style settings live in cursors.py. Each cursor is described on a
32x32 grid, so changing shared thickness/colors rebuilds the entire set. Every cursor, halo
included, must stay inside the allowed region (PADDING from each canvas edge); the build stops
and lists the cursors that cross it. Every .cur size is grid-fitted separately (see gridfit.py),
so lines and edges stay sharp at 100-300% display scaling, not only at the base size.

Dependency for PNG/.cur and preview: PyQt6 (pip install PyQt6)
"""
from __future__ import annotations

import json
import os
import struct
import sys
from pathlib import Path

from cursors import (
    build_svg,
    canvas_size,
    ACTUAL_SIZE,
    CURSORS,
    CUR_SIZES,
    GRID,
    PADDING,
    PNG_SIZES,
    THEME,
    THEMES,
)
from gridfit import pixel
from preview import (
    contact_sheet,
    preview_html,
)

PADDING_CHECK_PIXELS_PER_UNIT = 10
PADDING_TOLERANCE = 0.1   # one check pixel: antialiasing may spill into the neighbouring pixel
SIDES = ("left", "top", "right", "bottom")

# --------------------------- Qt: PNG, .cur, QCursor ------------------------

_application = None


def _ensure_application() -> None:
    """Creates a headless Qt application unless the host program already has one."""
    global _application
    from PyQt6.QtGui import QGuiApplication
    if _application is None and QGuiApplication.instance() is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        _application = QGuiApplication([])


def hotspot(name: str, size: int) -> tuple[int, int]:
    hotspot_x, hotspot_y = CURSORS[name][0]
    return pixel(hotspot_x * size / GRID), pixel(hotspot_y * size / GRID)


def image_side(name: str, size: int) -> int:
    """Side of the square image: size pixels per GRID units, the larger canvas side decides."""
    return round(max(canvas_size(name)) * size / GRID)


def render_image(name: str, size: int, theme: str | None = None):
    """Returns a square QImage; the cursor sits in its top left corner at size pixels per GRID units
    (a bigger canvas stays transparent below/right, so the hotspot position is the same).
    The SVG is already fitted to size and written in pixels, so it maps 1:1 onto the image."""
    from PyQt6.QtCore import QByteArray, QRectF, Qt
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtSvg import QSvgRenderer
    _ensure_application()
    canvas_width, canvas_height = canvas_size(name)
    renderer = QSvgRenderer(QByteArray(build_svg(name, size, theme=theme).encode("utf-8")))
    side = image_side(name, size)
    image = QImage(side, side, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, round(canvas_width * size / GRID), round(canvas_height * size / GRID)))
    painter.end()
    return image


def png_bytes(image) -> bytes:
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data)


def write_cur(path: Path, entries: list[tuple[int, int, int, bytes]]) -> None:
    """entries: (size, hotspot_x, hotspot_y, png_bytes). PNG inside .cur - Vista+."""
    header = struct.pack("<HHH", 0, 2, len(entries))
    offset = 6 + 16 * len(entries)
    directory, blobs = b"", b""
    for size, hotspot_x, hotspot_y, png in entries:
        dimension = size if size < 256 else 0
        directory += struct.pack("<BBBBHHII", dimension, dimension, 0, 0,
                                 hotspot_x, hotspot_y, len(png), offset + len(blobs))
        blobs += png
    path.write_bytes(header + directory + blobs)


def qcursor(name: str, size: int = 32):
    """Ready-to-use QCursor for PyQt6: widget.setCursor(qcursor("pen_add"))"""
    from PyQt6.QtGui import QCursor, QPixmap
    hotspot_x, hotspot_y = hotspot(name, size)
    return QCursor(QPixmap.fromImage(render_image(name, size)), hotspot_x, hotspot_y)


# ============================== PADDING ====================================

def padding(name: str) -> tuple[float, float, float, float]:
    """Empty margin (left, top, right, bottom) in grid units between the drawn cursor, halo
    included, and the edges of its canvas. A cursor that touches an edge measures 0."""
    size = PADDING_CHECK_PIXELS_PER_UNIT * GRID
    image = render_image(name, size, theme=THEME)
    pointer = image.constBits()
    pointer.setsize(image.sizeInBytes())
    alpha = bytes(pointer)[3::4]   # ARGB32 is stored as B, G, R, A bytes
    side = image.width()
    drawn_rows = [(y, alpha[y * side:(y + 1) * side]) for y in range(side)]
    drawn_rows = [(y, row) for y, row in drawn_rows if any(row)]
    left = min(side - len(row.lstrip(b"\0")) for _, row in drawn_rows)
    right = max(len(row.rstrip(b"\0")) for _, row in drawn_rows)
    top, bottom = drawn_rows[0][0], drawn_rows[-1][0] + 1
    unit = PADDING_CHECK_PIXELS_PER_UNIT
    canvas_width, canvas_height = canvas_size(name)
    return left / unit, top / unit, canvas_width - right / unit, canvas_height - bottom / unit


def check_padding() -> None:
    """Stops the build when any cursor crosses the allowed region."""
    problems = []
    for name in CURSORS:
        for side, margin in zip(SIDES, padding(name)):
            if round(margin, 2) < PADDING - PADDING_TOLERANCE:
                problems.append(f"  {name}: {side} margin {margin:.2f} < {PADDING:g}")
    if problems:
        sys.exit("cursors cross the allowed region:\n" + "\n".join(problems))


# ============================== BUILD ======================================

def preview_png(name: str, size: int, theme: str) -> bytes:
    return png_bytes(render_image(name, size, theme=theme))


def export_cursor(out: Path, name: str, theme: str) -> None:
    entries = []
    for size in CUR_SIZES:
        png = preview_png(name, size, theme)
        png_path = out / "png" / theme / f"{name}_{size}.png"
        if size in PNG_SIZES:
            png_path.write_bytes(png)
        else:
            png_path.unlink(missing_ok=True)
        hotspot_x, hotspot_y = hotspot(name, size)
        entries.append((image_side(name, size), hotspot_x, hotspot_y, png))
    write_cur(out / "cur" / theme / f"{name}.cur", entries)


def main() -> None:
    check_padding()
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "cursors_out")
    (out / "svg").mkdir(parents=True, exist_ok=True)
    for kind in ("png", "cur"):
        for theme in THEMES:
            (out / kind / theme).mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name in CURSORS:
        (out / "svg" / f"{name}.svg").write_text(build_svg(name), encoding="utf-8")
        for theme in THEMES:
            export_cursor(out, name, theme)
        manifest[name] = {
            "hotspot_32": CURSORS[name][0],
            "canvas": canvas_size(name),
        }
    manifest["_meta"] = {"theme": THEME, "themes": list(THEMES)}
    (out / "cursors.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "preview.html").write_text(preview_html(preview_png), encoding="utf-8")
    for theme in THEMES:
        for suffix, size in (("", 96), ("_small", ACTUAL_SIZE)):
            contact_sheet(out / f"sheet_{theme}{suffix}.png", image_side, render_image,
                          theme=theme, pixels_per_unit=size)
    print(f"ready: {len(CURSORS)} cursors (themes={', '.join(THEMES)}) -> {out.resolve()}")


if __name__ == "__main__":
    main()