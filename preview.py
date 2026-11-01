"""HTML and PNG preview generation for cursor sets."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Mapping


def preview_html(
    cursors: Mapping[str, tuple[tuple[int, int], Callable]],
    canvas_size: Callable[[str], tuple[float, float]],
    build_svg: Callable[..., str],
    grid: int,
    theme: str,
) -> str:
    cards = []
    actual_preview_size = 24
    large_px_per_unit = 2.0
    for name in cursors:
        hx, hy = cursors[name][0]
        cw, ch = canvas_size(name)
        scale = large_px_per_unit
        sw, sh = cw * scale, ch * scale
        pad = 10
        pw, ph = sw + 2 * pad, sh + 2 * pad
        stage = f'style="width:{sw:g}px;height:{sh:g}px"'
        panel = f'style="width:{pw:g}px;height:{ph:g}px"'
        c_scale = actual_preview_size / grid
        csw, csh = cw * c_scale, ch * c_scale
        c_stage = f'style="width:{csw:g}px;height:{csh:g}px"'
        large_blocks = []
        compact_blocks = []
        for th, label in (("dark", "dark"), ("light", "light")):
            svg = build_svg(name, round(scale * grid), theme=th)
            c_svg = build_svg(name, actual_preview_size, theme=th)
            large_blocks.append(
                f'<div class="theme theme-{th} view-large">'
                f'<div class="theme-label">{label}</div>'
                f'<div class="row">'
                f'<div class="panel light" {panel}><div class="stage" {stage}>{svg}</div></div>'
                f'<div class="panel dark" {panel}><div class="stage" {stage}>{svg}</div></div>'
                f'</div></div>')
            compact_blocks.append(
                f'<div class="theme compact-theme theme-{th} view-compact">'
                f'<div class="theme-label">{label}</div>'
                f'<div class="row actual-row">'
                f'<div class="panel actual-panel light">'
                f'<div class="actual-stage" {c_stage}>{c_svg}</div></div>'
                f'<div class="panel actual-panel dark">'
                f'<div class="actual-stage" {c_stage}>{c_svg}</div></div>'
                f'</div></div>')
        cards.append(
            f'<div class="card">'
            f'{"".join(large_blocks)}'
            f'<div class="meta">'
            f'<div class="name">{name}</div>'
            f'<div class="hotspot">hotspot {hx},{hy} · export: {theme}</div>'
            f'</div>'
            f'<div class="actual-label view-compact">Compact ({actual_preview_size}px)</div>'
            f'{"".join(compact_blocks)}'
            f'</div>')

    col_w = 260
    styles = f"""<style>
	body {{
		font: 14px 'Segoe UI', Arial, sans-serif;
		margin: 0;
		padding: 24px 24px 80px;
		background: #888;
	}}

	/* Cards grid — equal columns, equal gaps, no stretch */
	.grid {{
		display: grid;
		grid-template-columns: repeat(auto-fill, {col_w}px);
		gap: 16px;
		justify-content: start;
		align-items: start;
	}}

	.card {{
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
	}}

	.row {{
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 8px;
	}}

	.panel {{
		display: grid;
		place-items: center;
		border-radius: 8px;
		overflow: hidden;
		box-sizing: border-box;
		width: 100%;
	}}

	.light {{ background: #ffffff; }}
	.dark {{ background: #000000; }}

	.theme {{
		display: flex;
		flex-direction: column;
		gap: 4px;
	}}

	.theme-label {{
		font-size: 11px;
		font-weight: 600;
		letter-spacing: .04em;
		text-transform: uppercase;
		color: #333;
		opacity: .75;
	}}

	.stage {{
		position: relative;
		max-width: 100%;
	}}

	.stage svg {{
		display: block;
		max-width: 100%;
		height: auto;
	}}

	.actual-label {{
		font-size: 12px;
		font-weight: 600;
		line-height: 1.2;
		color: #333;
	}}

	.actual-panel {{
		min-height: 48px;
		padding: 6px;
	}}

	.actual-stage {{
		position: relative;
	}}

	.actual-stage svg,
	.actual-stage img {{
		display: block;
		max-width: 100%;
		height: auto;
	}}

	.compact-theme {{
		gap: 2px;
	}}

	.meta {{
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}}

	.name {{
		font-size: 15px;
		font-weight: 600;
		line-height: 1.2;
		letter-spacing: .01em;
		color: #111;
		overflow-wrap: anywhere;
	}}

	.hotspot {{
		font-size: 12px;
		line-height: 1.2;
		color: #2c2c2c;
		opacity: .8;
	}}

	.toolbar {{
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
	}}

	.toolbar label {{
		display: flex;
		align-items: center;
		gap: 6px;
		cursor: pointer;
		user-select: none;
		white-space: nowrap;
	}}

	.toolbar input {{
		margin: 0;
	}}

	body.hide-large .view-large {{ display: none !important; }}
	body.hide-compact .view-compact {{ display: none !important; }}
	body.hide-dark .theme-dark {{ display: none !important; }}
	body.hide-light .theme-light {{ display: none !important; }}

	.toolbar button {{
		font: inherit;
		padding: 4px 12px;
		border: 1px solid #bbb;
		border-radius: 6px;
		background: #f5f5f5;
		cursor: pointer;
		color: #222;
	}}

	.toolbar button:hover {{
		background: #eaeaea;
	}}

	.toolbar button:disabled {{
		opacity: .55;
		cursor: wait;
	}}
</style>
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
"""
    toolbar = """
<div class="toolbar">
  <label><input type="checkbox" id="tog-large" checked> Large</label>
  <label><input type="checkbox" id="tog-compact" checked> Compact</label>
  <label><input type="checkbox" id="tog-dark" checked> dark</label>
  <label><input type="checkbox" id="tog-light" checked> light</label>
  <button type="button" id="btn-shot" title="Capture visible cards as PNG (multi-page if tall)">Save PNG</button>
</div>
<script>
(function () {
  const KEY = 'cursors-preview-toggles';
  const map = {
    'tog-large': 'hide-large',
    'tog-compact': 'hide-compact',
    'tog-dark': 'hide-dark',
    'tog-light': 'hide-light',
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
    return ("<!doctype html><meta charset=utf-8><title>Cursors</title>"
            + styles
            + '<div id="grid" class="grid">' + "".join(cards) + '</div>'
            + toolbar)


def contact_sheet(path: Path, cursor_names, image_side: Callable, render_image: Callable, qt_loader: Callable) -> None:
    """Render a quick-check sheet on pure white and black backgrounds."""
    _, _, _, Qt, QImage, QPainter, _ = qt_loader()
    from PyQt6.QtGui import QColor
    names = list(cursor_names)
    cols, px = 4, 96
    max_side = max(image_side(name, px) for name in names)
    panel = max_side + 16
    cell, row_h = 2 * panel + 20, panel + 20
    rows = (len(names) + cols - 1) // cols
    img = QImage(cols * cell, rows * row_h, QImage.Format.Format_ARGB32)
    img.fill(QColor("#808080"))
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    for i, name in enumerate(names):
        x0, y0 = (i % cols) * cell + 10, (i // cols) * row_h + 8
        painter.fillRect(x0, y0, panel, panel, QColor("#ffffff"))
        painter.fillRect(x0 + panel, y0, panel, panel, QColor("#000000"))
        cursor_image = render_image(name, px)
        for x in (x0 + 8, x0 + panel + 8):
            painter.drawImage(x, y0 + 8, cursor_image)
    painter.end()
    img.save(str(path))
