"""Cursor shapes, drawing primitives, and shared style settings."""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Callable

from gridfit import (
    Fit,
    number,
    pixel,
)

# ============================== STYLE ======================================
GRID = 32            # logical cursor grid: one unit is exactly one pixel at the base size
SW = 2               # thickness of all outlines and lines, whole pixels at the base size
H = 2                # halo width, whole pixels at the base size
# Windows asks for 32 px at 100% and 40/48/56/64/72/80/96 px at 125-300% scaling; 112 and 128 serve the
# larger cursor-size settings. Each entry is grid-fitted on its own, so every size stays sharp.
CUR_SIZES = (32, 40, 48, 56, 64, 72, 80, 96, 112, 128)
ACTUAL_SIZE = GRID         # size shown 1:1 in previews

# Allowed region: every cursor, halo included, stays at least PADDING away from all four canvas edges.
# Shapes derived from the constants below follow PADDING automatically; hand-drawn geometry
# (hands, arrow, scissors, wand, bucket) is verified by check_padding() in main.py.
PADDING = 1
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

# Cursor rotation angles, in degrees.
_TOOL_TIP_ANGLE = 45

# Shared rendering and canvas geometry.
_STROKED_KINDS = ("fill", "solid", "line", "inverse")   # kinds whose outline is centered on the path
_CANVAS_CENTER = GRID // 2
_CENTER_DOT_RADIUS = 2

# Shared by eyedropper, pen nib, and knife.
_TOOL_TIP = (PADDING + PAPER_REACH, GRID - PADDING - PAPER_REACH)
_TOOL_TRANSFORM = (*_TOOL_TIP, _TOOL_TIP_ANGLE)
_TOOL_LENGTH = 29.5


@dataclass
class Shape:
    """A single cursor element, drawn in grid units around its own origin.

    kind:
      paper - light form with a dark outline (closed path, circle)
      fill  - light form with an outline of thickness SW drawn over the fill (folds stay visible)
      inverse - solid ink form with paper-colored halo only (like ink, colors swapped; arrow family)
      ink   - solid dark form
      solid - solid dark form with an outline of thickness SW (arrowheads, corners)
      line  - dark line with thickness SW (symbols +, -, ^, etc.)
      dot   - solid dark circle with a halo, always drawn above everything else
    top: drawn above everything else, without a halo (details inside forms)
    transform: (x, y, angle) moves the origin to x, y and rotates by angle degrees; an unrotated shape
      is snapped to the pixel grid, a rotated one only has its origin snapped
    sharp: square line ends and mitered corners, for axis-aligned geometry that must stay crisp
    """
    kind: str
    path: str = ""
    circle: tuple[float, float, float] | None = None
    top: bool = False
    transform: tuple[float, float, float] = (0.0, 0.0, 0.0)
    sharp: bool = False


def _stroke(color: str, width: float, fill: str = "none", sharp: bool = False) -> str:
    cap, join = ("square", "miter") if sharp else ("round", "round")
    return f'fill="{fill}" stroke="{color}" stroke-width="{number(width)}" stroke-linecap="{cap}" stroke-linejoin="{join}"'


def _flat(color: str) -> str:
    return f'fill="{color}" stroke="none"'


def _place(shape: Shape, fit: Fit) -> Callable[..., str]:
    """Returns tag(attrs, grow=0): the shape as an SVG element in pixel units; grow widens a circle."""
    origin_x, origin_y, angle = shape.transform
    rotated = angle != 0
    origin = (0.0, 0.0) if rotated else (origin_x, origin_y)
    rotation = (f' transform="translate({number(pixel(origin_x * fit.scale))} '
                f'{number(pixel(origin_y * fit.scale))}) rotate({number(angle)})"') if rotated else ""
    if shape.circle is None:
        on_center = shape.kind in _STROKED_KINDS and fit.stroke % 2 == 1
        data = fit.path(shape.path, on_center, origin, snap=not rotated)
        return lambda attrs, grow=0.0: f'<path d="{data}" {attrs}{rotation}/>'
    outline_reach = fit.stroke if shape.kind in ("paper", "inverse") else fit.stroke / 2 if shape.kind in _STROKED_KINDS else 0
    center_x, center_y, radius = fit.circle(shape.circle, origin, not rotated, outline_reach)
    return lambda attrs, grow=0.0: (f'<circle cx="{number(center_x)}" cy="{number(center_y)}" '
                                    f'r="{number(radius + grow)}" {attrs}{rotation}/>')


def render(shapes: list[Shape], fit: Fit, theme: str | None = None) -> str:
    """theme: 'dark' | 'light' | None (= THEME)."""
    colors = THEMES[theme or THEME]
    ink, paper, halo = colors["ink"], colors["paper"], colors["halo"]
    stroke, halo_width = fit.stroke, fit.halo
    placed = [(shape, _place(shape, fit)) for shape in shapes]
    body = [(shape, tag) for shape, tag in placed if not shape.top and shape.kind != "dot"]
    details = [(shape, tag) for shape, tag in placed if shape.top or shape.kind == "dot"]
    out: list[str] = []
    # 1) halo
    for shape, tag in body:
        if shape.kind == "paper":
            attrs = _stroke(halo, 2 * (stroke + halo_width), halo, shape.sharp)
        elif shape.kind == "inverse":
            attrs = _stroke(ink, 2 * halo_width, ink, shape.sharp)  # pure opposite of ink
        elif shape.kind == "ink":
            attrs = _stroke(halo, 2 * halo_width, halo, shape.sharp)
        elif shape.kind in ("fill", "solid"):
            attrs = _stroke(halo, stroke + 2 * halo_width, halo, shape.sharp)
        else:
            attrs = _stroke(halo, stroke + 2 * halo_width, sharp=shape.sharp)
        out.append(tag(attrs))
    # 2) outline / dark forms
    for shape, tag in body:
        if shape.kind == "paper":
            attrs = _stroke(ink, 2 * stroke, ink, shape.sharp)
        elif shape.kind == "inverse":
            attrs = _flat(paper)
        elif shape.kind == "ink":
            attrs = _flat(ink)
        elif shape.kind == "fill":
            attrs = _stroke(ink, stroke, paper, shape.sharp)
        elif shape.kind == "solid":
            attrs = _stroke(ink, stroke, ink, shape.sharp)
        else:
            attrs = _stroke(ink, stroke, sharp=shape.sharp)
        out.append(tag(attrs))
    # 3) light fill on top (eraser for internal intersection lines)
    for shape, tag in body:
        if shape.kind == "paper":
            out.append(tag(_flat(paper)))
    # 4) top details
    for shape, tag in details:
        if shape.kind == "dot":
            out.append(tag(_flat(halo), halo_width))
            out.append(tag(_flat(ink)))
        elif shape.kind == "inverse":
            out.append(tag(_stroke(paper, stroke, ink, shape.sharp)))
        elif shape.kind == "ink":
            out.append(tag(_flat(ink)))
        else:
            out.append(tag(_stroke(ink, stroke, sharp=shape.sharp)))
    return "\n".join(out)


# ============================ GEOMETRY ====================================

def _path(*segments: str) -> str:
    """Joins named path segments into one path string."""
    return " ".join(segments)


def path_shape(
    path_data: str,
    kind: str,
    top: bool = False,
    transform: tuple[float, float, float] = (0.0, 0.0, 0.0),
    sharp: bool = False,
) -> Shape:
    return Shape(kind, path_data, None, top, transform, sharp)


def _circle(center_x: float, center_y: float, radius: float, kind: str, top: bool = False,
            transform: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> Shape:
    return Shape(kind, "", (center_x, center_y, radius), top, transform)


def _dot(center_x: float, center_y: float, radius: float,
         transform: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> Shape:
    return _circle(center_x, center_y, radius, "dot", transform=transform)


def _direction(origin: tuple[float, float], target: tuple[float, float]) -> tuple[float, float, float]:
    """Unit vector from origin to target and the distance between them."""
    delta_x, delta_y = target[0] - origin[0], target[1] - origin[1]
    distance = math.hypot(delta_x, delta_y)
    return delta_x / distance, delta_y / distance, distance


_MAX_CURVE_SWEEP = math.pi / 2   # one cubic per corner up to this angle, two (three nodes) beyond it


def _corner_curves(start: tuple[float, float], end: tuple[float, float], corner: tuple[float, float],
                   arc_radius: float, sweep: float) -> str:
    """Circular corner arc as one cubic, or two when it turns more than _MAX_CURVE_SWEEP."""
    start_x, start_y, _ = _direction(corner, start)
    end_x, end_y, _ = _direction(corner, end)
    # travel directions: start -> corner at the start, corner -> end at the end
    tangents = [(-start_x, -start_y), (end_x, end_y)]
    points = [start, end]
    if sweep > _MAX_CURVE_SWEEP:
        bisector_x, bisector_y = start_x + end_x, start_y + end_y
        length = math.hypot(bisector_x, bisector_y)
        middle_tangent = (end_x - start_x, end_y - start_y)
        tangent_length = math.hypot(*middle_tangent)
        center_distance = arc_radius / math.sin((math.pi - sweep) / 2)
        points.insert(1, (corner[0] + bisector_x / length * (center_distance - arc_radius),
                          corner[1] + bisector_y / length * (center_distance - arc_radius)))
        tangents.insert(1, (middle_tangent[0] / tangent_length, middle_tangent[1] / tangent_length))
    handle = 4 / 3 * math.tan(sweep / (len(points) - 1) / 4) * arc_radius
    curves = []
    for (from_point, from_tangent), (to_point, to_tangent) in zip(zip(points, tangents), zip(points[1:], tangents[1:])):
        curves.append(f"C{number(from_point[0] + from_tangent[0] * handle)} {number(from_point[1] + from_tangent[1] * handle)} "
                      f"{number(to_point[0] - to_tangent[0] * handle)} {number(to_point[1] - to_tangent[1] * handle)} "
                      f"{number(to_point[0])} {number(to_point[1])}")
    return " ".join(curves)


def rounded_polygon(points: list[tuple[float, float]], radius: float | list[float]) -> str:
    """Closed path through `points` with every corner replaced by a circular arc drawn as one or two cubics
    (two or three nodes). radius is shared by all corners or given per corner; 0 keeps a corner sharp."""
    count = len(points)
    radii = [radius] * count if isinstance(radius, (int, float)) else list(radius)
    segments: list[str] = []
    for index, (corner, corner_radius) in enumerate(zip(points, radii)):
        previous_x, previous_y, previous_length = _direction(corner, points[index - 1])
        next_x, next_y, next_length = _direction(corner, points[(index + 1) % count])
        command = "M" if index == 0 else "L"
        if corner_radius == 0:
            segments.append(f"{command}{number(corner[0])} {number(corner[1])}")
            continue
        half_angle = math.acos(max(-1.0, min(1.0, previous_x * next_x + previous_y * next_y))) / 2
        cut = min(corner_radius / math.tan(half_angle), previous_length / 2, next_length / 2)
        arc_radius = cut * math.tan(half_angle)
        start = (corner[0] + previous_x * cut, corner[1] + previous_y * cut)
        end = (corner[0] + next_x * cut, corner[1] + next_y * cut)
        segments.append(f"{command}{number(start[0])} {number(start[1])} "
                        + _corner_curves(start, end, corner, arc_radius, math.pi - 2 * half_angle))
    return _path(*segments, "Z")


def rectangle(left: float, top: float, right: float, bottom: float, radius: float = 0) -> str:
    return rounded_polygon([(left, top), (right, top), (right, bottom), (left, bottom)], radius)


_STAR_POINTS = 5
_STAR_INNER_RATIO = 0.45     # inner point radius / outer point radius
_STAR_ROUNDING_RATIO = 0.1   # corner radius / outer point radius


def star(outer_radius: float) -> str:
    """Grid-snapped star with _STAR_POINTS outer and as many inner points, all corners rounded."""
    points = []
    for index in range(2 * _STAR_POINTS):
        radius = outer_radius if index % 2 == 0 else outer_radius * _STAR_INNER_RATIO
        angle = math.radians(-90 + index * 180 / _STAR_POINTS)
        x, y = radius * math.cos(angle), radius * math.sin(angle)
        points.append((int(math.copysign(pixel(abs(x)), x)), int(math.copysign(pixel(abs(y)), y))))
    return rounded_polygon(points, pixel(outer_radius * _STAR_ROUNDING_RATIO))


def arrow() -> list[Shape]:
    """Default pointer: rounded triangle, minimal points (two per corner), the top-left corner is the hotspot.
    The left edge is a whole-pixel vertical, every anchor sits on a grid point."""
    start = "M6 7"
    top_left_corner = "C6 5 8 5 9 6"
    upper_edge = "L22 18"
    right_tip = "C23 19 22.4 20.6 21 21"
    concave_lower_edge = "C16 22.4 11.5 24.4 8 26.5"
    bottom_left_corner = "C7 27.1 6 27 6 26"  # tangent to the lower edge; the left edge closes the path
    outline = _path(start, top_left_corner, upper_edge, right_tip, concave_lower_edge, bottom_left_corner, "Z")
    return [path_shape(outline, "ink")]


def path_selection() -> list[Shape]:
    """Path Selection uses the default pointer silhouette."""
    return arrow()


def direct_selection() -> list[Shape]:
    """White pointer for selecting and editing path anchors."""
    return [replace(shape, kind="inverse") for shape in arrow()]


_LENS_RADIUS = 8
_LENS_CENTER = PADDING + PAPER_REACH + _LENS_RADIUS   # the lens touches the top left of the allowed region
_ZOOM_SIGN_ARM = 4
_HANDLE_SIDE = 1.5               # offset of the handle edges from its axis on each grid axis: they run on x - y = +-3
_HALF_DIAGONAL = math.sqrt(0.5)  # cos(45 degrees): the handle runs along the grid diagonal
_HANDLE_RADIUS = _HANDLE_SIDE / _HALF_DIAGONAL
_HANDLE_START = _LENS_CENTER + 6   # the flat end hides under the lens outline
_HANDLE_END = GRID - PADDING - H - _HANDLE_RADIUS   # round end touches the bottom right of the allowed region


def zoom(sign: str) -> list[Shape]:
    center, arm, side = _LENS_CENTER, _ZOOM_SIGN_ARM, _HANDLE_SIDE
    handle = _path(f"M{number(_HANDLE_START - side)} {number(_HANDLE_START + side)}",
                   f"L{number(_HANDLE_START + side)} {number(_HANDLE_START - side)}",
                   f"L{number(_HANDLE_END + side)} {number(_HANDLE_END - side)}",
                   f"A{number(_HANDLE_RADIUS)} {number(_HANDLE_RADIUS)} 0 0 1 "
                   f"{number(_HANDLE_END - side)} {number(_HANDLE_END + side)}",
                   "Z")
    horizontal_bar = f"M{center - arm} {center} H{center + arm}"
    vertical_bar = f"M{center} {center - arm} V{center + arm}"
    bars = _path(horizontal_bar, vertical_bar) if sign == "+" else horizontal_bar
    return [
        _circle(center, center, _LENS_RADIUS, "paper"),
        path_shape(handle, "ink"),
        path_shape(bars, "line", top=True, sharp=True),
    ]


def eyedropper() -> list[Shape]:
    tip, neck, tube_end = "M0 0", "-7", "-17.5"
    tube = _path(tip, f"L-2.7 {neck}", f"L-2.7 {tube_end}", f"L2.7 {tube_end}", f"L2.7 {neck}", "Z")
    cap = rounded_polygon([(-4.5, -21.5), (4.5, -21.5), (4.5, -17), (-4.5, -17)], 1.2)
    bulb = rectangle(-3.5, -_TOOL_LENGTH, 3.5, -19.5, 3.5)
    return [
        path_shape(_path(tube, cap), "paper", transform=_TOOL_TRANSFORM),
        path_shape(bulb, "ink", transform=_TOOL_TRANSFORM),
    ]


# Hands are in 32x32 grid coordinates on whole pixels, fitted to the allowed region with outline and halo.
# The closed hand has the same scale and anchor (two states of one cursor, so it is not enlarged).
# One outline runs from the wrist over thumb and fingers, then down the palm back to the wrist.
# The line between two fingers is part of the outline: it runs down the edge of a finger to the knuckle
# and back up along the next one, so every finger edge is a whole-pixel vertical.
_HAND_START = "M16 28"
_HAND_WRIST = "C14.5 28 13 27.5 12 26"
_HAND_PALM = "C28 21 27 25 24 27 C23.4 27.7 22.8 28 22 28 L16 28"
_HAND_THUMBS = {
    "grab": "C10 24 7 19.5 6 17 C5.4 15.8 6.4 14 8 14 L12 18",
    "grabbing": "C10 24 9 22 8.5 21 C8.2 20 8.4 19.4 8.8 19 C9.5 18 10.5 16.7 12 16 L12 18",
}
_FINGER_WIDTH = 4
_FINGERS_LEFT = 12
_KNUCKLE_Y = 16
# per pose: thumb variant and the top of each fingertip arc (index, middle, ring, little)
_HAND_POSES = {
    "grab": ("grab", (5, 4, 6, 8)),
    "grabbing": ("grabbing", (12, 11, 12, 14)),
    "pointer": ("grab", (5, 11, 12, 14)),
}


def _finger(left: float, tip_top: float) -> str:
    """Up the left edge, over a semicircular tip, down the right edge to the knuckle."""
    radius, right = _FINGER_WIDTH / 2, left + _FINGER_WIDTH
    return (f"L{left} {tip_top + radius} A{radius} {radius} 0 0 1 {right} {tip_top + radius} "
            f"L{right} {_KNUCKLE_Y}")


def _hand(pose: str) -> list[Shape]:
    thumb, tips = _HAND_POSES[pose]
    fingers = [_finger(_FINGERS_LEFT + index * _FINGER_WIDTH, tip_top) for index, tip_top in enumerate(tips)]
    outline = _path(_HAND_START, _HAND_WRIST, _HAND_THUMBS[thumb], *fingers, _HAND_PALM, "Z")
    return [path_shape(outline, "fill")]


_NIB_SLIT = 13.14  # slit length from the tip; the dot sits at its end


def pen_nib() -> list[Shape]:
    tip = "M0 0"
    left_flank = "L-5.4 -11.79"
    left_shoulder = "Q-6 -17.97 -4.2 -20.44"
    top_edge = "L4.2 -20.44"
    right_shoulder = "Q6 -17.97 5.4 -11.79"
    nib = _path(tip, left_flank, left_shoulder, top_edge, right_shoulder, "Z")
    return [
        path_shape(nib, "paper", transform=_TOOL_TRANSFORM),
        path_shape(rectangle(-4.2, -_TOOL_LENGTH, 4.2, -19.32, 1.6), "ink", transform=_TOOL_TRANSFORM),
        path_shape(f"M0 0 V{-_NIB_SLIT}", "line", top=True, transform=_TOOL_TRANSFORM),
        _circle(0, -_NIB_SLIT, 1.65, "ink", top=True, transform=_TOOL_TRANSFORM),
    ]


# Knife: blade (outlined) sits on the handle (solid); the blade tip is the hotspot, the tip is off the handle axis.
_KNIFE_SEAM = -17.92         # where the blade ends and the handle starts
_KNIFE_SPINE = -2.54         # the blunt upper edge; the handle is flush with its outline
_KNIFE_HANDLE_WIDTH = 5.47


def knife() -> list[Shape]:
    seam, side_a = _KNIFE_SEAM, _KNIFE_SPINE - SW
    side_b, end_radius = side_a + _KNIFE_HANDLE_WIDTH, _KNIFE_HANDLE_WIDTH / 2
    blade = _path("M0 0", f"Q-3.17 -5.34 {_KNIFE_SPINE} {seam}", f"L4.31 {seam}", "L3.68 -7.94", "C3.39 -3.48 0 0 0 0", "Z")
    handle = rounded_polygon([(side_a, seam), (side_b, seam), (side_b, -_TOOL_LENGTH), (side_a, -_TOOL_LENGTH)],
                             [0, 0, end_radius, end_radius])
    return [path_shape(blade, "paper", transform=_TOOL_TRANSFORM), path_shape(handle, "ink", transform=_TOOL_TRANSFORM)]


# Magnet: horseshoe and poles sit above the hotspot, matching the other rotated tool cursors.
_MAGNET_ORIGIN = (8, 24)
_MAGNET_OUTER = 9.8
_MAGNET_ARM = 5.93
_MAGNET_BEND_Y = -15.96
_MAGNET_POLE_Y = -4.33       # pole faces
_MAGNET_POLE_LENGTH = 5.47
_MAGNET_POLE_GAP = SW        # visible gap between a pole and the body
_MAGNET_DOT_RADIUS = 2
_MAGNET_TRANSFORM = (*_MAGNET_ORIGIN, _TOOL_TIP_ANGLE)


def magnet() -> list[Shape]:
    outer, inner, bend = _MAGNET_OUTER, _MAGNET_OUTER - _MAGNET_ARM, _MAGNET_BEND_Y
    pole_top = _MAGNET_POLE_Y - _MAGNET_POLE_LENGTH
    body_end = pole_top - _MAGNET_POLE_GAP
    body = _path(f"M{-outer} {body_end} V{bend} A{outer} {outer} 0 0 1 {outer} {bend} V{body_end}",
                 f"H{inner} V{bend} A{inner} {inner} 0 0 0 {-inner} {bend} V{body_end} Z")
    poles = [rectangle(left, pole_top, left + _MAGNET_ARM, _MAGNET_POLE_Y) for left in (-outer, inner)]
    return [
        path_shape(_path(body, *poles), "ink", transform=_MAGNET_TRANSFORM, sharp=True),
        _dot(*_MAGNET_ORIGIN, _MAGNET_DOT_RADIUS),
    ]


def crosshair() -> list[Shape]:
    """Precision crosshair with four separate arms and an open center; the arm ends touch the allowed region."""
    center, gap, near, far = _CANVAS_CENTER, 5, LINE_INSET, LINE_FAR_EDGE
    left_arm = f"M{near} {center} H{center - gap}"
    right_arm = f"M{center + gap} {center} H{far}"
    top_arm = f"M{center} {near} V{center - gap}"
    bottom_arm = f"M{center} {center + gap} V{far}"
    return [
        path_shape(_path(left_arm, right_arm, top_arm, bottom_arm), "line", sharp=True),
        _dot(center, center, _CENTER_DOT_RADIUS),
    ]


def artboard() -> list[Shape]:
    """Artboard cursor with the stepped lower-right frame; the line ends touch the allowed region."""
    near, far = LINE_INSET, LINE_FAR_EDGE
    outline = f"M{near} 16 H11 M21 16 H{far} V{far} M16 {near} V11 M16 21 V{far} H{far}"
    return [
        path_shape(outline, "line", sharp=True),
        _dot(_CANVAS_CENTER, _CANVAS_CENTER, _CENTER_DOT_RADIUS),
    ]


_CROP_RING_RADIUS = 6
_CROP_ARM_OUTER_RADIUS = _CANVAS_CENTER - LINE_INSET   # the arm ends touch the allowed region


def crop() -> list[Shape]:
    """Crop tool target with arms meeting the circular ring."""
    center = _CANVAS_CENTER
    inner, outer = _CROP_RING_RADIUS, _CROP_ARM_OUTER_RADIUS
    arms = _path(
        f"M{center} {center - outer} V{center - inner}",
        f"M{center + inner} {center} H{center + outer}",
        f"M{center} {center + inner} V{center + outer}",
        f"M{center - outer} {center} H{center - inner}",
    )
    return [
        path_shape(arms, "line", sharp=True),
        _circle(center, center, _CROP_RING_RADIUS, "paper"),
        _dot(center, center, _CENTER_DOT_RADIUS),
    ]


# Crop frame: corner brackets in the allowed region; the top left corner is closed into a solid triangle
# (arrow-like) and is the hotspot.
_CROP_FRAME_ARM = 7
_CROP_FRAME_HOTSPOT = (LINE_INSET, LINE_INSET)


def crop_frame() -> list[Shape]:
    """Crop tool: arrow corner at the top left plus three corner brackets of the frame."""
    near, far, arm = LINE_INSET, LINE_FAR_EDGE, _CROP_FRAME_ARM
    triangle = _path(f"M{near} {near}", f"H{near + arm}", f"L{near} {near + arm}", "Z")
    top_right = f"M{far - arm} {near} H{far} V{near + arm}"
    bottom_right = f"M{far} {far - arm} V{far} H{far - arm}"
    bottom_left = f"M{near + arm} {far} H{near} V{far - arm}"
    return [
        path_shape(triangle, "solid"),
        path_shape(_path(top_right, bottom_right, bottom_left), "line", sharp=True),
    ]


# Note tool: a corner bracket marks the hotspot, the sheet with text lines and a folded corner sits inside it.
# The last, half-length text line is level with the top edge of the fold. Every edge and line center sits on
# a whole grid unit, so at 32 px each 2 px line covers exactly two pixel rows or columns.
_NOTE_SHEET = (9, 9, 25, 26)    # left, top, right, bottom
_NOTE_FOLD = 5
_NOTE_TEXT_INSET = 4
_NOTE_TEXT_STEP = 4
_NOTE_BRACKET_INSET = 4    # bracket corner, also the hotspot
_NOTE_BRACKET_END = 27


def note() -> list[Shape]:
    left, top, right, bottom = _NOTE_SHEET
    near, end, fold = _NOTE_BRACKET_INSET, _NOTE_BRACKET_END, _NOTE_FOLD
    bracket = f"M{end} {near} H{near} V{end}"
    sheet = _path(f"M{left} {top}", f"H{right}", f"V{bottom - fold}", f"L{right - fold} {bottom}", f"H{left}", "Z")
    flap = f"M{right - fold} {bottom} V{bottom - fold} H{right}"
    text_start, text_end = left + _NOTE_TEXT_INSET, right - _NOTE_TEXT_INSET
    text_rows = [bottom - fold - _NOTE_TEXT_STEP * step for step in (2, 1, 0)]
    short_end = right - fold - SW - (_NOTE_TEXT_STEP - SW)   # the gap to the fold equals the gap between rows
    text = _path(f"M{text_start} {text_rows[0]} H{text_end}", f"M{text_start} {text_rows[1]} H{text_end}",
                 f"M{text_start} {text_rows[2]} H{short_end}")
    return [
        path_shape(bracket, "line", sharp=True),
        path_shape(sheet, "paper", sharp=True),
        path_shape(_path(flap, text), "line", top=True, sharp=True),
    ]


# Direction cursors: solid arrowheads at the allowed region edge, joined by shafts through the canvas center.
_ARROW_REACH = _CANVAS_CENTER - LINE_INSET   # center to arrow tip
_ARROW_HEAD_LENGTH = 4       # equal to the half width: both head edges run exactly along the pixel diagonal
_ARROW_HEAD_HALF_WIDTH = 4


def _arrow_head(direction_x: int, direction_y: int) -> str:
    """Triangle path with its tip at the allowed region edge, pointing along the direction."""
    tip_x, tip_y = _CANVAS_CENTER + direction_x * _ARROW_REACH, _CANVAS_CENTER + direction_y * _ARROW_REACH
    base_x, base_y = tip_x - direction_x * _ARROW_HEAD_LENGTH, tip_y - direction_y * _ARROW_HEAD_LENGTH
    side_x, side_y = -direction_y * _ARROW_HEAD_HALF_WIDTH, direction_x * _ARROW_HEAD_HALF_WIDTH
    return _path(f"M{tip_x} {tip_y}",
                 f"L{base_x + side_x} {base_y + side_y}",
                 f"L{base_x - side_x} {base_y - side_y}", "Z")


def arrows(horizontal: bool, vertical: bool) -> list[Shape]:
    """Double arrows along the chosen axes: resize for one axis, move for both."""
    shaft_reach = _ARROW_REACH - _ARROW_HEAD_LENGTH
    axes = [axis for axis, enabled in (((1, 0), horizontal), ((0, 1), vertical)) if enabled]
    shafts = [f"M{_CANVAS_CENTER - axis_x * shaft_reach} {_CANVAS_CENTER - axis_y * shaft_reach} "
              f"L{_CANVAS_CENTER + axis_x * shaft_reach} {_CANVAS_CENTER + axis_y * shaft_reach}"
              for axis_x, axis_y in axes]
    heads = [_arrow_head(sign * axis_x, sign * axis_y) for axis_x, axis_y in axes for sign in (-1, 1)]
    return [path_shape(_path(*shafts), "line", sharp=True), path_shape(_path(*heads), "solid")]


_SCISSORS_TILT = 45
_SCISSORS_HOTSPOT = (7, 7)
_SCISSORS_TRANSFORM = (*_SCISSORS_HOTSPOT, -_SCISSORS_TILT)
_SCISSORS_PATH = _path(
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
    "-3.75 20.27 C-3.22 19.36 -3.54 18.19 -4.45 17.66 Z",
)


def scissors() -> list[Shape]:
    """Scissors point down in local coordinates and rotate to their intended angle."""
    return [path_shape(_SCISSORS_PATH, "ink", transform=_SCISSORS_TRANSFORM)]


# Magic wand: a star on top of a straight stick that narrows towards it; the whole cursor rotates together.
_WAND_TILT = 45
_WAND_CENTER = (10, 10)    # hotspot: the star center
_WAND_STAR_RADIUS = 8
_WAND_TIP_WIDTH = 2
_WAND_HANDLE_WIDTH = 4
_WAND_LENGTH = 24
_WAND_STAR_STICK_GAP = 0


def magic_wand() -> list[Shape]:
    """Magic wand: star on a tapered stick."""
    tip_half, handle_half = _WAND_TIP_WIDTH / 2, _WAND_HANDLE_WIDTH / 2
    star_notch = pixel(_WAND_STAR_RADIUS * _STAR_INNER_RATIO)
    stick_start = star_notch + 2 * SW + _WAND_STAR_STICK_GAP - tip_half
    corners = [(-tip_half, stick_start), (tip_half, stick_start),
               (handle_half, _WAND_LENGTH), (-handle_half, _WAND_LENGTH)]
    stick = rounded_polygon(corners, [tip_half, tip_half, handle_half, handle_half])
    return [path_shape(_path(star(_WAND_STAR_RADIUS), stick), "ink", transform=(*_WAND_CENTER, -_WAND_TILT))]


# Fill (paint bucket): the bucket is drawn upright around its own origin and tilted to pour to the left;
# the drop falls below the lower rim end and its lowest point is the hotspot.
_BUCKET_TILT = 35
_BUCKET_CENTER = (18, 18)
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
    transform = (*_BUCKET_CENTER, -_BUCKET_TILT)
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
    drop = _path(f"M{drop_x} {number(drop_top)}",
                 f"C{number(drop_x - _DROP_RADIUS * 0.5)} {number(drop_top + 2.2)} {number(drop_x - _DROP_RADIUS)} "
                 f"{number(drop_center_y - 1.2)} {number(drop_x - _DROP_RADIUS)} {number(drop_center_y)}",
                 f"A{_DROP_RADIUS} {_DROP_RADIUS} 0 0 0 {number(drop_x + _DROP_RADIUS)} {number(drop_center_y)}",
                 f"C{number(drop_x + _DROP_RADIUS)} {number(drop_center_y - 1.2)} "
                 f"{number(drop_x + _DROP_RADIUS * 0.5)} {number(drop_top + 2.2)} {drop_x} {number(drop_top)}",
                 "Z")
    return [
        path_shape(handle, "line", transform=transform),
        path_shape(body, "paper", transform=transform),
        path_shape(drop, "ink"),
    ]


# Extra elements ("badges") are attached next to a base cursor; the base is never shrunk.
# If an element does not fit into the base's 32x32 grid, the canvas of that cursor grows to the right
# and down (the hotspot stays where it was, the origin is the top left corner).
# Every glyph is drawn once around its own origin (0, 0) on whole units and no glyph reaches farther right
# or down than _BADGE_HALF_SIZE, so all badges share one origin in the bottom right corner of the allowed region.
#   "shared" - universal marks (+, -), usable on any cursor;
#   "<base>" - marks of one tool, so a bulky mark never constrains the others.
# add_badged() looks in the base's group first, then in "shared".
_BADGE_HALF_SIZE = 3
BADGE_ORIGIN = GRID - PADDING - LINE_REACH - _BADGE_HALF_SIZE
BADGES: dict[str, dict[str, list[Shape]]] = {
    "shared": {
        "plus": [path_shape("M-3 0 H3 M0 -3 V3", "line", sharp=True)],
        "minus": [path_shape("M-3 0 H3", "line", sharp=True)],
        "ring": [_circle(0, 0, 3, "line")],
    },
    "pen": {
        "wave": [path_shape("M-3 1 Q-1.5 -2 0 1 T3 1", "line")],
        "curve": [path_shape("M-5 3 C-1 3 -1 -3 3 -3", "line")],
        "caret": [path_shape("M-3 3 L0 -1 L3 3", "line")],
    },
}

# Canvas size in grid units, only for cursors that do not fit 32x32 (name -> (width, height)).
CANVAS: dict[str, tuple[float, float]] = {}


# name -> (hotspot on the 32x32 grid, shape factory)
CURSORS: dict[str, tuple[tuple[float, float], Callable[[], list[Shape]]]] = {
    "arrow": ((7, 5), arrow),
    "path_selection": ((7, 5), path_selection),
    "direct_selection": ((7, 5), direct_selection),
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
    "note": ((_NOTE_BRACKET_INSET, _NOTE_BRACKET_INSET), note),
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
    placed = [replace(shape, transform=(BADGE_ORIGIN, BADGE_ORIGIN, 0)) for shape in shapes]
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
    "color_sampler": ("eyedropper", "ring"),
}.items():
    add_badged(name, base, badge)
# other tools reuse the same badges, e.g.: add_badged("select_add", "select", "plus")


def canvas_size(name: str) -> tuple[float, float]:
    return CANVAS.get(name, (GRID, GRID))


def build_svg(name: str, size: int = GRID, theme: str | None = None) -> str:
    """size = pixels per GRID units, so the scale is the same for every canvas. The geometry is fitted to that
    size and written in pixels, so the rasterizer hits whole pixels."""
    hot, factory = CURSORS[name]
    scale = size / GRID
    canvas_width, canvas_height = canvas_size(name)
    width, height = round(canvas_width * scale), round(canvas_height * scale)
    fit = Fit.for_style(scale, SW, H)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" shape-rendering="geometricPrecision">\n'
            f'<!-- hotspot: {number(hot[0])},{number(hot[1])} -->\n{render(factory(), fit, theme=theme)}\n</svg>\n')