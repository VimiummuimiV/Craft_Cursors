"""HTML and PNG preview generation for cursor sets."""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Callable

from config import (
    ACTUAL_SIZE,
    GRID,
    LARGE_PIXELS_PER_UNIT,
    PIXEL_ZOOM,
    SHEET_COLUMNS,
    THEMES,
)
from cursors import (
    build_svg,
    canvas_size,
    image_side,
    CURSORS,
)

_LARGE_PANEL_PADDING = 10

_PREVIEW_STYLES = """<style>
    body {
        font: 14px 'Segoe UI', Arial, sans-serif;
        margin: 0;
        padding: 24px 24px 80px;
        background: #888;
    }

    /* Cards grid — equal columns, equal gaps, no stretch */
    .grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, 260px);
        gap: 16px;
        justify-content: start;
        align-items: start;
    }

    .card {
        background: rgba(255, 255, 255, .18);
        padding: 10px;
        border-radius: 10px;
        box-sizing: border-box;
        color: #111;
        display: flex;
        flex-direction: column;
        gap: 8px;
        width: 100%;
        min-width: 0;
    }

    .row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
    }

    .panel {
        display: grid;
        place-items: center;
        border-radius: 8px;
        overflow: hidden;
        box-sizing: border-box;
        width: 100%;
    }

    .light { background: #ffffff; }
    .dark { background: #000000; }

    .theme {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .theme-label {
        font-size: 11px;
        font-weight: 600;
        letter-spacing: .04em;
        text-transform: uppercase;
        color: #333;
        opacity: .75;
    }

    .stage {
        position: relative;
        max-width: 100%;
    }

    .stage svg {
        display: block;
        max-width: 100%;
        height: auto;
    }

    .actual-label {
        font-size: 12px;
        font-weight: 600;
        line-height: 1.2;
        color: #333;
    }

    .actual-panel {
        min-height: 48px;
        padding: 6px;
    }

    .actual-stage {
        position: relative;
    }

    .actual-stage svg {
        display: block;
        max-width: 100%;
        height: auto;
    }

    .compact-theme {
        gap: 2px;
    }

    .actual-stage img {
        display: block;
        image-rendering: pixelated;
    }

    .hotspot-marker {
        position: absolute;
        width: 8px;
        height: 8px;
        border: 1px solid #fff;
        border-radius: 50%;
        box-sizing: border-box;
        background: #ff3030;
        box-shadow: 0 0 0 1px #111;
        transform: translate(-50%, -50%);
        pointer-events: none;
        z-index: 1;
    }

    .meta {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
    }

    .name {
        font-size: 15px;
        font-weight: 600;
        line-height: 1.2;
        letter-spacing: .01em;
        color: #111;
        overflow-wrap: anywhere;
    }

    .hotspot {
        font-size: 12px;
        line-height: 1.2;
        color: #2c2c2c;
        opacity: .8;
    }

    .toolbar {
        position: fixed;
        bottom: 16px;
        left: 50%;
        transform: translateX(-50%);
        display: flex;
        flex-direction: row;
        flex-wrap: wrap;
        gap: 12px 18px;
        align-items: center;
        padding: 10px 16px;
        background: rgba(255, 255, 255, .94);
        border-radius: 10px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, .18);
        font-size: 13px;
        color: #222;
        z-index: 100;
    }

    .toolbar label {
        display: flex;
        align-items: center;
        gap: 6px;
        cursor: pointer;
        user-select: none;
        white-space: nowrap;
    }

    .toolbar input {
        margin: 0;
    }

    body.hide-large .view-large { display: none !important; }
    body.hide-compact .view-compact { display: none !important; }
    body.hide-pixels .view-pixels { display: none !important; }
    body.hide-dark .theme-dark { display: none !important; }
    body.hide-light .theme-light { display: none !important; }
    body.hide-hotspot .hotspot-marker { display: none !important; }

    .toolbar button {
        font: inherit;
        padding: 4px 12px;
        border: 1px solid #bbb;
        border-radius: 6px;
        background: #f5f5f5;
        cursor: pointer;
        color: #222;
    }

    .toolbar button:hover {
        background: #eaeaea;
    }

    .toolbar button:disabled {
        opacity: .55;
        cursor: wait;
    }
</style>
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
"""

_PREVIEW_TOOLBAR = """
<div class="toolbar">
  <label><input type="checkbox" id="tog-large" checked> Large</label>
  <label><input type="checkbox" id="tog-compact" checked> Actual 1:1</label>
  <label><input type="checkbox" id="tog-pixels" checked> Pixels</label>
  <label><input type="checkbox" id="tog-dark" checked> dark</label>
  <label><input type="checkbox" id="tog-light" checked> light</label>
  <label><input type="checkbox" id="tog-hotspot"> Hotspot</label>
  <button type="button" id="btn-shot" title="Capture visible cards as PNG (multi-page if tall)">Save PNG</button>
</div>
<script>
(function () {
  const KEY = 'cursors-preview-toggles';
  const map = {
    'tog-large': 'hide-large',
    'tog-compact': 'hide-compact',
    'tog-pixels': 'hide-pixels',
    'tog-dark': 'hide-dark',
    'tog-light': 'hide-light',
    'tog-hotspot': 'hide-hotspot',
  };
  function sync() {
    const state = {};
    for (const [id, cls] of Object.entries(map)) {
      const el = document.getElementById(id);
      document.body.classList.toggle(cls, !el.checked);
      state[id] = el.checked;
    }
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (_) {}
  }
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (saved && typeof saved === 'object') {
      for (const id of Object.keys(map)) {
        if (typeof saved[id] === 'boolean') {
          document.getElementById(id).checked = saved[id];
        }
      }
    }
  } catch (_) {}
  for (const id of Object.keys(map)) {
    document.getElementById(id).addEventListener('change', sync);
  }
  sync();

  // Capture visible cards into one or more PNG pages (~A4 landscape height at 2x)
  const PAGE_H = 1600;
  const SCALE = 2;

  function downloadCanvas(canvas, name) {
    const a = document.createElement('a');
    a.download = name;
    a.href = canvas.toDataURL('image/png');
    a.click();
  }

  async function capturePages() {
    const btn = document.getElementById('btn-shot');
    if (typeof html2canvas !== 'function') {
      alert('html2canvas failed to load (network / CDN).');
      return;
    }
    btn.disabled = true;
    const prevText = btn.textContent;
    btn.textContent = '…';
    try {
      const target = document.getElementById('grid');
      const full = await html2canvas(target, {
        backgroundColor: '#888888',
        scale: SCALE,
        logging: false,
      });
      const pageH = Math.min(PAGE_H * SCALE, full.height);
      if (full.height <= pageH) {
        downloadCanvas(full, 'cursors-preview.png');
      } else {
        let page = 1;
        for (let y = 0; y < full.height; y += pageH) {
          const h = Math.min(pageH, full.height - y);
          const slice = document.createElement('canvas');
          slice.width = full.width;
          slice.height = h;
          slice.getContext('2d').drawImage(
            full, 0, y, full.width, h, 0, 0, full.width, h);
          downloadCanvas(slice, 'cursors-preview-' + page + '.png');
          page += 1;
        }
      }
    } catch (err) {
      console.error(err);
      alert('Capture failed: ' + err);
    } finally {
      btn.disabled = false;
      btn.textContent = prevText;
    }
  }

  document.getElementById('btn-shot').addEventListener('click', capturePages);
})();
</script>
"""


def _theme_block(
    theme: str,
    content: str,
    stage_style: str,
    view: str,
    panel_style: str = "",
    hotspot_marker: str = "",
) -> str:
    """One theme row: the cursor (SVG or PNG markup) on a light and a dark panel."""
    compact = view != "large"
    theme_class = "theme compact-theme" if compact else "theme"
    panel_class = "panel actual-panel" if compact else "panel"
    stage_class = "actual-stage" if compact else "stage"
    panels = "".join(
        f'<div class="{panel_class} {background}"{panel_style}>'
        f'<div class="{stage_class}" {stage_style}>{content}{hotspot_marker}</div></div>'
        for background in ("light", "dark"))
    return (f'<div class="{theme_class} theme-{theme} view-{view}">'
            f'<div class="theme-label">{theme}</div>'
            f'<div class="row">{panels}</div></div>')


def _png_markup(png: bytes, side: int, shown: int) -> str:
    encoded = base64.b64encode(png).decode("ascii")
    return f'<img src="data:image/png;base64,{encoded}" width="{shown}" height="{shown}" alt="">'


def _hotspot_markup(hotspot_x: float, hotspot_y: float, width: float, height: float) -> str:
    left = hotspot_x / width * 100
    top = hotspot_y / height * 100
    return f'<span class="hotspot-marker" style="left:{left:g}%;top:{top:g}%"></span>'


def _card(name: str, render_png: Callable[[str, int, str], bytes]) -> str:
    hotspot_x, hotspot_y = CURSORS[name][0]
    canvas_width, canvas_height = canvas_size(name)
    stage_width, stage_height = canvas_width * LARGE_PIXELS_PER_UNIT, canvas_height * LARGE_PIXELS_PER_UNIT
    large_hotspot = _hotspot_markup(hotspot_x, hotspot_y, canvas_width, canvas_height)
    panel_style = (f' style="width:{stage_width + 2 * _LARGE_PANEL_PADDING:g}px;'
                   f'height:{stage_height + 2 * _LARGE_PANEL_PADDING:g}px"')
    large_stage = f'style="width:{stage_width:g}px;height:{stage_height:g}px"'
    large_blocks = [
        _theme_block(theme, build_svg(name, LARGE_PIXELS_PER_UNIT * GRID, theme=theme),
                     large_stage, "large", panel_style=panel_style, hotspot_marker=large_hotspot)
        for theme in THEMES]
    actual_side = round(max(canvas_width, canvas_height) * ACTUAL_SIZE / GRID)
    zoomed_side = actual_side * PIXEL_ZOOM
    compact_hotspot = _hotspot_markup(hotspot_x, hotspot_y, max(canvas_width, canvas_height),
                                      max(canvas_width, canvas_height))
    pixel_blocks = []
    actual_blocks = []
    for theme in THEMES:
        png = render_png(name, ACTUAL_SIZE, theme)
        actual_blocks.append(_theme_block(theme, _png_markup(png, actual_side, actual_side),
                                          f'style="width:{actual_side}px;height:{actual_side}px"', "compact",
                                          hotspot_marker=compact_hotspot))
        pixel_blocks.append(_theme_block(theme, _png_markup(png, actual_side, zoomed_side),
                                         f'style="width:{zoomed_side}px;height:{zoomed_side}px"', "pixels",
                                         hotspot_marker=compact_hotspot))
    return (f'<div class="card">'
            f'{"".join(large_blocks)}'
            f'<div class="meta">'
            f'<div class="name">{name}</div>'
            f'<div class="hotspot">hotspot {hotspot_x:g},{hotspot_y:g}</div>'
            f'</div>'
            f'<div class="actual-label view-compact">Actual ({ACTUAL_SIZE}px, 1:1)</div>'
            f'{"".join(actual_blocks)}'
            f'<div class="actual-label view-pixels">Pixels ×{PIXEL_ZOOM}</div>'
            f'{"".join(pixel_blocks)}'
            f'</div>')


def preview_html(render_png: Callable[[str, int, str], bytes], names: list[str]) -> str:
    """render_png(name, size, theme) returns the PNG bytes of one cursor at a fitted size."""
    cards = "".join(_card(name, render_png) for name in names)
    return ("<!doctype html><meta charset=utf-8><title>Cursors</title>"
            + _PREVIEW_STYLES
            + f'<div id="grid" class="grid">{cards}</div>'
            + _PREVIEW_TOOLBAR)


def contact_sheet(
    path: Path,
    render_image: Callable,
    names: list[str],
    theme: str,
    pixels_per_unit: int,
) -> None:
    """Render a quick-check sheet on pure white and black backgrounds."""
    from PyQt6.QtGui import QColor, QImage, QPainter
    columns = SHEET_COLUMNS
    panel = max(image_side(name, pixels_per_unit) for name in names) + 16
    cell_width, row_height = 2 * panel + 20, panel + 20
    rows = (len(names) + columns - 1) // columns
    sheet = QImage(columns * cell_width, rows * row_height, QImage.Format.Format_ARGB32)
    sheet.fill(QColor("#808080"))
    painter = QPainter(sheet)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    for index, name in enumerate(names):
        left, top = (index % columns) * cell_width + 10, (index // columns) * row_height + 8
        painter.fillRect(left, top, panel, panel, QColor("#ffffff"))
        painter.fillRect(left + panel, top, panel, panel, QColor("#000000"))
        cursor_image = render_image(name, pixels_per_unit, theme=theme)
        for x in (left + 8, left + panel + 8):
            painter.drawImage(x, top + 8, cursor_image)
    painter.end()
    sheet.save(str(path))