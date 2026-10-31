"""
Generator for a unified cursor set.

Usage:   python cursors.py [output_folder]
Result: svg/, png/, cur/, preview.html, cursors.json

The shared style is controlled by the tokens in the STYLE block. Each cursor is described
only by geometry on a 32x32 grid, so changing thickness/colors rebuilds the entire set.

Dependency for PNG/.cur and preview: PyQt6 (pip install PyQt6)
"""
from __future__ import annotations

import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

# ============================== STYLE ======================================
GRID = 32            # logical cursor grid
INK = "#000000"      # outline and dark detail color
PAPER = "#ffffff"    # fill for light forms
HALO = "#ffffff"     # halo outside the outline (readable on dark backgrounds)
SW = 1.2             # outline thickness
H = 1.0              # halo width
SIZES = (32, 48, 64) # sizes included in .cur and PNG outputs
# ===========================================================================

ROUND = 'stroke-linecap="round" stroke-linejoin="round"'


@dataclass
class Shape:
    """A single cursor element.

    kind:
      paper - light form with a dark outline (closed path, rect, circle)
      pline - thick light line with rounded ends and outline (fingers, thumb)
      ink   - solid dark form
      line  - dark line with thickness w (symbols +, -, ^, etc.)
    top: drawn above everything else, without a halo (details inside forms)
    """
    el: str
    geom: str
    kind: str
    w: float = 0.0
    top: bool = False
    xf: str = ""

    def tag(self, attrs: str) -> str:
        t = f' transform="{self.xf}"' if self.xf else ""
        return f"<{self.el} {self.geom} {attrs}{t}/>"


def render(shapes: list[Shape]) -> str:
    out: list[str] = []
    # 1) halo
    for s in shapes:
        if s.top:
            continue
        if s.kind == "paper":
            a = f'fill="{HALO}" stroke="{HALO}" stroke-width="{2 * (SW + H)}" {ROUND}'
        elif s.kind == "pline":
            a = f'fill="none" stroke="{HALO}" stroke-width="{s.w + 2 * (SW + H)}" {ROUND}'
        elif s.kind == "ink":
            a = f'fill="{HALO}" stroke="{HALO}" stroke-width="{2 * H}" {ROUND}'
        else:
            a = f'fill="none" stroke="{HALO}" stroke-width="{s.w + 2 * H}" {ROUND}'
        out.append(s.tag(a))
    # 2) outline / dark forms
    for s in shapes:
        if s.top:
            continue
        if s.kind == "paper":
            a = f'fill="{INK}" stroke="{INK}" stroke-width="{2 * SW}" {ROUND}'
        elif s.kind == "pline":
            a = f'fill="none" stroke="{INK}" stroke-width="{s.w + 2 * SW}" {ROUND}'
        elif s.kind == "ink":
            a = f'fill="{INK}" stroke="none"'
        else:
            a = f'fill="none" stroke="{INK}" stroke-width="{s.w}" {ROUND}'
        out.append(s.tag(a))
    # 3) light fill on top (eraser for internal intersection lines)
    for s in shapes:
        if s.top:
            continue
        if s.kind == "paper":
            out.append(s.tag(f'fill="{PAPER}" stroke="none"'))
        elif s.kind == "pline":
            out.append(s.tag(f'fill="none" stroke="{PAPER}" stroke-width="{s.w}" {ROUND}'))
    # 4) top details
    for s in shapes:
        if not s.top:
            continue
        if s.kind == "ink":
            out.append(s.tag(f'fill="{INK}" stroke="none"'))
        else:
            out.append(s.tag(f'fill="none" stroke="{INK}" stroke-width="{s.w}" {ROUND}'))
    return "\n".join(out)


# ============================ GEOMETRY ====================================

_ARGS = {"M": 2, "L": 2, "C": 6, "Q": 4, "A": 7}


def fit(d: str, s: float, ref: tuple[float, float], to: tuple[float, float] = (16, 16)) -> str:
    """Scales an absolute path (M L C Q A Z) without changing line thickness.
    Geometry is drawn in reference "pixel" coordinates; ref is remapped to point to on the 32x32 grid."""
    import re
    toks = re.findall(r"[A-Za-z]|-?\d*\.?\d+", d)
    out: list[str] = []
    i, cmd = 0, ""
    f = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")
    while i < len(toks):
        if toks[i].isalpha():
            cmd = toks[i]
            out.append(cmd)
            i += 1
            continue
        n = _ARGS[cmd]
        a = [float(v) for v in toks[i:i + n]]
        i += n
        if cmd == "A":
            out.append(" ".join([f(a[0] * s), f(a[1] * s), f(a[2]), f(a[3]), f(a[4]),
                                 f((a[5] - ref[0]) * s + to[0]), f((a[6] - ref[1]) * s + to[1])]))
        else:
            out.append(" ".join(f((v - (ref[0] if k % 2 == 0 else ref[1])) * s + to[k % 2 == 1])
                                for k, v in enumerate(a)))
    return " ".join(out)


def zoom(sign: str) -> list[Shape]:
    cx = cy = 13
    sh = [
        Shape("circle", f'cx="{cx}" cy="{cy}" r="8.5"', "paper"),
        Shape("path", 'd="M21 21 L27.5 27.5"', "line", 4.4),
        Shape("path", f'd="M{cx - 3.8} {cy} H{cx + 3.8}"', "line", 1.8, top=True),
    ]
    if sign == "+":
        sh.append(Shape("path", f'd="M{cx} {cy - 3.8} V{cy + 3.8}"', "line", 1.8, top=True))
    return sh


def eyedropper() -> list[Shape]:
    xf = "translate(3.8 28.2) rotate(45)"
    return [
        Shape("path", 'd="M0 0 L-2.7 -7 L-2.7 -17.5 L2.7 -17.5 L2.7 -7 Z"', "paper", xf=xf),
        Shape("rect", 'x="-4.5" y="-21.5" width="9" height="4.5" rx="1.2"', "paper", xf=xf),
        Shape("rect", 'x="-3.5" y="-31" width="7" height="10.5" rx="3.5"', "ink", xf=xf),
    ]


# Hands are drawn in reference coordinates (pixels); fit() remaps them to the 32x32 grid.
# Open and closed hands are two frames of the same tool: shared palm, wrist,
# scale, and outline. They differ in the fingers (tip arc centers) and the thumb protrusion.
_HAND_S, _HAND_REF = 0.060, (207, 283.5)
_TAIL = "L365 410 C365 465 335 492 290 492 L210 492 C185 492 165 480 150 458 "
# thumb: extended for the open hand, bent shorter for the grab hand; the base is the same
_THUMB_OPEN = "L52.6 307.7 A29 29 0 0 1 101.4 276.3 Z"
_THUMB_GRAB = "L97.5 420.5 A29 29 0 0 1 118 371 Z"
# contour of the thumb lying across the palm (inner line)
_THUMB_GRAB_LINE = "M118 371 L205 356 A29 29 0 0 1 205 414 L108 428"
# arc centers of fingertips: index, middle, ring, pinky
_TIPS_OPEN = (127.5, 105, 125, 192.5)
_TIPS_GRAB = (242.5, 227, 240, 262.5)
# end y-coordinates of separator lines, one per joint
_SEP_END_OPEN = (275, 285, 292)
_SEP_END_GRAB = (300, 305, 310)


def _hand_path(c: tuple, thumb: str) -> str:
    return (f"M135 335 L135 {c[0]} A27.5 27.5 0 0 1 190 {c[0]} L190 {c[1]} A30 30 0 0 1 250 {c[1]} "
            f"L250 {c[2]} A30 30 0 0 1 310 {c[2]} L310 {c[3]} A27.5 27.5 0 0 1 365 {c[3]} " + _TAIL + thumb)


def _hand_seps(c: tuple, ends: tuple) -> list:
    # (x, y_from, y_to, side): -1 = fill on the right side of the edge (outline on the left), +1 = opposite
    return [(190, c[0], ends[0], -1), (250, c[2], ends[1], +1), (310, c[3], ends[2], +1)]


def _seps(seps, s: float) -> str:
    """Separator lines between fingers: shift by half the thickness so they continue the contour."""
    k = SW / 2 / s
    up = 0.8 / s  # move slightly above the joint to merge smoothly with the contour without a gap
    return " ".join(f"M{x + side * k:.2f} {y0 - up:.2f} L{x + side * k:.2f} {y1}"
                    for x, y0, y1, side in seps)


def _hand(tips: tuple, ends: tuple, thumb: str, thumb_line: str = "") -> list[Shape]:
    s, ref = _HAND_S, _HAND_REF
    sh = [
        Shape("path", f'd="{fit(_hand_path(tips, thumb), s, ref)}"', "paper"),
        Shape("path", f'd="{fit(_seps(_hand_seps(tips, ends), s), s, ref)}"', "line", SW, top=True),
    ]
    if thumb_line:
        sh.append(Shape("path", f'd="{fit(thumb_line, s, ref)}"', "line", SW, top=True))
    return sh


def hand_open() -> list[Shape]:
    """Open hand."""
    return _hand(_TIPS_OPEN, _SEP_END_OPEN, _THUMB_OPEN)


def hand_grab() -> list[Shape]:
    """Closed hand: same hand shape, fingers bent inward."""
    return _hand(_TIPS_GRAB, _SEP_END_GRAB, _THUMB_GRAB, _THUMB_GRAB_LINE)


_NIB_XF = "translate(4.5 28.3) rotate(35)"


def pen_nib() -> list[Shape]:
    xf = _NIB_XF
    return [
        Shape("path", 'd="M0 0 L-5.4 -10.5 Q-6 -16 -4.2 -18.2 L4.2 -18.2 Q6 -16 5.4 -10.5 Z"',
              "paper", xf=xf),
        Shape("rect", 'x="-4.2" y="-27.6" width="8.4" height="10.4" rx="1.6"', "ink", xf=xf),
        Shape("path", 'd="M0 -1.3 V-8.8"', "line", 1.0, top=True, xf=xf),
        Shape("circle", 'cx="0" cy="-11.7" r="1.65"', "ink", top=True, xf=xf),
    ]


# small icons at the lower right of the pen
BADGES = {
    "pen": [],
    "pen_freeform": [Shape("path", 'd="M20.5 25.5 Q22.5 21.5 24.5 25.5 T28.5 25.5"', "line", 1.7)],
    "pen_curvature": [Shape("path", 'd="M21 27.5 C24 27.5 24 22 28 22"', "line", 1.7)],
    "pen_add": [Shape("path", 'd="M21.5 24.5 H27.5 M24.5 21.5 V27.5"', "line", 1.8)],
    "pen_delete": [Shape("path", 'd="M21.5 24.5 H27.5"', "line", 1.8)],
    "pen_convert": [Shape("path", 'd="M21.5 27 L24.5 22 L27.5 27"', "line", 1.7)],
    "pen_close": [Shape("circle", 'cx="24.5" cy="24.5" r="2.8"', "line", 1.6)],
}

# name -> (hotspot on the 32x32 grid, shape factory)
CURSORS: dict[str, tuple[tuple[int, int], callable]] = {
    "zoom_in": ((13, 13), lambda: zoom("+")),
    "zoom_out": ((13, 13), lambda: zoom("-")),
    "eyedropper": ((4, 28), eyedropper),
    "hand_open": ((16, 16), hand_open),
    "hand_grab": ((16, 16), hand_grab),
}
for _name, _badge in BADGES.items():
    CURSORS[_name] = ((4, 28), (lambda b=_badge: pen_nib() + b))


# ============================== BUILD ======================================

def build_svg(name: str, size: int = GRID) -> str:
    hot, factory = CURSORS[name]
    body = render(factory())
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="0 0 {GRID} {GRID}">\n<!-- hotspot: {hot[0]},{hot[1]} -->\n{body}\n</svg>\n')


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


def render_image(name: str, px: int):
    """Returns a QImage for the cursor at the requested size."""
    QBuffer, QByteArray, QIODevice, Qt, QImage, QPainter, QSvgRenderer = _qt()
    r = QSvgRenderer(QByteArray(build_svg(name).encode("utf-8")))
    img = QImage(px, px, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    r.render(p)
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


# ------------------------------- preview ------------------------------------

def preview_html() -> str:
    cards = []
    for name in CURSORS:
        hx, hy = CURSORS[name][0]
        svg = build_svg(name, 96)
        hot = f'<i style="left:{hx * 3}px;top:{hy * 3}px"></i>'
        cards.append(
            f'<div class="c"><div class="row"><div class="bg l"><div class="s">{svg}{hot}</div></div>'
            f'<div class="bg d"><div class="s">{svg}{hot}</div></div></div>'
            f'<b>{name}</b><small>hotspot {hx},{hy}</small></div>')
    return ("<!doctype html><meta charset=utf-8><title>Cursors</title><style>"
            "body{font:14px system-ui;margin:24px;background:#888;display:grid;"
            "grid-template-columns:repeat(auto-fill,230px);gap:16px}"
            ".c{background:#fff3;padding:8px;border-radius:8px;color:#111}"
            ".row{display:flex}.bg{width:110px;height:110px;display:grid;place-items:center}"
            ".l{background:#f1f1f1}.d{background:#262626}"
            ".s{position:relative;width:96px;height:96px}.s svg{display:block}"
            ".s i{position:absolute;width:5px;height:5px;margin:-2px 0 0 -2px;border-radius:50%;"
            "background:#e0245e}b{display:block;margin-top:6px}small{opacity:.7}"
            "</style>" + "".join(cards))


def contact_sheet(path: Path) -> None:
    """Quick-check PNG sheet: light/dark background, red dot = hotspot."""
    QBuffer, QByteArray, QIODevice, Qt, QImage, QPainter, QSvgRenderer = _qt()
    from PyQt6.QtGui import QColor
    names = list(CURSORS)
    cols, cell, px = 4, 240, 96
    rows = (len(names) + cols - 1) // cols
    img = QImage(cols * cell, rows * 130, QImage.Format.Format_ARGB32)
    img.fill(QColor("#888888"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for i, n in enumerate(names):
        x0, y0 = (i % cols) * cell + 10, (i // cols) * 130 + 8
        p.fillRect(x0, y0, 110, 110, QColor("#f1f1f1"))
        p.fillRect(x0 + 110, y0, 110, 110, QColor("#262626"))
        c = render_image(n, px)
        hx, hy = hotspot(n, px)
        for bx in (x0 + 7, x0 + 117):
            p.drawImage(bx, y0 + 7, c)
            p.setBrush(QColor("#e0245e"))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(bx + hx - 2, y0 + 7 + hy - 2, 5, 5)
        p.setPen(QColor("#111111"))
        p.drawText(x0, y0 + 124, n)
    p.end()
    img.save(str(path))


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "cursors_out")
    for d in ("svg", "png", "cur"):
        (out / d).mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name in CURSORS:
        (out / "svg" / f"{name}.svg").write_text(build_svg(name), encoding="utf-8")
        entries = []
        for px in SIZES:
            png = png_bytes(render_image(name, px))
            (out / "png" / f"{name}_{px}.png").write_bytes(png)
            hx, hy = hotspot(name, px)
            entries.append((px, hx, hy, png))
        write_cur(out / "cur" / f"{name}.cur", entries)
        manifest[name] = {"hotspot_32": CURSORS[name][0]}
    (out / "cursors.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "preview.html").write_text(preview_html(), encoding="utf-8")
    contact_sheet(out / "sheet.png")
    print(f"ready: {len(CURSORS)} cursors -> {out.resolve()}")


if __name__ == "__main__":
    main()
