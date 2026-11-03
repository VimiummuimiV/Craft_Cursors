"""
Generator for a unified cursor set.

Usage:   python main.py [output_folder]
Settings (themes per format, sizes, cursors to build, output folder, style, preview) live in config.py.
Result: svg/<theme>/, png/<theme>/<size>/, cur/<theme>/<size>/ and cur/<theme>/multi/, preview.html, sheet_*.png, cursors.json.
Stale SVG, PNG, CUR and contact-sheet exports are removed from those generated output folders.

Cursor geometry lives in cursors.py. Each cursor is described on a
32x32 grid, so changing shared thickness/colors in config.py rebuilds the entire set. Every cursor, halo
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

from config import (
    CUR_MULTI_SIZE_FILE,
    CUR_SINGLE_SIZE_FILES,
    CUR_SIZES,
    CUR_THEMES,
    EXPORT_CURSORS,
    EXPORT_PREVIEW,
    GRID,
    OUTPUT_FOLDER,
    PADDING,
    PNG_THEMES,
    SHEET_SIZES,
    SVG_SIZE,
    SVG_THEMES,
    THEMES,
)
from cursors import (
    build_svg,
    canvas_size,
    image_side,
    CURSORS,
)
from gridfit import pixel
from preview import (
    contact_sheet,
    preview_html,
)

_MULTI_SIZE_FOLDER = "multi"   # one .cur per cursor with every size inside, for installing in Windows
_PADDING_CHECK_PIXELS_PER_UNIT = 10
_PADDING_CHECK_THEME = next(iter(THEMES))   # the shape, not the colors, decides the margins
_PADDING_TOLERANCE = 0.1   # one check pixel: antialiasing may spill into the neighbouring pixel
_SIDES = ("left", "top", "right", "bottom")

# --------------------------- Qt: PNG, .cur, QCursor ------------------------

_application = None


def _ensure_application() -> None:
    """Creates a headless Qt application unless the host program already has one."""
    global _application
    from PyQt6.QtGui import QGuiApplication
    if _application is None and QGuiApplication.instance() is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        _application = QGuiApplication([])


def _hotspot(name: str, size: int) -> tuple[int, int]:
    hotspot_x, hotspot_y = CURSORS[name][0]
    return pixel(hotspot_x * size / GRID), pixel(hotspot_y * size / GRID)


def _render_image(name: str, size: int, theme: str):
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


def _png_bytes(image) -> bytes:
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data)


def _target(path: Path) -> Path:
    """Creates the parent folder so the file can be written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write_cur(path: Path, entries: list[tuple[int, int, int, bytes]]) -> None:
    """entries: (size, hotspot_x, hotspot_y, png_bytes). PNG inside .cur - Vista+."""
    header = struct.pack("<HHH", 0, 2, len(entries))
    offset = 6 + 16 * len(entries)
    directory, blobs = b"", b""
    for size, hotspot_x, hotspot_y, png in entries:
        dimension = size if size < 256 else 0
        directory += struct.pack("<BBBBHHII", dimension, dimension, 0, 0,
                                 hotspot_x, hotspot_y, len(png), offset + len(blobs))
        blobs += png
    _target(path).write_bytes(header + directory + blobs)


def qcursor(name: str, size: int = 32):
    """Ready-to-use QCursor for PyQt6: widget.setCursor(qcursor("pen_add"))"""
    from PyQt6.QtGui import QCursor, QPixmap
    hotspot_x, hotspot_y = _hotspot(name, size)
    return QCursor(QPixmap.fromImage(_render_image(name, size)), hotspot_x, hotspot_y)


# ============================== PADDING ====================================

def _padding(name: str) -> tuple[float, float, float, float]:
    """Empty margin (left, top, right, bottom) in grid units between the drawn cursor, halo
    included, and the edges of its canvas. A cursor that touches an edge measures 0."""
    size = _PADDING_CHECK_PIXELS_PER_UNIT * GRID
    image = _render_image(name, size, theme=_PADDING_CHECK_THEME)
    pointer = image.constBits()
    pointer.setsize(image.sizeInBytes())
    alpha = bytes(pointer)[3::4]   # ARGB32 is stored as B, G, R, A bytes
    side = image.width()
    drawn_rows = [(y, alpha[y * side:(y + 1) * side]) for y in range(side)]
    drawn_rows = [(y, row) for y, row in drawn_rows if any(row)]
    left = min(side - len(row.lstrip(b"\0")) for _, row in drawn_rows)
    right = max(len(row.rstrip(b"\0")) for _, row in drawn_rows)
    top, bottom = drawn_rows[0][0], drawn_rows[-1][0] + 1
    unit = _PADDING_CHECK_PIXELS_PER_UNIT
    canvas_width, canvas_height = canvas_size(name)
    return left / unit, top / unit, canvas_width - right / unit, canvas_height - bottom / unit


def _check_padding(names: list[str]) -> None:
    """Stops the build when any cursor crosses the allowed region."""
    problems = []
    for name in names:
        for side, margin in zip(_SIDES, _padding(name)):
            if round(margin, 2) < PADDING - _PADDING_TOLERANCE:
                problems.append(f"  {name}: {side} margin {margin:.2f} < {PADDING:g}")
    if problems:
        sys.exit("cursors cross the allowed region:\n" + "\n".join(problems))


# ============================== BUILD ======================================

def _preview_png(name: str, size: int, theme: str) -> bytes:
    return _png_bytes(_render_image(name, size, theme=theme))


def _export_cursor(out: Path, name: str) -> None:
    for theme in dict.fromkeys((*PNG_THEMES, *CUR_THEMES)):
        entries = []
        for size in CUR_SIZES:
            png = _preview_png(name, size, theme)
            hotspot_x, hotspot_y = _hotspot(name, size)
            entry = (image_side(name, size), hotspot_x, hotspot_y, png)
            entries.append(entry)
            if theme in PNG_THEMES:
                _target(out / "png" / theme / str(size) / f"{name}.png").write_bytes(png)
            if theme in CUR_THEMES and CUR_SINGLE_SIZE_FILES:
                _write_cur(out / "cur" / theme / str(size) / f"{name}.cur", [entry])
        if theme in CUR_THEMES and CUR_MULTI_SIZE_FILE:
            _write_cur(out / "cur" / theme / _MULTI_SIZE_FOLDER / f"{name}.cur", entries)


def _prune_stale_exports(out: Path) -> None:
    expected_svg = {Path(theme) / f"{name}.svg" for theme in SVG_THEMES for name in CURSORS}
    expected_png = {
        Path(theme) / str(size) / f"{name}.png"
        for theme in PNG_THEMES
        for size in CUR_SIZES
        for name in CURSORS
    }
    cur_folders = [str(size) for size in CUR_SIZES if CUR_SINGLE_SIZE_FILES]
    if CUR_MULTI_SIZE_FILE:
        cur_folders.append(_MULTI_SIZE_FOLDER)
    expected_cur = {
        Path(theme) / folder / f"{name}.cur"
        for theme in CUR_THEMES
        for folder in cur_folders
        for name in CURSORS
    }

    for root, expected, suffix in (
        (out / "svg", expected_svg, ".svg"),
        (out / "png", expected_png, ".png"),
        (out / "cur", expected_cur, ".cur"),
    ):
        if root.exists():
            for path in root.rglob(f"*{suffix}"):
                if path.relative_to(root) not in expected:
                    path.unlink()
            for folder in sorted((path for path in (root, *root.rglob("*")) if path.is_dir()), reverse=True):
                if not any(folder.iterdir()):
                    folder.rmdir()

    expected_sheets = {f"sheet_{theme}{suffix}.png" for theme in THEMES for suffix in SHEET_SIZES}
    for path in out.glob("sheet_*.png"):
        if path.name not in expected_sheets:
            path.unlink()


def _check_config() -> None:
    """Stops the build on a theme or cursor name in config.py that does not exist."""
    problems = [f"  {setting}: unknown theme {theme!r}"
                for setting, themes in (("SVG_THEMES", SVG_THEMES), ("PNG_THEMES", PNG_THEMES),
                                        ("CUR_THEMES", CUR_THEMES))
                for theme in themes if theme not in THEMES]
    problems += [f"  EXPORT_CURSORS: unknown cursor {name!r}" for name in EXPORT_CURSORS if name not in CURSORS]
    if problems:
        sys.exit("config.py:\n" + "\n".join(problems))


def main() -> None:
    _check_config()
    names = [name for name in CURSORS if not EXPORT_CURSORS or name in EXPORT_CURSORS]
    _check_padding(names)
    out = Path(sys.argv[1] if len(sys.argv) > 1 else OUTPUT_FOLDER)
    for name in names:
        for theme in SVG_THEMES:
            _target(out / "svg" / theme / f"{name}.svg").write_text(build_svg(name, SVG_SIZE, theme), encoding="utf-8")
        _export_cursor(out, name)
    manifest = {name: {"hotspot_32": CURSORS[name][0], "canvas": canvas_size(name)} for name in CURSORS}
    manifest["_meta"] = {"themes": list(THEMES)}
    _target(out / "cursors.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    preview_file = out / "preview.html"
    if EXPORT_PREVIEW:
        preview_file.write_text(preview_html(_preview_png, names), encoding="utf-8")
    else:
        preview_file.unlink(missing_ok=True)
    for theme in THEMES:
        for suffix, size in SHEET_SIZES.items():
            contact_sheet(out / f"sheet_{theme}{suffix}.png", _render_image, names, theme=theme, pixels_per_unit=size)
    _prune_stale_exports(out)
    print(f"ready: {len(names)} cursors (svg={', '.join(SVG_THEMES) or '-'}; png={', '.join(PNG_THEMES) or '-'}; "
          f"cur={', '.join(CUR_THEMES) or '-'}) -> {out.resolve()}")


if __name__ == "__main__":
    main()
