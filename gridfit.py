"""Pixel grid fitting: places cursor geometry on whole pixels of one render size, so axis-aligned
edges get full coverage (no gray fringe) at that size."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

_PATH_TOKEN = re.compile(r"[A-Za-z]|-?\d*\.?\d+")
_ARGUMENT_COUNTS = {"M": 2, "L": 2, "T": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "A": 7, "Z": 0}
_HALF_PIXEL = 0.5


def pixel(value: float) -> int:
    """Rounds half up; round() goes to even, so 4.5 and 5.5 would land on different sides."""
    return math.floor(value + _HALF_PIXEL)


def number(value: float) -> str:
    return f"{round(value, 3) + 0.0:g}"


@dataclass(frozen=True)
class Fit:
    """Style of one render size: pixels per grid unit and whole-pixel outline and halo widths."""
    scale: float
    stroke: int
    halo: int

    @classmethod
    def for_style(cls, scale: float, stroke: float, halo: float) -> Fit:
        """Stroke rounds half up and halo half down, so a .5 split never thickens both."""
        return cls(scale, max(1, pixel(stroke * scale)), max(1, math.ceil(halo * scale - _HALF_PIXEL)))

    def snap(self, value: float, on_center: bool) -> float:
        """Grid units -> pixels, on a pixel edge or (on_center) on a pixel center."""
        pixels = value * self.scale
        return math.floor(pixels) + _HALF_PIXEL if on_center else pixel(pixels)

    def circle(self, circle: tuple[float, float, float], origin: tuple[float, float], snap: bool,
               outline_reach: float) -> tuple[float, float, float]:
        """Center and radius in pixels. An odd outer diameter needs the center on a pixel center."""
        center_x, center_y, radius = circle
        radius_pixels = radius * self.scale
        if not snap:
            return center_x * self.scale, center_y * self.scale, radius_pixels
        odd_diameter = pixel(2 * (radius_pixels + outline_reach)) % 2 == 1
        return (self.snap(center_x + origin[0], odd_diameter), self.snap(center_y + origin[1], odd_diameter),
                radius_pixels)

    def path(self, data: str, on_center: bool = False, origin: tuple[float, float] = (0.0, 0.0),
             snap: bool = True) -> str:
        """Absolute path data in grid units -> path data in pixels. With snap every endpoint lands on the
        pixel grid and its control points move with it, so curves keep their shape."""
        scale = self.scale
        tokens = _PATH_TOKEN.findall(data)
        parts: list[str] = []
        current = (0.0, 0.0)   # previous endpoint in pixels
        shift = (0.0, 0.0)     # how far snapping moved it
        command, index = "", 0

        def raw(x: float, y: float) -> tuple[float, float]:
            return (x + origin[0]) * scale, (y + origin[1]) * scale

        def endpoint(x: float, y: float) -> tuple[tuple[float, float], tuple[float, float]]:
            unsnapped = raw(x, y)
            if not snap:
                return unsnapped, (0.0, 0.0)
            placed = (self.snap(x + origin[0], on_center), self.snap(y + origin[1], on_center))
            return placed, (placed[0] - unsnapped[0], placed[1] - unsnapped[1])

        def control(x: float, y: float, moved_by: tuple[float, float]) -> str:
            unsnapped = raw(x, y)
            return f"{number(unsnapped[0] + moved_by[0])} {number(unsnapped[1] + moved_by[1])}"

        while index < len(tokens):
            if tokens[index].isalpha():
                command = tokens[index]
                index += 1
                if command not in _ARGUMENT_COUNTS:
                    raise ValueError(f"unsupported path command {command!r}: only absolute commands are fitted")
                if command == "Z":
                    parts.append("Z")
                    continue
            count = _ARGUMENT_COUNTS[command]
            values = [float(token) for token in tokens[index:index + count]]
            index += count
            if command == "H":
                (placed_x, _), (shift_x, _) = endpoint(values[0], 0)
                current, shift = (placed_x, current[1]), (shift_x, shift[1])
                parts.append(f"H{number(placed_x)}")
            elif command == "V":
                (_, placed_y), (_, shift_y) = endpoint(0, values[0])
                current, shift = (current[0], placed_y), (shift[0], shift_y)
                parts.append(f"V{number(placed_y)}")
            else:
                end_values = values[-2:]
                end, end_shift = endpoint(*end_values)
                if command == "C":
                    leading = f"{control(*values[0:2], shift)} {control(*values[2:4], end_shift)} "
                elif command in "SQ":
                    moved_by = end_shift if command == "S" else ((shift[0] + end_shift[0]) / 2,
                                                                 (shift[1] + end_shift[1]) / 2)
                    leading = f"{control(*values[0:2], moved_by)} "
                elif command == "A":
                    leading = (f"{number(values[0] * scale)} {number(values[1] * scale)} {number(values[2])} "
                               f"{int(values[3])} {int(values[4])} ")
                else:
                    leading = ""
                parts.append(f"{command}{leading}{number(end[0])} {number(end[1])}")
                current, shift = end, end_shift
        return " ".join(parts)