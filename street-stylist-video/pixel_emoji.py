"""Chunky 3D pixel-art emoji stickers (16x16 voxel faces) for the Street Stylist video."""
import math
import numpy as np
import cairo
from scipy.ndimage import gaussian_filter

def hexc(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

PAL = {'Y': hexc('FFC83D'), 'y': hexc('F0A81E'), 'K': hexc('3B2314'), 'W': hexc('FFFFFF'),
       'R': hexc('FF3B5C'), 'P': hexc('FF8FA3'), 'M': hexc('8A1E2E'), 'G': hexc('2FD27A'),
       'g': hexc('1A9E55'), 'B': hexc('7FD3FF'), 'S': hexc('C8CCD4')}

FACE = ["......YYYY......",
        "....YYYYYYYY....",
        "...YYYYYYYYYY...",
        "..YYYYYYYYYYYY..",
        ".YYYYYYYYYYYYYY.",
        ".YYYYYYYYYYYYYY.",
        "YYYYYYYYYYYYYYYY",
        "YYYYYYYYYYYYYYYY",
        "YYYYYYYYYYYYYYYY",
        "YYYYYYYYYYYYYYYY",
        ".YYYYYYYYYYYYYYy",
        ".YYYYYYYYYYYYYy.",
        "..YYYYYYYYYYYyy.",
        "...YYYYYYYYYyy..",
        "....yyyyyyyyy...",
        "......yyyy......"]


def face(marks):
    g = [list(r) for r in FACE]
    for ch, pts in marks.items():
        for (r, c) in pts:
            g[r][c] = ch
    return g


def rect(r0, r1, c0, c1): return [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]


DOT_EYES = rect(5, 6, 4, 5) + rect(5, 6, 10, 11)
HEART_L = [(4, 2), (4, 3), (4, 5), (4, 6), (5, 2), (5, 3), (5, 4), (5, 5), (5, 6), (6, 3), (6, 4), (6, 5), (7, 4)]
HEART_R = [(r, c + 7) for r, c in HEART_L]
DOLLAR_L = [(3, 4), (4, 3), (4, 4), (4, 5), (5, 3), (6, 3), (6, 4), (6, 5), (7, 5), (8, 3), (8, 4), (8, 5), (9, 4)]
DOLLAR_R = [(r, c + 7) for r, c in DOLLAR_L]

DESIGNS = {
    '😕': face({'K': DOT_EYES + [(11, 5), (11, 6), (10, 7), (10, 8), (10, 9), (9, 10), (9, 11)]}),
    '😐': face({'K': DOT_EYES + rect(10, 10, 5, 10)}),
    '😮': face({'K': DOT_EYES + [(9, 7), (9, 8), (10, 6), (11, 6), (12, 7), (12, 8), (10, 9), (11, 9)],
                'M': [(10, 7), (10, 8), (11, 7), (11, 8)]}),
    '😳': face({'W': rect(4, 7, 3, 6) + rect(4, 7, 9, 12), 'K': rect(5, 6, 4, 5) + rect(5, 6, 10, 11) + [(11, 7), (11, 8)],
                'P': [(9, 2), (9, 3), (9, 12), (9, 13)]}),
    '😍': face({'R': HEART_L + HEART_R, 'K': rect(9, 9, 3, 12) + [(10, 3), (10, 12), (11, 4), (11, 11), (12, 5), (12, 6), (12, 7), (12, 8), (12, 9), (12, 10)],
                'M': rect(10, 10, 4, 11) + rect(11, 11, 5, 10), 'W': rect(10, 10, 5, 10)}),
    '😩': face({'K': [(4, 3), (4, 4), (4, 11), (4, 12), (6, 3), (6, 4), (6, 5), (7, 5), (6, 10), (6, 11), (6, 12), (7, 10),
                      (9, 6), (9, 7), (9, 8), (9, 9), (10, 5), (11, 5), (12, 5), (10, 10), (11, 10), (12, 10), (13, 6), (13, 7), (13, 8), (13, 9)],
                'M': rect(10, 12, 6, 9)}),
    '🤑': face({'G': DOLLAR_L + DOLLAR_R, 'K': rect(10, 10, 3, 12) + [(11, 3), (11, 12), (12, 4), (12, 11)],
                'g': rect(11, 13, 6, 9), 'W': [(11, 4), (11, 5), (11, 10), (11, 11)]}),
}
DESIGNS['💅'] = [list(r) for r in [
    "................",
    "...RR.RR.RR.....",
    "...YY.YY.YY.RR..",
    "...YY.YY.YY.YY..",
    "...YY.YY.YY.YY..",
    "...YYYYYYYYYYY..",
    "R..YYYYYYYYYYY..",
    "YY.YYYYYYYYYYY..",
    "YYYYYYYYYYYYYY..",
    ".YYYYYYYYYYYYy..",
    "..YYYYYYYYYYyy..",
    "...YYYYYYYYyy...",
    "....yyyyyyyy....",
    "....SSSSSSSS....",
    "....SSSSSSSS....",
    "................"]]


def shade(c, k): return tuple(max(0.0, min(1.0, v * k)) for v in c)


def render_voxel(grid, cell, depth=0.55, glow=True):
    """Return a cairo ImageSurface with an extruded, softly lit pixel sprite plus a soft glow."""
    n = len(grid)
    pad = int(cell * 2.5)
    W = H = int(n * cell + 2 * pad)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    cells = [(r, c, grid[r][c]) for r in range(n) for c in range(n) if grid[r][c] in PAL]
    ox, oy = pad, pad
    d = depth * cell
    steps = max(2, int(d))
    # extrusion (side walls), drawn back to front
    for s in range(steps, 0, -1):
        off = d * s / steps
        for r, c, ch in cells:
            ctx.rectangle(ox + c * cell + off * 0.35, oy + r * cell + off, cell + 0.6, cell + 0.6)
            ctx.set_source_rgb(*shade(PAL[ch], 0.48)); ctx.fill()
    # front faces with a tiny bevel
    for r, c, ch in cells:
        x, y = ox + c * cell, oy + r * cell
        ctx.rectangle(x, y, cell + 0.6, cell + 0.6); ctx.set_source_rgb(*PAL[ch]); ctx.fill()
        filled = lambda rr, cc: 0 <= rr < n and 0 <= cc < n and grid[rr][cc] in PAL
        if not filled(r - 1, c):
            ctx.rectangle(x, y, cell + 0.6, cell * 0.2); ctx.set_source_rgba(1, 1, 1, 0.30); ctx.fill()
        if not filled(r, c - 1):
            ctx.rectangle(x, y, cell * 0.2, cell + 0.6); ctx.set_source_rgba(1, 1, 1, 0.18); ctx.fill()
    # glossy key light from the top-left
    g = cairo.LinearGradient(ox, oy, ox + n * cell * 0.7, oy + n * cell * 0.7)
    g.add_color_stop_rgba(0, 1, 1, 1, 0.28); g.add_color_stop_rgba(0.5, 1, 1, 1, 0.0)
    ctx.set_operator(cairo.OPERATOR_ATOP); ctx.set_source(g); ctx.paint(); ctx.set_operator(cairo.OPERATOR_OVER)
    surf.flush()
    if glow:
        buf = np.ndarray((H, surf.get_stride() // 4, 4), np.uint8, surf.get_data())[:, :W].astype(np.float32) / 255
        a = buf[..., 3]
        gl = gaussian_filter(a, cell * 1.1) * 0.55
        col = np.array([0.45, 0.80, 1.0])          # BGR: warm glow
        out = buf.copy()
        ga = gl * (1 - a)
        out[..., :3] = buf[..., :3] + col * ga[..., None]
        out[..., 3] = a + ga
        arr = np.ndarray((H, surf.get_stride() // 4, 4), np.uint8, surf.get_data())
        arr[:, :W] = np.clip(out * 255, 0, 255).astype(np.uint8)
        surf.mark_dirty()
    return surf, W, H


def build_all(cell=9):
    return {k: render_voxel(v, cell) for k, v in DESIGNS.items()}


def voxel_chip(ctx, x, y, s, col, metal=False):
    """One chunky voxel block (colour swatch) with its top-left corner at x,y."""
    d = s * 0.28
    steps = 6
    for k in range(steps, 0, -1):
        off = d * k / steps
        ctx.rectangle(x + off * 0.35, y + off, s, s); ctx.set_source_rgb(*shade(col, 0.45)); ctx.fill()
    if metal:
        g = cairo.LinearGradient(x, y, x + s, y + s)
        g.add_color_stop_rgb(0, 0.95, 0.96, 0.98); g.add_color_stop_rgb(0.45, *col)
        g.add_color_stop_rgb(0.7, 0.62, 0.65, 0.70); g.add_color_stop_rgb(1, 0.88, 0.90, 0.93)
        ctx.rectangle(x, y, s, s); ctx.set_source(g); ctx.fill()
    else:
        ctx.rectangle(x, y, s, s); ctx.set_source_rgb(*col); ctx.fill()
    ctx.rectangle(x, y, s, s * 0.14); ctx.set_source_rgba(1, 1, 1, 0.22); ctx.fill()
    ctx.rectangle(x, y + s * 0.86, s, s * 0.14); ctx.set_source_rgba(0, 0, 0, 0.16); ctx.fill()
