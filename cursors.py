"""Cursor shapes, drawing primitives, and shared style settings."""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Callable

# ============================== STYLE ======================================
GRID = 32            # logical cursor grid
COMPACT_PREVIEW_SIZE = 28
SW = 1.8             # thickness of all outlines and lines
H = 1.8              # halo width
CUR_SIZES = (96,)    # sizes included in .cur files
PNG_SIZE = max(CUR_SIZES)  # the PNG is exported at the largest .cur size

# Allowed region: every cursor, halo included, stays at least PADDING away from all four canvas edges.
# Shapes derived from the constants below follow PADDING automatically; hand-drawn geometry
# (hands, arrow, scissors, wand, bucket) is verified by check_padding() in main.py.
PADDING = 1.0
LINE_REACH = SW / 2 + H            # how far a line's halo sticks out past its centerline
PAPER_REACH = SW + H               # same for outlined forms (stroke on both sides of the edge)
LINE_INSET = PADDING + LINE_REACH  # nearest a line's centerline may get to a canvas edge
LINE_FAR_EDGE = GRID - LINE_INSET  # farthest a line's centerline may reach

# Color themes: "dark" = white outline on black paper (default), "light" = black on white
THEMES = {
    "dark":  {"ink": "#ffffff", "paper": "#000000", "halo": "#000000"},
    "light": {"ink": "#000000", "paper": "#ffffff", "halo": "#ffffff"},
}
THEME = "dark"       # default export theme; change to "light" for the inverse
# ===========================================================================

@dataclass
class Shape:
    """A single cursor element.

    kind:
      paper - light form with a dark outline (closed path, rect, circle)
      fill  - light form with an outline of thickness w drawn over the fill (folds stay visible)
      pline - thick light line with rounded ends and outline (fingers, thumb)
      ink   - solid dark form
      solid - solid dark form with a rounded outline of thickness w (arrowheads, corners)
      line  - dark line with thickness w (symbols +, -, ^, etc.)
    top: drawn above everything else, without a halo (details inside forms)
    """
    el: str
    geom: str
    kind: str
    w: float = 0.0
    top: bool = False
    xf: str = ""
    line_join: str = "round"

    def tag(self, attrs: str) -> str:
        t = f' transform="{self.xf}"' if self.xf else ""
        return f"<{self.el} {self.geom} {attrs}{t}/>"


def _stroke(color: str, width: float, fill: str = "none", line_join: str = "round") -> str:
    return f'fill="{fill}" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="{line_join}"'


def _flat(color: str) -> str:
    return f'fill="{color}" stroke="none"'


def render(shapes: list[Shape], theme: str | None = None) -> str:
    """theme: 'dark' | 'light' | None (= THEME)."""
    colors = THEMES[theme or THEME]
    ink, paper, halo = colors["ink"], colors["paper"], colors["halo"]
    body = [s for s in shapes if not s.top]
    details = [s for s in shapes if s.top]
    out: list[str] = []
    # 1) halo
    for s in body:
        if s.kind == "paper":
            attrs = _stroke(halo, 2 * (SW + H), fill=halo, line_join=s.line_join)
        elif s.kind == "pline":
            attrs = _stroke(halo, s.w + 2 * (SW + H), line_join=s.line_join)
        elif s.kind == "ink":
            attrs = _stroke(halo, 2 * H, fill=halo, line_join=s.line_join)
        elif s.kind in ("fill", "solid"):
            attrs = _stroke(halo, s.w + 2 * H, fill=halo, line_join=s.line_join)
        else:
            attrs = _stroke(halo, s.w + 2 * H, line_join=s.line_join)
        out.append(s.tag(attrs))
    # 2) outline / dark forms
    for s in body:
        if s.kind == "paper":
            attrs = _stroke(ink, 2 * SW, fill=ink, line_join=s.line_join)
        elif s.kind == "pline":
            attrs = _stroke(ink, s.w + 2 * SW, line_join=s.line_join)
        elif s.kind == "ink":
            attrs = _flat(ink)
        elif s.kind == "fill":
            attrs = _stroke(ink, s.w, fill=paper, line_join=s.line_join)
        elif s.kind == "solid":
            attrs = _stroke(ink, s.w, fill=ink, line_join=s.line_join)
        else:
            attrs = _stroke(ink, s.w, line_join=s.line_join)
        out.append(s.tag(attrs))
    # 3) light fill on top (eraser for internal intersection lines)
    for s in body:
        if s.kind == "paper":
            out.append(s.tag(_flat(paper)))
        elif s.kind == "pline":
            out.append(s.tag(_stroke(paper, s.w, line_join=s.line_join)))
    # 4) top details
    for s in details:
        if s.kind == "halo":
            attrs = _flat(halo)
        else:
            attrs = _flat(ink) if s.kind == "ink" else _stroke(ink, s.w, line_join=s.line_join)
        out.append(s.tag(attrs))
    return "\n".join(out)


# ============================ GEOMETRY ====================================

def _path(*segments: str) -> str:
    """Joins named path segments into one path string."""
    return " ".join(segments)


def path_shape(
    path_data: str,
    kind: str,
    width: float = 0.0,
    top: bool = False,
    xf: str = "",
    line_join: str = "round",
) -> Shape:
    return Shape("path", f'd="{path_data}"', kind, width, top, xf, line_join)


def _number(value: float) -> str:
    return f"{round(value, 2) + 0.0:g}"


def _dot(cx: float, cy: float, radius: float, xf: str = "") -> list[Shape]:
    geom = f'cx="{_number(cx)}" cy="{_number(cy)}"'
    return [
        Shape("circle", f'{geom} r="{_number(radius + H)}"', "halo", top=True, xf=xf),
        Shape("circle", f'{geom} r="{_number(radius)}"', "ink", top=True, xf=xf),
    ]


def _direction(origin: tuple[float, float], target: tuple[float, float]) -> tuple[float, float, float]:
    """Unit vector from origin to target and the distance between them."""
    delta_x, delta_y = target[0] - origin[0], target[1] - origin[1]
    distance = math.hypot(delta_x, delta_y)
    return delta_x / distance, delta_y / distance, distance


def rounded_polygon(points: list[tuple[float, float]], radius: float | list[float]) -> str:
    """Closed path through `points` with every corner replaced by a circular arc.
    radius is shared by all corners or given per corner; 0 keeps a corner sharp."""
    count = len(points)
    radii = [radius] * count if isinstance(radius, (int, float)) else list(radius)
    segments: list[str] = []
    for index, (corner, corner_radius) in enumerate(zip(points, radii)):
        previous_x, previous_y, previous_length = _direction(corner, points[index - 1])
        next_x, next_y, next_length = _direction(corner, points[(index + 1) % count])
        command = "M" if index == 0 else "L"
        if corner_radius == 0:
            segments.append(f"{command}{_number(corner[0])} {_number(corner[1])}")
            continue
        half_angle = math.acos(max(-1.0, min(1.0, previous_x * next_x + previous_y * next_y))) / 2
        cut = min(corner_radius / math.tan(half_angle), previous_length / 2, next_length / 2)
        arc_radius = cut * math.tan(half_angle)
        turn = (-previous_x) * next_y - (-previous_y) * next_x
        start = (corner[0] + previous_x * cut, corner[1] + previous_y * cut)
        end = (corner[0] + next_x * cut, corner[1] + next_y * cut)
        segments.append(
            f"{command}{_number(start[0])} {_number(start[1])} "
            f"A{_number(arc_radius)} {_number(arc_radius)} 0 0 {int(turn > 0)} {_number(end[0])} {_number(end[1])}")
    return _path(*segments, "Z")


_STAR_POINTS = 5
_STAR_INNER_RATIO = 0.45     # inner point radius / outer point radius
_STAR_ROUNDING_RATIO = 0.1   # corner radius / outer point radius


def star(outer_radius: float) -> str:
    """Star around the origin with _STAR_POINTS outer and as many inner points, all corners rounded.
    One outer point looks straight up."""
    points = []
    for index in range(2 * _STAR_POINTS):
        radius = outer_radius if index % 2 == 0 else outer_radius * _STAR_INNER_RATIO
        angle = math.radians(-90 + index * 180 / _STAR_POINTS)
        points.append((radius * math.cos(angle), radius * math.sin(angle)))
    return rounded_polygon(points, outer_radius * _STAR_ROUNDING_RATIO)


def arrow() -> list[Shape]:
    """Default pointer: rounded triangle, minimal points (two per corner), the top-left corner is the hotspot."""
    start = "M6 6.2"
    top_left_corner = "C6 4.3 7.7 4.3 8.6 5.1"
    upper_edge = "L22.06 17.3"
    right_tip = "C22.8 18 22.6 19.5 21.7 19.7"
    concave_lower_edge = "C15.7 21.6 11.1 24.3 8.3 27.1"
    bottom_left_corner = "C7.6 27.8 6 27.5 6 25.9"  # the left edge closes the path
    outline = _path(start, top_left_corner, upper_edge, right_tip, concave_lower_edge, bottom_left_corner, "Z")
    return [path_shape(outline, "paper")]


_LENS_RADIUS = 8.4
_LENS_CENTER = PADDING + PAPER_REACH + _LENS_RADIUS   # the lens touches the top left of the allowed region
_ZOOM_SIGN_ARM = 3.8
_HANDLE_RADIUS = 2.2
_HANDLE_START_DISTANCE = 9.5   # from the lens center; the flat end hides under the lens outline
_HALF_DIAGONAL = math.sqrt(0.5)   # cos(45 degrees): the handle runs along the grid diagonal
_HANDLE_END = GRID - PADDING - H - _HANDLE_RADIUS   # round end touches the bottom right of the allowed region


def zoom(sign: str) -> list[Shape]:
    center, arm = _LENS_CENTER, _ZOOM_SIGN_ARM
    side = _HANDLE_RADIUS * _HALF_DIAGONAL   # offset of the handle edges from its axis on each grid axis
    start = center + _HANDLE_START_DISTANCE * _HALF_DIAGONAL
    handle = _path(f"M{_number(start - side)} {_number(start + side)}",
                   f"L{_number(start + side)} {_number(start - side)}",
                   f"L{_number(_HANDLE_END + side)} {_number(_HANDLE_END - side)}",
                   f"A{_HANDLE_RADIUS} {_HANDLE_RADIUS} 0 0 1 {_number(_HANDLE_END - side)} {_number(_HANDLE_END + side)}",
                   "Z")
    horizontal_bar = f"M{center - arm} {center} H{center + arm}"
    vertical_bar = f"M{center} {center - arm} V{center + arm}"
    bars = _path(horizontal_bar, vertical_bar) if sign == "+" else horizontal_bar
    return [
        Shape("circle", f'cx="{center}" cy="{center}" r="{_LENS_RADIUS}"', "paper"),
        path_shape(handle, "ink"),
        path_shape(bars, "line", SW, top=True),
    ]


# Eyedropper, pen nib and knife are drawn along the local -y axis from the tip at the hotspot, tilted 45 degrees.
# The tip sits in the bottom left corner of the allowed region.
_TOOL_TIP = (PADDING + PAPER_REACH, GRID - PADDING - PAPER_REACH)
_TOOL_TIP_ANGLE = 45
_TOOL_TIP_XF = f"translate({_number(_TOOL_TIP[0])} {_number(_TOOL_TIP[1])}) rotate({_TOOL_TIP_ANGLE})"


def eyedropper() -> list[Shape]:
    tip, neck, tube_end = "M0 0", "-7", "-17.5"
    tube = _path(tip, f"L-2.7 {neck}", f"L-2.7 {tube_end}", f"L2.7 {tube_end}", f"L2.7 {neck}", "Z")
    cap = rounded_polygon([(-4.5, -21.5), (4.5, -21.5), (4.5, -17), (-4.5, -17)], 1.2)
    return [
        path_shape(_path(tube, cap), "paper", xf=_TOOL_TIP_XF),
        Shape("rect", 'x="-3.5" y="-31" width="7" height="10.5" rx="3.5"', "ink", xf=_TOOL_TIP_XF),
    ]


# Hands are in 32x32 grid coordinates, fitted to the allowed region with outline and halo.
# The closed hand has the same scale and anchor (two states of one cursor, so it is not enlarged).
# One outline runs from the wrist over thumb and fingers, then down the palm back to the wrist.
# Parts that differ between "grab" (open hand) and "grabbing" (fist) keep both variants, "pointer"
# mixes them (see _HAND_GRAB_PARTS). The line between two fingers is part of the outline: it runs
# down the edge of a finger to its base and back up along the next one.
_HAND_START = "M 15.35 28.3"
_HAND_WRIST = "C 14.96 28.3 14.57 28.21 14.22 28.05 C 13.51 27.73 12.32 27.02 11.08 25.54"
_HAND_PALM = (
    "C 26.66 21 25.66 24.93 23.65 27.32 C 23.13 27.94 22.36 28.3 21.55 28.3 "
    "C 19.82 28.3 16.56 28.3 15.35 28.3"
)

_HAND_PARTS = {
    "thumb": {
        "grab": "C 9.1 23.2 6.7 18.81 5.49 16.5 C 5.03 15.63 5.27 14.55 6.04 13.94 "
                "C 6.94 13.25 8.2 13.4 8.9 14.27 L 12.26 18.51",
        "grabbing": "C 9.7 23.91 8.88 21.79 8.5 20.66 C 8.32 20.11 8.38 19.5 8.68 19 "
                    "C 9.22 18.08 10.33 16.68 12.26 16.29 L 12.26 18.51",
    },
    "index": {
        "grab": "L 12.26 6.93 C 12.26 5.93 13.07 5.12 14.07 5.12 "
                "C 15.07 5.12 15.87 5.93 15.87 6.93 L 15.87 15.43",
        "grabbing": "L 12.26 13.56 C 12.26 12.56 13.07 11.75 14.07 11.75 "
                    "C 15.07 11.75 15.87 12.56 15.87 13.56 L 15.87 15.43",
    },
    "middle": {
        "grab": "L 15.87 5.51 C 15.87 5.03 16.07 4.57 16.4 4.23 C 16.74 3.89 17.2 3.7 17.68 3.7 "
                "C 18.16 3.7 18.62 3.89 18.96 4.23 C 19.3 4.57 19.49 5.03 19.49 5.51 "
                "L 19.49 15.53",
        "grabbing": "L 15.87 12.48 C 15.87 12 16.07 11.54 16.4 11.2 "
                    "C 16.74 10.86 17.2 10.67 17.68 10.67 C 18.16 10.67 18.62 10.86 18.96 11.2 "
                    "C 19.3 11.54 19.49 12 19.49 12.48 L 19.49 15.53",
    },
    "ring": {
        "grab": "L 19.49 7.6 C 19.49 7.13 19.68 6.67 20.02 6.33 C 20.36 5.99 20.82 5.8 21.31 5.8 "
                "C 21.81 5.8 22.26 5.99 22.6 6.33 C 22.94 6.67 23.13 7.13 23.13 7.6 L 23.13 16.29",
        "grabbing": "L 19.49 13.43 C 19.49 12.95 19.68 12.5 20.02 12.16 "
                    "C 20.36 11.82 20.82 11.63 21.31 11.63 C 21.81 11.63 22.26 11.82 22.6 12.16 "
                    "C 22.94 12.5 23.13 12.95 23.13 13.43 L 23.13 16.29",
    },
    "little": {
        "grab": "L 23.13 9.6 C 23.13 9.13 23.32 8.67 23.66 8.33 C 24 7.99 24.46 7.8 24.94 7.8 "
                "C 25.42 7.8 25.88 7.99 26.21 8.33 C 26.55 8.67 26.74 9.13 26.74 9.6 "
                "L 26.74 15.71",
        "grabbing": "L 23.13 15.43 C 23.13 14.95 23.32 14.5 23.66 14.16 "
                    "C 24 13.82 24.46 13.63 24.94 13.63 C 25.42 13.63 25.88 13.82 26.21 14.16 "
                    "C 26.55 14.5 26.74 14.95 26.74 15.43 L 26.74 15.71",
    },
}

_HAND_GRAB_PARTS = {   # parts drawn in their "grab" variant, the others use "grabbing"
    "grab": tuple(_HAND_PARTS),
    "grabbing": (),
    "pointer": ("thumb", "index"),
}


def _hand(pose: str) -> list[Shape]:
    grab_parts = _HAND_GRAB_PARTS[pose]

    def variant(name: str) -> str:
        return "grab" if name in grab_parts else "grabbing"

    fingers = (parts[variant(name)] for name, parts in _HAND_PARTS.items())
    outline = _path(_HAND_START, _HAND_WRIST, *fingers, _HAND_PALM, "Z")
    return [path_shape(outline, "fill", SW)]


_NIB_SLIT = 13.14  # slit length from the tip; the dot sits at its end


def pen_nib() -> list[Shape]:
    tip = "M0 0"
    left_flank = "L-5.4 -11.79"
    left_shoulder = "Q-6 -17.97 -4.2 -20.44"
    top_edge = "L4.2 -20.44"
    right_shoulder = "Q6 -17.97 5.4 -11.79"
    nib = _path(tip, left_flank, left_shoulder, top_edge, right_shoulder, "Z")
    return [
        path_shape(nib, "paper", xf=_TOOL_TIP_XF),
        Shape("rect", 'x="-4.2" y="-31" width="8.4" height="11.68" rx="1.6"', "ink", xf=_TOOL_TIP_XF),
        path_shape(f"M0 0 V{-_NIB_SLIT}", "line", SW, top=True, xf=_TOOL_TIP_XF),
        Shape("circle", f'cx="0" cy="{-_NIB_SLIT}" r="1.65"', "ink", top=True, xf=_TOOL_TIP_XF),
    ]


# Knife: blade (outlined) sits on the handle (solid); the blade tip is the hotspot, the tip is off the handle axis.
_KNIFE_SEAM = -17.92         # where the blade ends and the handle starts
_KNIFE_SPINE = -2.54         # the blunt upper edge; the handle is flush with its outline
_KNIFE_HANDLE_WIDTH = 5.47
_KNIFE_HANDLE_END = -31


def knife() -> list[Shape]:
    seam, side_a = _KNIFE_SEAM, _KNIFE_SPINE - SW
    side_b, end_radius = side_a + _KNIFE_HANDLE_WIDTH, _KNIFE_HANDLE_WIDTH / 2
    blade = _path("M0 0", f"Q-3.17 -5.34 {_KNIFE_SPINE} {seam}", f"L4.31 {seam}", "L3.68 -7.94", "C3.39 -3.48 0 0 0 0", "Z")
    handle = rounded_polygon([(side_a, seam), (side_b, seam), (side_b, _KNIFE_HANDLE_END), (side_a, _KNIFE_HANDLE_END)],
                             [0, 0, end_radius, end_radius])
    return [path_shape(blade, "paper", xf=_TOOL_TIP_XF), path_shape(handle, "ink", xf=_TOOL_TIP_XF)]


# Magnet: horseshoe and poles sit above the hotspot, matching the other rotated tool cursors.
_MAGNET_ORIGIN = (7.9, 24.1)
_MAGNET_OUTER = 9.8
_MAGNET_ARM = 5.93
_MAGNET_BEND_Y = -15.96
_MAGNET_POLE_Y = -4.33       # pole faces
_MAGNET_POLE_LENGTH = 5.47
_MAGNET_POLE_GAP = SW        # visible gap between a pole and the body
_MAGNET_DOT_RADIUS = 2
_MAGNET_DOT_OFFSET = 0.8
_MAGNET_XF = f"translate({_MAGNET_ORIGIN[0]} {_MAGNET_ORIGIN[1]}) rotate({_TOOL_TIP_ANGLE})"


def magnet() -> list[Shape]:
    outer, inner, bend = _MAGNET_OUTER, _MAGNET_OUTER - _MAGNET_ARM, _MAGNET_BEND_Y
    pole_top = _MAGNET_POLE_Y - _MAGNET_POLE_LENGTH
    body_end = pole_top - _MAGNET_POLE_GAP
    body = _path(f"M{-outer} {body_end} V{bend} A{outer} {outer} 0 0 1 {outer} {bend} V{body_end}",
                 f"H{inner} V{bend} A{inner} {inner} 0 0 0 {-inner} {bend} V{body_end} Z")
    poles = [f"M{_number(x)} {_number(pole_top)} h{_MAGNET_ARM} v{_MAGNET_POLE_LENGTH} h{-_MAGNET_ARM} Z"
             for x in (-outer, inner)]
    return [
        path_shape(_path(body, *poles), "ink", xf=_MAGNET_XF, line_join="miter"),
        *_dot(0, _MAGNET_DOT_OFFSET, _MAGNET_DOT_RADIUS, xf=_MAGNET_XF),
    ]


_CANVAS_CENTER = GRID // 2
_CENTER_DOT_RADIUS = 2


def crosshair() -> list[Shape]:
    """Precision crosshair with four separate arms and an open center; the arm ends touch the allowed region."""
    center, gap, near, far = _CANVAS_CENTER, 5, _number(LINE_INSET), _number(LINE_FAR_EDGE)
    left_arm = f"M{near} {center} H{center - gap}"
    right_arm = f"M{center + gap} {center} H{far}"
    top_arm = f"M{center} {near} V{center - gap}"
    bottom_arm = f"M{center} {center + gap} V{far}"
    return [
        path_shape(_path(left_arm, right_arm, top_arm, bottom_arm), "line", SW),
        *_dot(center, center, _CENTER_DOT_RADIUS),
    ]


def artboard() -> list[Shape]:
    """Artboard cursor with the stepped lower-right frame; the line ends touch the allowed region."""
    near, far = _number(LINE_INSET), _number(LINE_FAR_EDGE)
    outline = f"M{near} 16 H11 M21 16 H{far} V{far} M16 {near} V11 M16 21 V{far} H{far}"
    return [
        path_shape(outline, "line", SW),
        *_dot(_CANVAS_CENTER, _CANVAS_CENTER, _CENTER_DOT_RADIUS),
    ]


_CROP_RING_RADIUS = 6.5
_CROP_ARM_OUTER_RADIUS = _CANVAS_CENTER - LINE_INSET   # the arm ends touch the allowed region


def crop() -> list[Shape]:
    """Crop tool target with arms meeting the circular ring."""
    center = _CANVAS_CENTER
    inner, outer = _CROP_RING_RADIUS, _CROP_ARM_OUTER_RADIUS
    arms = _path(
        f"M{center} {_number(center - outer)} V{center - inner}",
        f"M{center + inner} {center} H{_number(center + outer)}",
        f"M{center} {center + inner} V{_number(center + outer)}",
        f"M{_number(center - outer)} {center} H{center - inner}",
    )
    return [
        path_shape(arms, "line", SW),
        Shape("circle", f'cx="{center}" cy="{center}" r="{_CROP_RING_RADIUS}"', "paper"),
        *_dot(center, center, _CENTER_DOT_RADIUS),
    ]


# Crop frame: corner brackets in the allowed region; the top left corner is closed into a solid triangle
# (arrow-like) and is the hotspot.
_CROP_FRAME_ARM = 7
_CROP_FRAME_HOTSPOT = (LINE_INSET, LINE_INSET)


def crop_frame() -> list[Shape]:
    """Crop tool: arrow corner at the top left plus three corner brackets of the frame."""
    near, far, arm = LINE_INSET, LINE_FAR_EDGE, _CROP_FRAME_ARM
    triangle = _path(f"M{_number(near)} {_number(near)}", f"H{_number(near + arm)}", f"L{_number(near)} {_number(near + arm)}", "Z")
    top_right = f"M{_number(far - arm)} {_number(near)} H{_number(far)} V{_number(near + arm)}"
    bottom_right = f"M{_number(far)} {_number(far - arm)} V{_number(far)} H{_number(far - arm)}"
    bottom_left = f"M{_number(near + arm)} {_number(far)} H{_number(near)} V{_number(far - arm)}"
    return [
        path_shape(triangle, "solid", SW),
        path_shape(_path(top_right, bottom_right, bottom_left), "line", SW),
    ]


# Direction cursors: solid arrowheads at the allowed region edge, joined by shafts through the canvas center.
_ARROW_REACH = _CANVAS_CENTER - LINE_INSET   # center to arrow tip
_ARROW_HEAD_LENGTH = 5.5
_ARROW_HEAD_HALF_WIDTH = 3.6


def _arrow_head(direction_x: int, direction_y: int) -> str:
    """Triangle path with its tip at the allowed region edge, pointing along the direction."""
    tip_x, tip_y = _CANVAS_CENTER + direction_x * _ARROW_REACH, _CANVAS_CENTER + direction_y * _ARROW_REACH
    base_x, base_y = tip_x - direction_x * _ARROW_HEAD_LENGTH, tip_y - direction_y * _ARROW_HEAD_LENGTH
    side_x, side_y = -direction_y * _ARROW_HEAD_HALF_WIDTH, direction_x * _ARROW_HEAD_HALF_WIDTH
    return _path(f"M{_number(tip_x)} {_number(tip_y)}",
                 f"L{_number(base_x + side_x)} {_number(base_y + side_y)}",
                 f"L{_number(base_x - side_x)} {_number(base_y - side_y)}", "Z")


def arrows(horizontal: bool, vertical: bool) -> list[Shape]:
    """Double arrows along the chosen axes: resize for one axis, move for both."""
    shaft_reach = _ARROW_REACH - _ARROW_HEAD_LENGTH
    axes = [axis for axis, enabled in (((1, 0), horizontal), ((0, 1), vertical)) if enabled]
    shafts = [f"M{_number(_CANVAS_CENTER - axis_x * shaft_reach)} {_number(_CANVAS_CENTER - axis_y * shaft_reach)} "
              f"L{_number(_CANVAS_CENTER + axis_x * shaft_reach)} {_number(_CANVAS_CENTER + axis_y * shaft_reach)}"
              for axis_x, axis_y in axes]
    heads = [_arrow_head(sign * axis_x, sign * axis_y) for axis_x, axis_y in axes for sign in (-1, 1)]
    return [path_shape(_path(*shafts), "line", SW), path_shape(_path(*heads), "solid", SW)]


_WAND_TILT = 32
_SCISSORS_HOTSPOT = (10, 5.6)
_SCISSORS_XF = f"translate({_SCISSORS_HOTSPOT[0]} {_SCISSORS_HOTSPOT[1]}) rotate({-_WAND_TILT})"
_SCISSORS_PATH = (
    "M0 16.25 L-1.25 18.41 C-1.03 19.41 -1.17 20.49 -1.72 21.45 "
    "C-2.89 23.48 -5.5 24.18 -7.54 23.01 C-9.58 21.83 -10.27 19.22 "
    "-9.1 17.19 C-7.99 15.27 -5.62 14.54 -3.64 15.44 L-2.06 12.69 "
    "L-5.69 6.4 C-7.79 2.77 -5.27 0 -5.27 0 L0 9.12 L5.27 0 "
    "C5.27 0 7.79 2.77 5.69 6.4 L2.06 12.69 L3.64 15.44 "
    "C5.62 14.54 7.99 15.27 9.1 17.19 C10.27 19.22 9.58 21.83 "
    "7.54 23.01 C5.5 24.18 2.89 23.48 1.72 21.45 "
    "C1.17 20.49 1.03 19.41 1.25 18.41 L0 16.25 Z "
    "M4.45 17.66 C3.54 18.19 3.22 19.36 3.75 20.27 "
    "C4.28 21.19 5.45 21.5 6.36 20.97 C7.28 20.44 7.59 19.27 "
    "7.06 18.36 C6.54 17.45 5.37 17.13 4.45 17.66 Z "
    "M-4.45 17.66 C-5.37 17.13 -6.54 17.45 -7.06 18.36 "
    "C-7.59 19.27 -7.28 20.44 -6.36 20.97 C-5.45 21.5 -4.28 21.19 "
    "-3.75 20.27 C-3.22 19.36 -3.54 18.19 -4.45 17.66 Z"
)


def scissors() -> list[Shape]:
    """Scissors point down in local coordinates and rotate to the Magic Wand angle."""
    return [path_shape(_SCISSORS_PATH, "ink", xf=_SCISSORS_XF)]


# Magic wand: a star on top of a straight stick that narrows towards it; the whole cursor rotates together.
_WAND_CENTER = (10, 9.2)    # hotspot: the star center
_WAND_STAR_RADIUS = 8.8
_WAND_TIP_WIDTH = 2.8        # stick width next to the star
_WAND_HANDLE_WIDTH = 4.6
_WAND_LENGTH = 23.2           # from the star center to the handle end
_WAND_STAR_STICK_GAP = 0    # visible gap between the outlined star and stick


def magic_wand() -> list[Shape]:
    """Magic wand: star on a tapered stick."""
    center_x, center_y = _WAND_CENTER
    transform = f"translate({center_x} {center_y}) rotate({-_WAND_TILT})"
    tip_half, handle_half = _WAND_TIP_WIDTH / 2, _WAND_HANDLE_WIDTH / 2
    star_notch = _WAND_STAR_RADIUS * _STAR_INNER_RATIO
    stick_start = star_notch + 2 * SW + _WAND_STAR_STICK_GAP - tip_half
    corners = [(-tip_half, stick_start), (tip_half, stick_start),
               (handle_half, _WAND_LENGTH), (-handle_half, _WAND_LENGTH)]
    stick = rounded_polygon(corners, [tip_half, tip_half, handle_half, handle_half])
    return [path_shape(_path(star(_WAND_STAR_RADIUS), stick), "ink", xf=transform)]


# Fill (paint bucket): the bucket is drawn upright around its own origin and tilted to pour to the left;
# the drop falls below the lower rim end and its lowest point is the hotspot.
_BUCKET_CENTER = (18.9, 17.2)
_BUCKET_TILT = 35            # degrees counter-clockwise
_BUCKET_RIM_HALF = 8.7       # half width at the rim (top)
_BUCKET_BASE_HALF = 5.5      # half width at the base (bottom)
_BUCKET_HALF_HEIGHT = 7.7
_BUCKET_RIM_ROUNDING = 1.1
_BUCKET_BASE_ROUNDING = 2.2
_BUCKET_HANDLE_RISE = 8.4  # how far the handle arc rises above the rim
_DROP_HOTSPOT = (6, GRID - PADDING - H)   # the lowest point touches the bottom of the allowed region
_DROP_RADIUS = 2.6
_DROP_HEIGHT = 6.8           # from the pointed top to the lowest point


def fill() -> list[Shape]:
    """Paint bucket tilted to pour, with a drop under the rim."""
    center_x, center_y = _BUCKET_CENTER
    transform = f"translate({center_x} {center_y}) rotate({-_BUCKET_TILT})"
    rim, base = -_BUCKET_HALF_HEIGHT, _BUCKET_HALF_HEIGHT
    body = rounded_polygon([(-_BUCKET_RIM_HALF, rim), (_BUCKET_RIM_HALF, rim),
                            (_BUCKET_BASE_HALF, base), (-_BUCKET_BASE_HALF, base)],
                           [_BUCKET_RIM_ROUNDING, _BUCKET_RIM_ROUNDING, _BUCKET_BASE_ROUNDING, _BUCKET_BASE_ROUNDING])
    handle_top = rim - _BUCKET_HANDLE_RISE
    handle = _path(f"M{-_BUCKET_RIM_HALF} {rim}",
                   f"C{-_BUCKET_RIM_HALF} {handle_top} {_BUCKET_RIM_HALF} {handle_top} {_BUCKET_RIM_HALF} {rim}")
    drop_x, drop_bottom = _DROP_HOTSPOT
    drop_center_y = drop_bottom - _DROP_RADIUS
    drop_top = drop_bottom - _DROP_HEIGHT
    drop = _path(f"M{drop_x} {drop_top}",
                 f"C{drop_x - _DROP_RADIUS * 0.5} {drop_top + 2.2} {drop_x - _DROP_RADIUS} {drop_center_y - 1.2} "
                 f"{drop_x - _DROP_RADIUS} {drop_center_y}",
                 f"A{_DROP_RADIUS} {_DROP_RADIUS} 0 0 0 {drop_x + _DROP_RADIUS} {drop_center_y}",
                 f"C{drop_x + _DROP_RADIUS} {drop_center_y - 1.2} {drop_x + _DROP_RADIUS * 0.5} {drop_top + 2.2} "
                 f"{drop_x} {drop_top}",
                 "Z")
    return [
        path_shape(handle, "line", SW, xf=transform),
        path_shape(body, "paper", xf=transform),
        path_shape(drop, "ink"),
    ]


# Extra elements ("badges") are attached next to a base cursor; the base is never shrunk.
# If an element does not fit into the base's 32x32 grid, the canvas of that cursor grows to the right
# and down (the hotspot stays where it was, the origin is the top left corner).
# Every glyph is drawn once around its own origin (0, 0) and no glyph reaches farther than _BADGE_HALF_SIZE,
# so all badges share one origin in the bottom right corner of the allowed region.
#   "shared" - universal marks (+, -), usable on any cursor;
#   "<base>" - marks of one tool, so a bulky mark never constrains the others.
# add_badged() looks in the base's group first, then in "shared".
_BADGE_HALF_SIZE = 2.8
BADGE_ORIGIN = GRID - PADDING - LINE_REACH - _BADGE_HALF_SIZE
BADGES: dict[str, dict[str, list[Shape]]] = {
    "shared": {
        "plus": [path_shape("M-2.8 0 H2.8 M0 -2.8 V2.8", "line", SW)],
        "minus": [path_shape("M-2.8 0 H2.8", "line", SW)],
    },
    "pen": {
        "wave": [path_shape("M-3.8 1.4 Q-2.15 -1.4 -0.5 1.4 T2.8 1.4", "line", SW)],
        "curve": [path_shape("M-4.6 2.8 C-1.4 2.8 -1.4 -3.6 2.8 -3.6", "line", SW)],
        "caret": [path_shape("M-3 2.6 L0 -1.8 L2.8 2.6", "line", SW)],
        "ring": [Shape("circle", 'cx="0" cy="0" r="2.5"', "line", SW)],
    },
}

# Canvas size in grid units, only for cursors that do not fit 32x32 (name -> (width, height)).
CANVAS: dict[str, tuple[float, float]] = {}


# name -> (hotspot on the 32x32 grid, shape factory)
CURSORS: dict[str, tuple[tuple[float, float], Callable[[], list[Shape]]]] = {
    "arrow": ((7, 4.5), arrow),
    "zoom_in": ((_LENS_CENTER, _LENS_CENTER), lambda: zoom("+")),
    "zoom_out": ((_LENS_CENTER, _LENS_CENTER), lambda: zoom("-")),
    "eyedropper": (_TOOL_TIP, eyedropper),
    "grab": ((_CANVAS_CENTER, _CANVAS_CENTER), lambda: _hand("grab")),
    "grabbing": ((_CANVAS_CENTER, _CANVAS_CENTER), lambda: _hand("grabbing")),
    "pointer": ((_CANVAS_CENTER, _CANVAS_CENTER), lambda: _hand("pointer")),
    "pen": (_TOOL_TIP, pen_nib),
    "knife": (_TOOL_TIP, knife),
    "magnetic_lasso": (_MAGNET_ORIGIN, magnet),
    "crosshair": ((_CANVAS_CENTER, _CANVAS_CENTER), crosshair),
    "artboard": ((_CANVAS_CENTER, _CANVAS_CENTER), artboard),
    "crop": ((_CANVAS_CENTER, _CANVAS_CENTER), crop),
    "crop_frame": (_CROP_FRAME_HOTSPOT, crop_frame),
    "resize_horizontal": ((_CANVAS_CENTER, _CANVAS_CENTER), lambda: arrows(horizontal=True, vertical=False)),
    "resize_vertical": ((_CANVAS_CENTER, _CANVAS_CENTER), lambda: arrows(horizontal=False, vertical=True)),
    "move": ((_CANVAS_CENTER, _CANVAS_CENTER), lambda: arrows(horizontal=True, vertical=True)),
    "scissors": (_SCISSORS_HOTSPOT, scissors),
    "magic_wand": (_WAND_CENTER, magic_wand),
    "fill": (_DROP_HOTSPOT, fill),
}


def add_badged(name: str, base: str, badge: str, canvas: tuple[float, float] | None = None) -> None:
    """Registers cursor `name` = base cursor + badge. The hotspot is taken from the base.
    canvas: size in grid units if the badge goes beyond the base's 32x32 grid."""
    hot, base_factory = CURSORS[base]
    shapes = BADGES.get(base, {}).get(badge) or BADGES["shared"][badge]
    placed = [replace(s, xf=f"translate({_number(BADGE_ORIGIN)} {_number(BADGE_ORIGIN)})") for s in shapes]
    CURSORS[name] = (hot, lambda: base_factory() + placed)
    if canvas:
        CANVAS[name] = canvas


for name, (base, badge) in {
    "pen_freeform": ("pen", "wave"),
    "pen_curvature": ("pen", "curve"),
    "pen_add": ("pen", "plus"),
    "pen_delete": ("pen", "minus"),
    "pen_convert": ("pen", "caret"),
    "pen_close": ("pen", "ring"),
}.items():
    add_badged(name, base, badge)
# other tools reuse the same badges, e.g.: add_badged("select_add", "select", "plus")


def canvas_size(name: str) -> tuple[float, float]:
    return CANVAS.get(name, (GRID, GRID))


def build_svg(name: str, size: int = GRID, theme: str | None = None) -> str:
    """size = pixels per GRID units, so the scale is the same for every canvas.
    Width/height are integers when size is integer so the rasterizer hits whole pixels."""
    hot, factory = CURSORS[name]
    canvas_width, canvas_height = canvas_size(name)
    width = round(canvas_width * size / GRID)
    height = round(canvas_height * size / GRID)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {canvas_width:g} {canvas_height:g}" shape-rendering="geometricPrecision">\n'
            f'<!-- hotspot: {_number(hot[0])},{_number(hot[1])} -->\n{render(factory(), theme=theme)}\n</svg>\n')