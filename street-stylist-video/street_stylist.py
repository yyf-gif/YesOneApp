#!/usr/bin/env python3
"""THE STREET STYLIST - 9:16, 12 s, no dialogue.
Premium monochrome look: black world, glowing white stick figures (rig.py style), glossy floor reflections,
bloom, grain. The only colour on screen is clothing, its 3-colour palette, and pixel-art emoji.

  python3 street_stylist.py                      -> street_stylist.mp4
  python3 street_stylist.py --preview 2.4,10.6   -> preview PNGs
"""
import os, sys, math, argparse, subprocess, wave
import numpy as np
import cairo
from scipy.ndimage import gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rig import Figure, BLACK                      # noqa: E402
from fx import ease_out_back, rrect, sparkle       # noqa: E402
import pixel_emoji as PX                           # noqa: E402
import garments as GM                              # noqa: E402

W, HT = 1080, 1920
FPS = 30
DUR = 12.0
BEAT = 60 / 90                                     # 90 bpm, chill
FONT = "Silkscreen"


def hexc(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


# clothing palette = the only colour in the film
BROWN, WHITE, BABY = hexc('5B3A24'), hexc('F4F2EC'), hexc('A9D3F2')
OLIVE, CREAM, BURG = hexc('6E7348'), hexc('EEE0C2'), hexc('7A1E34')
CHAR, PINK, SILVER = hexc('45474D'), hexc('F4B8CA'), hexc('C6CAD1')
TOPBLK = hexc('202024')
SKIN_HERO, SKIN_W = (1, 1, 1), hexc('A9A9AE')
ST_TOP, ST_SKIRT, ST_SHOE = hexc('F2F2F4'), hexc('E9E9EC'), hexc('1E1E22')
ANKLE = 0.14
SHOE_STYLE = {BROWN: 'loafer', BABY: 'sneaker', WHITE: 'sneaker', BURG: 'heel', TOPBLK: 'loafer', SILVER: 'metal'}
for _c, _k, _s in ((BROWN, 'suede', 0.8), (WHITE, 'twill', 0.65), (BABY, 'leather', 0.35), (OLIVE, 'canvas', 0.85),
                   (CREAM, 'linen', 0.8), (BURG, 'wool', 0.7), (CHAR, 'wool', 0.8), (PINK, 'knit', 0.85),
                   (TOPBLK, 'jersey', 0.7), (ST_TOP, 'jersey', 0.35), (ST_SKIRT, 'twill', 0.4)):
    GM.set_fabric(_c, _k, _s)


def clamp(x, a=0.0, b=1.0): return a if x < a else b if x > b else x
def sstep(u): u = clamp(u); return u * u * (3 - 2 * u)
def lerp(a, b, u): return a + (b - a) * u
def lerpt(a, b, u): return tuple(lerp(x, y, u) for x, y in zip(a, b))
def farc(c): return (c[0] * 0.78, c[1] * 0.78, c[2] * 0.80)
def depthH(G): return 100 + (G - 1150) * 0.025  # high camera: gentle size change with depth
def popin(dt, dur=0.3): return 0.0 if dt <= 0 else ease_out_back(min(dt / dur, 1.0), 1.6)
def ease_io(u): u = clamp(u); return 0.5 - 0.5 * math.cos(math.pi * u)


# ======================================================================== drawing primitives (rig style)
def stroke_part(ctx, pts, color, w, ow, sh, metal=False):
    ctx.set_line_cap(cairo.LINE_CAP_ROUND); ctx.set_line_join(cairo.LINE_JOIN_ROUND)

    def path():
        ctx.new_path(); ctx.move_to(*pts[0])
        for q in pts[1:]: ctx.line_to(*q)
    ctx.save(); ctx.translate(*sh); path(); ctx.set_source_rgb(*BLACK); ctx.set_line_width(w + 2 * ow); ctx.stroke(); ctx.restore()
    path(); ctx.set_source_rgb(*BLACK); ctx.set_line_width(w + 2 * ow); ctx.stroke()
    path(); ctx.set_source_rgb(*color); ctx.set_line_width(w); ctx.stroke()
    if metal:
        a, b = np.array(pts[0], float), np.array(pts[-1], float); d = b - a; L = np.linalg.norm(d)
        if L > 1e-3:
            n = np.array([d[1], -d[0]]) / L
            if n[1] > 0: n = -n
            ctx.new_path(); ctx.move_to(*(a + d * 0.1 + n * w * 0.2)); ctx.line_to(*(a + d * 0.75 + n * w * 0.2))
            ctx.set_source_rgb(1, 1, 1); ctx.set_line_width(w * 0.2); ctx.stroke()


def fill_sticker(ctx, build, color, ow, sh, shadow=True):
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    if shadow:
        ctx.save(); ctx.translate(*sh); build(); ctx.set_source_rgb(*BLACK); ctx.fill_preserve()
        ctx.set_line_width(2 * ow); ctx.stroke(); ctx.restore()
    build(); ctx.set_source_rgb(*BLACK); ctx.set_line_width(2 * ow); ctx.stroke_preserve()
    ctx.set_source_rgb(*color); ctx.fill()


def circle_sticker(ctx, c, r, color, ow, sh):
    def b(): ctx.new_path(); ctx.arc(c[0], c[1], r, 0, 2 * math.pi)
    fill_sticker(ctx, b, color, ow, sh)


def draw_bag(ctx, col, H, ow, metal=False):
    bw, bh = 0.84 * H, 0.62 * H
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.new_path(); ctx.arc(0, 0.30 * H, 0.25 * H, math.pi, 2 * math.pi)
    ctx.set_source_rgb(*BLACK); ctx.set_line_width(0.10 * H + 2 * ow); ctx.stroke_preserve()
    ctx.set_source_rgb(*col); ctx.set_line_width(0.10 * H); ctx.stroke()
    fill_sticker(ctx, lambda: rrect(ctx, -bw / 2, 0.28 * H, bw, bh, 0.14 * H), col, ow, (0.05 * H, 0.05 * H))
    ctx.new_path(); ctx.move_to(-bw / 2 + 0.06 * H, 0.47 * H); ctx.line_to(bw / 2 - 0.06 * H, 0.47 * H)
    ctx.set_source_rgb(*BLACK); ctx.set_line_width(ow); ctx.stroke()
    if metal:
        ctx.new_path(); ctx.move_to(-bw / 2 + 0.15 * H, 0.58 * H); ctx.line_to(-bw / 2 + 0.15 * H, 0.78 * H)
        ctx.set_source_rgb(1, 1, 1); ctx.set_line_width(0.08 * H); ctx.stroke()


def draw_beret(ctx, col, H, ow, tilt=0.0):
    def b():
        ctx.new_path(); ctx.save(); ctx.rotate(tilt); ctx.scale(1, 0.55)
        ctx.arc(0, 0, 0.64 * H, math.pi, 2 * math.pi); ctx.close_path(); ctx.restore()
    fill_sticker(ctx, b, col, ow, (0.05 * H, 0.05 * H))
    ctx.save(); ctx.rotate(tilt); circle_sticker(ctx, (0, -0.38 * H), 0.09 * H, col, ow, (0.03 * H, 0.03 * H)); ctx.restore()


def draw_item(ctx, kind, col, H):
    ow = 0.12 * 0.48 * H; sh = (0.05 * H, 0.05 * H)
    if kind == 'shoes':
        for dx, dy in ((-0.20 * H, -0.12 * H), (0.16 * H, 0.14 * H)):
            stroke_part(ctx, [(dx - 0.24 * H, dy), (dx + 0.24 * H, dy)], col, 0.40 * H, ow, sh, col == SILVER)
    elif kind == 'bag':
        ctx.translate(0, -0.55 * H); draw_bag(ctx, col, H, ow, col == SILVER)
    elif kind == 'beret':
        draw_beret(ctx, col, H, ow)
    elif kind == 'jacket':
        w = 0.36 * H
        stroke_part(ctx, [(-0.32 * H, -0.42 * H), (-0.72 * H, 0.30 * H)], col, w, ow, sh)
        stroke_part(ctx, [(0.32 * H, -0.42 * H), (0.72 * H, 0.30 * H)], col, w, ow, sh)
        fill_sticker(ctx, lambda: rrect(ctx, -0.40 * H, -0.55 * H, 0.80 * H, 1.15 * H, 0.18 * H), col, ow, sh)
        ctx.new_path(); ctx.move_to(-0.16 * H, -0.55 * H); ctx.line_to(0, -0.22 * H); ctx.line_to(0.16 * H, -0.55 * H)
        ctx.move_to(0, -0.22 * H); ctx.line_to(0, 0.58 * H)
        ctx.set_source_rgb(*BLACK); ctx.set_line_width(ow); ctx.stroke()


def grain_surface(kind, strength):
    """fabric grain as dark/light specks (premultiplied), painted ATOP a flat fill: matte cloth, no gloss"""
    src = GM.tex(kind); n = src.get_width()
    v = np.ndarray((n, src.get_stride() // 4, 4), np.uint8, src.get_data())[:, :n, 0].astype(np.float32) / 255
    d = (v - 0.5) * 2
    a = np.abs(d) * strength
    lum_ = np.where(d > 0, 1.0, 0.0) * a
    s_ = cairo.ImageSurface(cairo.FORMAT_ARGB32, n, n)
    b = np.ndarray((n, s_.get_stride() // 4, 4), np.uint8, s_.get_data())
    b[:, :n, 0] = b[:, :n, 1] = b[:, :n, 2] = (lum_ * 255).astype(np.uint8); b[:, :n, 3] = (a * 255).astype(np.uint8)
    s_.mark_dirty(); return s_


_GRAIN = {}


def grain(col):
    kind, strength, _ = GM.fabric_of(col)
    key = (kind, round(strength, 2))
    if key not in _GRAIN: _GRAIN[key] = grain_surface(kind, 0.20 * strength + 0.05)
    return _GRAIN[key]


def poly(ctx, pts):
    ctx.new_path(); ctx.move_to(*pts[0])
    for q in pts[1:]: ctx.line_to(*q)


def piece(ctx, strokes, col, ow, sh, H, fabric=True, details=None):
    """one garment/body piece in the rig style: offset black shadow, black outline, FLAT fill (+ cloth grain, flat details)
    strokes: list of (points, width)"""
    ctx.set_line_cap(cairo.LINE_CAP_ROUND); ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.save(); ctx.translate(*sh)
    for pts, ww in strokes:
        poly(ctx, pts); ctx.set_source_rgb(*BLACK); ctx.set_line_width(ww + 2 * ow); ctx.stroke()
    ctx.restore()
    for pts, ww in strokes:
        poly(ctx, pts); ctx.set_source_rgb(*BLACK); ctx.set_line_width(ww + 2 * ow); ctx.stroke()
    ctx.push_group()
    for pts, ww in strokes:
        poly(ctx, pts); ctx.set_source_rgb(*col); ctx.set_line_width(ww); ctx.stroke()
    ctx.set_operator(cairo.OPERATOR_ATOP)
    if fabric:
        pat = cairo.SurfacePattern(grain(col)); pat.set_extend(cairo.EXTEND_REPEAT)
        k = 256 / (1.3 * H); pat.set_matrix(cairo.Matrix(k, 0, 0, k, 0, 0)); ctx.set_source(pat); ctx.paint()
    if details: details()
    ctx.set_operator(cairo.OPERATOR_OVER)
    ctx.pop_group_to_source(); ctx.paint()


def unit(v):
    v = np.asarray(v, float); L = np.linalg.norm(v); return v / L if L > 1e-9 else np.array([0.0, 1.0])


def line(ctx, a, b, col, lw, alpha=1.0):
    ctx.new_path(); ctx.move_to(*a); ctx.line_to(*b); ctx.set_source_rgba(*col, alpha); ctx.set_line_width(lw); ctx.stroke()


def draw_ponytail(ctx, hc, H, face, view, col, ow, sh, swing=0.0):
    b = -face * (1 - view) if view < 0.85 else 0.55
    root = hc + np.array([b * 0.30 * H, -0.36 * H]); c1 = hc + np.array([b * 0.95 * H, -0.42 * H])
    c2 = hc + np.array([b * 0.90 * H + swing * H * 0.5, 0.10 * H]); tip = hc + np.array([b * 0.62 * H + swing * H, 0.62 * H])
    pts = [(1 - u) ** 3 * root + 3 * (1 - u) ** 2 * u * c1 + 3 * (1 - u) * u * u * c2 + u ** 3 * tip for u in np.linspace(0, 1, 17)]
    L, R = [], []
    for k in range(17):
        d = unit(pts[min(k + 1, 16)] - pts[max(k - 1, 0)]); n = np.array([-d[1], d[0]]); u = k / 16
        r = H * (0.11 * (1 - u) + 0.15 * math.sin(math.pi * min(u * 1.3, 1)) * (1 - u) + 0.015)
        L.append(pts[k] + n * r); R.append(pts[k] - n * r)
    pp = L + R[::-1]

    def path():
        ctx.new_path(); ctx.move_to(*pp[0])
        for q in pp[1:]: ctx.line_to(*q)
        ctx.close_path()
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.save(); ctx.translate(*sh); path(); ctx.set_source_rgb(*BLACK); ctx.set_line_width(2 * ow); ctx.stroke_preserve(); ctx.fill(); ctx.restore()
    path(); ctx.set_source_rgb(*BLACK); ctx.set_line_width(2 * ow); ctx.stroke_preserve(); ctx.set_source_rgb(*col); ctx.fill()


def draw_actor(ctx, s):
    if s['o'].get('hero'):                     # the stylist: the plain white rig figure, exactly as the style sheet draws it
        J, fig = s['J'], s['fig']
        draw_ponytail(ctx, np.asarray(J['head'], float), fig.H, J['face'], J['view'], (0.80, 0.80, 0.82), fig.ow,
                      (0.11 * fig.w, 0.10 * fig.w), s['o'].get('hair_swing', 0.0))
        fig.draw(ctx, s['p'])
    else:
        draw_person(ctx, s['fig'], s['J'], s['o'])


def draw_person(ctx, fig, J, o):
    H, w, wt, ow = fig.H, fig.w, fig.wt, fig.ow
    view, face = J['view'], J['face']
    sh = (0.11 * w, 0.10 * w)
    fl = o.get('flash', {})
    up, perp, hip, top, hc = [np.asarray(J[k], float) for k in ('up', 'perp', 'hip', 'top', 'head')]
    skin = o['skin']

    def C(key, far=False):
        c = o[key]
        if fl.get(key, 0) > 0: c = lerpt(c, (1, 1, 1), fl[key])
        return farc(c) if far else c

    def head():
        circle_sticker(ctx, hc, 0.5 * H, skin, ow, sh)
        if o.get('beret'):
            ctx.save(); ctx.translate(*(hc + np.array([-face * (1 - view) * 0.08 * H, -0.36 * H])))
            draw_beret(ctx, C('beret'), H, ow, tilt=-0.30 * face * (1 - view) - 0.1); ctx.restore()

    def arm(name, far):
        s_, e, h = [np.asarray(q, float) for q in J[name]]
        sk = farc(skin) if far else skin
        piece(ctx, [([s_, e, h], w)], sk, ow, sh, H, fabric=False)
        if not o.get('jacket'): return
        col = C('jacket', far)
        cuff = e + (h - e) * 0.70
        u = unit(h - e)

        def det():
            line(ctx, cuff - u * 0.09 * H + np.array([-u[1], u[0]]) * w * 0.6, cuff - u * 0.09 * H - np.array([-u[1], u[0]]) * w * 0.6,
                 GM.mulc(col, 0.72), 0.035 * H)
        piece(ctx, [([s_, e, cuff], w)], col, ow, sh, H, details=det)

    def leg(name, far):
        hp, kn, an, toe = [np.asarray(q, float) for q in J[name]]
        if o.get('trousers'):
            col = C('trousers', far)

            def det():
                for a, b in ((hp, kn), (kn, an)):           # pressed crease
                    line(ctx, a + (b - a) * 0.1, a + (b - a) * 0.9, GM.mulc(col, 0.82), 0.022 * H)
            piece(ctx, [([hp, kn, an], w)], col, ow, sh, H, details=det)
        else:
            piece(ctx, [([hp, kn, an], w)], farc(skin) if far else skin, ow, sh, H, fabric=False)
        sc = C('shoes', far and o['shoes'] != SILVER)
        style = o.get('shoe_style', 'flat')

        def sdet():
            d = toe - an; L = np.linalg.norm(d)
            if L < 1e-3: return
            uu = d / L; n = np.array([-uu[1], uu[0]]);
            if n[1] < 0: n = -n
            if style == 'sneaker':
                line(ctx, an + n * w * 0.36 - uu * w * 0.5, toe + n * w * 0.36 + uu * w * 0.5, (0.97, 0.97, 0.98), 0.12 * H)
            if o['shoes'] == SILVER:
                line(ctx, an - n * w * 0.18, toe - n * w * 0.18, (1, 1, 1), 0.06 * H, 0.9)
        piece(ctx, [([an, toe], w * 1.04)], sc, ow, sh, H, fabric=False, details=sdet)
        if style == 'heel':
            d = unit(toe - an); hb = an - d * 0.10 * H + np.array([0, 0.26 * H])
            line(ctx, an - d * 0.10 * H + np.array([0, 0.12 * H]), hb, BLACK, 0.07 * H)

    def torso():
        if not o.get('jacket'):
            piece(ctx, [([hip, top], wt)], skin, ow, (0.11 * wt, 0.10 * wt), H, fabric=False); return
        col = C('jacket')
        hem = hip - up * 0.42 * H
        inner = o.get('top') if (o.get('top') is not None and o['jacket'] != o['top']) else None
        front = 0.0 if view > 0.6 else -face * wt * 0.28

        def det():
            F = lambda q: q + perp * front
            if inner is not None:                          # open jacket: the top shows down the middle
                ctx.new_path(); ctx.move_to(*F(top - perp * wt * 0.24)); ctx.line_to(*F(top + perp * wt * 0.24))
                ctx.line_to(*F(hem + perp * wt * 0.10 + up * 0.1 * H)); ctx.line_to(*F(hem - perp * wt * 0.10 + up * 0.1 * H)); ctx.close_path()
                ctx.set_source_rgb(*inner); ctx.fill()
            dk = GM.mulc(col, 0.68)
            for sgn in (-1, 1):                            # lapels
                a = F(top + perp * sgn * wt * 0.26 - up * 0.02 * H); b = F(top + perp * sgn * wt * 0.36 - up * 0.45 * H)
                c = F(top + perp * sgn * wt * 0.03 - up * 0.95 * H)
                ctx.new_path(); ctx.move_to(*a); ctx.line_to(*b); ctx.line_to(*c)
                ctx.set_source_rgb(*dk); ctx.set_line_width(0.03 * H); ctx.stroke()
            line(ctx, F(top - up * 0.95 * H), F(hem + up * 0.05 * H), dk, 0.025 * H)
            if inner is None:
                ctx.new_path(); ctx.arc(*F(top - up * 1.15 * H + perp * wt * 0.08), 0.045 * H, 0, 2 * math.pi); ctx.set_source_rgb(*dk); ctx.fill()
            for sgn in (-1, 1):                            # pocket welts
                pc = F(hip + up * 0.05 * H + perp * sgn * wt * 0.30)
                line(ctx, pc - perp * 0.09 * H, pc + perp * 0.09 * H, dk, 0.025 * H)
        piece(ctx, [([hem, top], wt)], col, ow, (0.11 * wt, 0.10 * wt), H, details=det)
        if o.get('belt'):
            P = hip + up * 0.30 * H
            piece(ctx, [([P - perp * wt * 0.32, P + perp * wt * 0.32], 0.13 * H)], C('belt'), ow * 0.7, (0.02 * H, 0.02 * H), H, fabric=False,
                  details=lambda: (ctx.rectangle(*(P + perp * (0 if view > 0.5 else -face * 0.08 * H) - np.array([0.045 * H, 0.055 * H])), 0.09 * H, 0.11 * H),
                                   ctx.set_source_rgb(0.85, 0.86, 0.9), ctx.fill()))

    def bag():
        if not o.get('bag'): return
        hand = J['armB'][2]
        ctx.save(); ctx.translate(hand[0], hand[1]); ctx.rotate(o.get('bag_swing', 0.0))
        draw_bag(ctx, C('bag'), H, ow, o['bag'] == SILVER); ctx.restore()

    draw_ponytail(ctx, hc, H, face, view, farc(skin), ow, sh, o.get('hair_swing', 0.0))
    if view < 0.5:
        arm('armA', True); leg('legA', True); leg('legB', False); torso(); head(); arm('armB', False); bag()
    else:
        leg('legA', True); leg('legB', False); torso(); head(); arm('armA', True); arm('armB', False); bag()


# ======================================================================== cast & timeline
SN = [4 * BEAT, 8 * BEAT, 12 * BEAT]               # 2.67, 5.33, 8.00 : outfit snaps on the beat
CUTS = [0.0, 2 * BEAT, 6 * BEAT, 10 * BEAT, 14 * BEAT, DUR]   # hard cuts on the beat
WOMEN = [
    dict(face=1, view=0.0, base=dict(jacket=BROWN, trousers=WHITE, shoes=BROWN),
         changes=[(SN[0], 'shoes', BABY), (SN[0], 'bag', BABY)],
         emoji=[(0.0, '😕'), (SN[0], '😳'), (SN[0] + BEAT, '😍')],
         rows=[('BROWN', BROWN), ('WHITE', WHITE), ('BABY BLUE', BABY)], newrow=2),
    dict(face=-1, view=0.0, base=dict(jacket=OLIVE, trousers=CREAM, shoes=WHITE),
         changes=[(SN[1], 'shoes', BURG), (SN[1], 'bag', BURG), (SN[1], 'beret', BURG), (SN[1], 'belt', BURG)],
         emoji=[(0.0, '😐'), (SN[1], '😮'), (SN[1] + BEAT, '💅')],
         rows=[('OLIVE', OLIVE), ('CREAM', CREAM), ('BURGUNDY', BURG)], newrow=2),
    dict(face=-1, view=0.62, base=dict(jacket=TOPBLK, trousers=CHAR, shoes=TOPBLK), top=TOPBLK,
         changes=[(SN[2], 'jacket', PINK), (SN[2] + BEAT / 2, 'bag', SILVER), (SN[2] + BEAT, 'shoes', SILVER)],
         emoji=[(0.0, '😩'), (SN[2], '😳'), (SN[2] + 1.5 * BEAT, '🤑')],
         rows=[('CHARCOAL', CHAR), ('PINK', PINK), ('SILVER', SILVER)], newrow=None),
]
for i, wd in enumerate(WOMEN):
    s_ = SN[i]
    wd['row_t'] = [s_ + 0.15 + 0.3 * k for k in range(3)] if i < 2 else [s_ + 0.1, s_ + BEAT / 2 + 0.1, s_ + BEAT + 0.1]
    wd['pal_out'] = 99.0
PAL_BACK = 99.0
# each shot: stylist (x, G, idle facing), women {i: (x, G at shot start, velocity, face, view)}
SHOTS = [
    dict(st=(0.0, 1080.0), w={0: (-560.0, 1200.0, (175.0, 0.0), 1, 0.0), 1: (560.0, 980.0, (-175.0, 0.0), -1, 0.0),
                              2: (190.0, 860.0, (-12.0, 60.0), -1, 0.85)}, zmax=1.0),
    dict(st=(300.0, 1150.0), w={0: (-600.0, 1150.0, (185.0, 0.0), 1, 0.0)}, zmax=1.35),
    dict(st=(-300.0, 1150.0), w={1: (600.0, 1150.0, (-185.0, 0.0), -1, 0.0)}, zmax=1.35),
    dict(st=(-300.0, 1180.0), w={2: (200.0, 880.0, (-20.0, 110.0), -1, 0.85)}, zmax=1.35),
    dict(st=(270.0, 930.0), w={1: (-250.0, 930.0, (-95.0, 0.0), -1, 0.0), 0: (420.0, 1430.0, (95.0, 0.0), 1, 0.0),
                               2: (10.0, 1300.0, (-14.0, 70.0), -1, 0.85)}, zmax=1.0, final=True),
]


def shot_at(t):
    for k in range(len(SHOTS)):
        if CUTS[k] <= t < CUTS[k + 1]: return k
    return len(SHOTS) - 1


def wpos(i, t):
    k = shot_at(t); spec = SHOTS[k]['w'].get(i)
    if spec is None: return None
    x0, G0, v, face, view = spec; dt = t - CUTS[k]
    return x0 + v[0] * dt, G0 + v[1] * dt, v, face, view


THROWS = [dict(R=SN[0] - 0.6, f=-1), dict(R=SN[1] - 0.6, f=1), dict(R=SN[2] - 0.6, f=1)]
# (throw, item, colour, arrival, attach, woman)
ITEMS = [(0, 'shoes', BABY, SN[0], 'feet', 0), (0, 'bag', BABY, SN[0], 'hand', 0),
         (1, 'shoes', BURG, SN[1], 'feet', 1), (1, 'bag', BURG, SN[1], 'hand', 1), (1, 'beret', BURG, SN[1], 'head', 1),
         (2, 'jacket', PINK, SN[2], 'torso', 2), (2, 'bag', SILVER, SN[2] + BEAT / 2, 'hand', 2),
         (2, 'shoes', SILVER, SN[2] + BEAT, 'feet', 2)]
HIT_T = 14 * BEAT                                  # 9.33  cut to the final shot, music resolves
FINAL_T = HIT_T + 0.35                             # "THREE COLORS."
FINAL_T2 = HIT_T + 1.0                             # "BETTER FITS."
DUST_T = [9.75, 10.05, 10.35]


# ======================================================================== walking
def arm_fk(sh, theta, bend, H):
    """screen-plane FK: theta=0 hangs straight down, positive swings toward +x; bend rotates the forearm"""
    e = sh + 1.2 * H * np.array([math.sin(theta), math.cos(theta)])
    h = e + 1.08 * H * np.array([math.sin(theta + bend), math.cos(theta + bend)])
    return h, e


def shoulders(fig, hip, lean, view):
    H = fig.H
    up = np.array([math.sin(lean), -math.cos(lean)]); perp = np.array([math.cos(lean), math.sin(lean)])
    top = np.asarray(hip, float) + up * fig.torso
    sx = view * (fig.wt / 2 + 2.6 * fig.ow + fig.w / 2); shoff = (fig.w / 2 - fig.wt / 2) + 0.04 * H
    return top - perp * sx - up * shoff, top + perp * sx - up * shoff


def set_arm(p, fig, which, sh, theta, bend):
    h, e = arm_fk(sh, theta, bend, fig.H)
    p['h' + which] = tuple(h); p['e' + which] = tuple(e - (sh + h) / 2 + np.array([0, 1e-3]))


def walk_pose(fig, t, x, G, face, view, vel, carry=False, conf=1.0):
    H = fig.H
    TW = 2 * BEAT
    ph = (t / TW) % 1.0
    speed = math.hypot(*vel)
    S = speed * TW / 2.0                           # stride = ground travel per step: planted feet don't slide
    dirv = np.array(vel) / max(speed, 1e-6)
    hy0 = fig.stand_hip_y(G)

    def foot(p):
        if p < 0.5:
            u = p / 0.5; return S / 2 - S * u, 0.0
        u = (p - 0.5) / 0.5; e = 0.5 - 0.5 * math.cos(math.pi * u)
        return -S / 2 + S * e, 0.26 * H * math.sin(math.pi * u) ** 1.5
    pA, pB = ph, (ph + 0.5) % 1
    dA, lA = foot(pA); dB, lB = foot(pB)
    sw = math.cos(2 * math.pi * ph)                 # +1 : leg A forward (contact), arms opposite
    ds = abs(dA if pA < 0.5 else dB) * (1 - 0.3 * view) * abs(dirv[0])
    hy = G - math.sqrt(max((3.0 * H * 0.996) ** 2 - ds ** 2, 1.0)) - 0.18 * H     # standing leg straight
    hx = view * 0.22 * H
    fA = np.array([x - hx, G]) + dirv * dA * (1 - 0.3 * view) - np.array([0, lA])
    fB = np.array([x + hx, G]) + dirv * dB * (1 - 0.3 * view) - np.array([0, lB])
    amp = 0.72 * H * (1 - 0.6 * view)

    def handp(s_, side, k=1.0):
        a = s_ * k
        return (x + face * amp * a + side * 0.42 * H * view, hy - 0.08 * H - 0.24 * H * abs(a))
    hA = handp(-sw, -1); hB = handp(sw, 1, 0.3 if carry else 1.0)
    return dict(hip=(x, hy), lean=face * 0.06 * (1 - view), view=view, face=face, fA=tuple(fA), fB=tuple(fB),
                hA=hA, hB=hB), ph


def woman_state(i, t):
    wd = WOMEN[i]
    wp = wpos(i, t)
    if wp is None: return None
    x, G, vel, face, view = wp
    H = depthH(G); fig = Figure(H, 'white')
    conf = sstep((t - SN[i]) / 0.5)
    o = dict(wd['base']); o['flash'] = {}
    for tc, k, c in wd['changes']:
        if t >= tc:
            o[k] = c
            f = 1 - (t - tc) / 0.12
            if f > 0: o['flash'][k] = f
    p, ph = walk_pose(fig, t, x, G, face, view, vel, carry=bool(o.get('bag')), conf=conf)
    o.update(skin=SKIN_W, top=wd.get('top'), shoe_style=SHOE_STYLE[o['shoes']], hair_swing=0.06 * math.sin(2 * math.pi * ph * 2 - 0.8),
             bag_swing=-face * 0.08 + 0.06 * math.sin(2 * math.pi * ph))
    return dict(fig=fig, J=fig.solve(p), o=o, x=x, G=G, H=H)


def attach_point(s, key):
    J, H = s['J'], s['H']
    if key == 'feet': return (np.array(J['legA'][2]) + np.array(J['legB'][2])) / 2
    if key == 'hand': return np.array(J['armB'][2]) + np.array([0, 0.5 * H])
    if key == 'head': return np.array(J['head']) - np.array([0, 0.4 * H])
    return (np.array(J['hip']) + np.array(J['top'])) / 2


# ======================================================================== stylist
def stylist_pose(t, x0, G, fig):
    H = fig.H; hy = fig.stand_hip_y(G)
    base = dict(hip=(x0, hy), lean=0.0, view=1.0, face=1.0)
    J0 = fig.solve(base)
    rest = dict(hA=tuple(J0['tgt']['hA']), hB=tuple(J0['tgt']['hB']), fA=tuple(J0['tgt']['fA']), fB=tuple(J0['tgt']['fB']))

    def B(**kw):
        d = dict(hip=(x0, hy), lean=0.0, view=1.0, face=1.0, head=(0.0, 0.0), eA=(-1.0, 0.4), eB=(1.0, 0.4), **rest)
        d.update(kw); return d

    def throw(f, ph):
        """side-view underhand toss with the near arm (B): swing back low, straight arm forward-up, finish pointing"""
        d = B(view=0.12, face=float(f), fA=(x0 - f * 0.34 * H, G), fB=(x0 + f * 0.42 * H, G))
        Hh = lambda dx, dy: (x0 + f * dx * H, hy - dy * H)
        if ph == 'wind':
            d.update(hip=(x0 - f * 0.08 * H, hy - 0.04 * H), lean=-f * 0.08, head=(-f * 0.03, 0.0),
                     hB=Hh(-1.45, 0.35), hA=Hh(0.95, 0.85), eB=(-f, 0.2), eA=(-f, 0.6))
        elif ph == 'release':
            d.update(hip=(x0 + f * 0.10 * H, hy - 0.06 * H), lean=f * 0.10, head=(f * 0.04, -0.03),
                     hB=Hh(2.15, 2.3), hA=Hh(-0.95, 0.65), eB=(f, 0.3), eA=(-f, 0.6))
        else:
            d.update(hip=(x0 + f * 0.12 * H, hy - 0.06 * H), lean=f * 0.08, head=(f * 0.03, -0.05),
                     hB=Hh(1.85, 3.25), hA=Hh(-0.6, 0.35), eB=(f, 0.3), eA=(-f, 0.6))
        return d
    keys = [(0.0, B())]
    for thr in THROWS:
        R, f = thr['R'], thr['f']
        keys += [(R - 0.75, B()), (R - 0.22, throw(f, 'wind')), (R, throw(f, 'release')), (R + 0.25, throw(f, 'follow')), (R + 0.95, B())]
    c1 = B(hA=(x0 - 0.15 * H, hy - 1.45 * H), hB=(x0 + 0.40 * H, hy - 1.6 * H), head=(0.0, 0.05))
    c2 = B(hA=(x0 - 0.40 * H, hy - 1.55 * H), hB=(x0 + 0.12 * H, hy - 1.42 * H), head=(0.0, 0.05))
    keys += [(9.5, B()), (DUST_T[0] - 0.1, c1), (DUST_T[0] + 0.05, c2), (DUST_T[1], c1), (DUST_T[1] + 0.15, c2),
             (DUST_T[2], c1), (DUST_T[2] + 0.15, c2), (10.9, B(head=(0.04, -0.04)))]
    p = dict(keys[-1][1])
    for (t0, p0), (t1, p1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            u = sstep((t - t0) / (t1 - t0))
            p = {k: (lerpt(p0[k], p1[k], u) if isinstance(p0[k], tuple) else lerp(p0[k], p1[k], u)) for k in p0}
            break
    wgt = clamp((p['view'] - 0.8) / 0.2)
    p['hip'] = (p['hip'][0] + 0.02 * H * math.sin(math.pi * t / BEAT) * wgt, p['hip'][1])
    return p


def stylist_state(t):
    ST_X, ST_G = SHOTS[shot_at(t)]['st']
    H = depthH(ST_G); fig = Figure(H, 'white')
    p = stylist_pose(t, ST_X, ST_G, fig)
    o = dict(skin=SKIN_HERO, hero=True, hair_swing=-0.6 * p['lean'] + 0.03 * math.sin(2 * math.pi * t / BEAT))
    return dict(fig=fig, J=fig.solve(p), p=p, o=o, x=p['hip'][0], G=ST_G, H=H)


def throw_hand(t, f):
    return np.array(stylist_state(t)['J']['armB'][2])


# ======================================================================== camera
SAFE = (50, 300, 950, 1460)
EMO_PAD, PAL_W, PAL_H = 100, 245, 135


def cam_fit(pairs, zmax):
    x0 = y0 = 1e9; x1 = y1 = -1e9
    for x, G in pairs:
        H = depthH(G)
        x0 = min(x0, x - 1.1 * H); x1 = max(x1, x + 1.1 * H); y0 = min(y0, G - 6.6 * H - 1.3 * H); y1 = max(y1, G + 0.3 * H)
    y1 += PAL_H + 40
    z = min(zmax, (SAFE[2] - SAFE[0] - 40) / (x1 - x0 + PAL_W * 0.5), (SAFE[3] - SAFE[1] - 40) / (y1 - y0))
    cx = (x0 + x1) / 2 - ((SAFE[0] + SAFE[2]) / 2 - W / 2) / z
    cy = (y0 + y1) / 2 - ((SAFE[1] + SAFE[3]) / 2 + 70 - HT / 2) / z
    return np.array([cx, cy, z])


def shot_cam(k):
    sh_ = SHOTS[k]; t0, t1 = CUTS[k], CUTS[k + 1]
    pts = [sh_['st']]
    for i in sh_['w']:
        for tt_ in (t0, t1 - 1e-3):
            x, G, *_ = wpos(i, tt_); pts.append((x, G))
    return cam_fit(pts, sh_['zmax'])


def camera_track(n):
    cams = [shot_cam(k) for k in range(len(SHOTS))]
    out = []
    for f in range(n):
        t = f / FPS; k = shot_at(t)
        u = (t - CUTS[k]) / (CUTS[k + 1] - CUTS[k])
        cx, cy, z = cams[k]
        zz = z * (1.0 + 0.035 * sstep(u))                       # slow push-in through every shot
        out.append((cx, cy - 20 * sstep(u), zz))
    return out


def _unused_camera_track(n):
    out = []; c = cam_target(0.0); dt = 1.0 / FPS
    for f in range(n):
        t = f / FPS; tg = cam_target(t)
        c = c + (tg - c) * (1 - math.exp(-dt / 0.45))
        out.append(tuple(c))
    return out


# ======================================================================== background
def draw_bg(ctx, t):
    ST_X, ST_G = SHOTS[shot_at(t)]['st']
    ctx.set_source_rgb(0.012, 0.012, 0.015); ctx.paint()
    # back wall: faint vertical gradient so it is not dead black
    g = cairo.LinearGradient(0, -400, 0, 900)
    g.add_color_stop_rgb(0, 0.01, 0.01, 0.012); g.add_color_stop_rgb(1, 0.045, 0.045, 0.05)
    ctx.rectangle(-1500, -1500, 4500, 2400); ctx.set_source(g); ctx.fill()
    # sidewalk slab
    FB, FF = 700, 1620
    g = cairo.LinearGradient(0, FB, 0, FF)
    g.add_color_stop_rgb(0, 0.055, 0.055, 0.06); g.add_color_stop_rgb(1, 0.085, 0.085, 0.09)
    ctx.rectangle(-1500, FB, 4500, FF - FB); ctx.set_source(g); ctx.fill()
    # paving joints in perspective, barely there
    ctx.set_line_width(2); ctx.set_source_rgba(1, 1, 1, 0.035)
    for k in range(1, 8):
        y = FB + (FF - FB) * (k / 8.0) ** 1.4
        ctx.move_to(-1500, y); ctx.line_to(3000, y); ctx.stroke()
    vp = (0, -1600)
    for xb in range(-2600, 3800, 200):
        u0 = (FB - vp[1]) / (FF - vp[1])
        ctx.move_to(vp[0] + (xb - vp[0]) * u0, FB); ctx.line_to(xb, FF); ctx.stroke()
    # back edge highlight + front curb face
    ctx.set_source_rgba(1, 1, 1, 0.10); ctx.set_line_width(2); ctx.move_to(-1500, FB); ctx.line_to(3000, FB); ctx.stroke()
    ctx.rectangle(-1500, FF, 4500, 34); ctx.set_source_rgb(0.11, 0.11, 0.12); ctx.fill()
    ctx.set_source_rgba(1, 1, 1, 0.22); ctx.set_line_width(2.5); ctx.move_to(-1500, FF); ctx.line_to(3000, FF); ctx.stroke()
    ctx.rectangle(-1500, FF + 34, 4500, 1500); ctx.set_source_rgb(0.018, 0.018, 0.02); ctx.fill()
    ctx.set_source_rgba(1, 1, 1, 0.06); ctx.set_line_width(8)
    for x in range(-1400, 3000, 300):
        ctx.move_to(x, FF + 190); ctx.line_to(x + 150, FF + 190); ctx.stroke()
    # street lamp behind the stylist
    lx, ltop = ST_X - 200 * (1 if ST_X >= 0 else -1), ST_G - 900
    LS = 1 if ST_X >= 0 else -1
    ctx.set_source_rgb(0.10, 0.10, 0.11); ctx.set_line_width(9)
    ctx.move_to(lx, ST_G - 60); ctx.line_to(lx, ltop); ctx.curve_to(lx, ltop - 60, lx + 40 * LS, ltop - 70, lx + 110 * LS, ltop - 55); ctx.stroke()
    ctx.rectangle(lx + 110 * LS - 30, ltop - 62, 60, 16); ctx.fill()
    # light cone (soft, additive) and pool on the floor
    cone = cairo.LinearGradient(0, ltop - 45, 0, ST_G + 40)
    cone.add_color_stop_rgba(0, 1, 0.97, 0.92, 0.10); cone.add_color_stop_rgba(1, 1, 0.97, 0.92, 0.0)
    ctx.new_path(); ctx.move_to(lx + 100 * LS, ltop - 45); ctx.line_to(lx + 120 * LS, ltop - 45)
    ctx.line_to(ST_X + 380, ST_G + 40); ctx.line_to(ST_X - 300, ST_G + 40); ctx.close_path()
    ctx.set_source(cone); ctx.fill()
    for (cx, cy, rx, ry, a) in ((ST_X + 10, ST_G + 5, 430, 120, 0.20), (ST_X + 10, ST_G + 5, 220, 60, 0.18)):
        ctx.save(); ctx.translate(cx, cy); ctx.scale(1, ry / rx)
        rg = cairo.RadialGradient(0, 0, 0, 0, 0, rx)
        rg.add_color_stop_rgba(0, 1, 0.98, 0.94, a); rg.add_color_stop_rgba(1, 1, 0.98, 0.94, 0)
        ctx.set_source(rg); ctx.arc(0, 0, rx, 0, 2 * math.pi); ctx.fill(); ctx.restore()
    rg = cairo.RadialGradient(lx + 110 * LS, ltop - 40, 0, lx + 110 * LS, ltop - 40, 70)
    rg.add_color_stop_rgba(0, 1, 0.98, 0.93, 1.0); rg.add_color_stop_rgba(0.25, 1, 0.98, 0.93, 0.6); rg.add_color_stop_rgba(1, 1, 0.98, 0.93, 0)
    ctx.set_source(rg); ctx.arc(lx + 110 * LS, ltop - 40, 70, 0, 2 * math.pi); ctx.fill()
    # dust drifting in the beam
    rng = np.random.default_rng(5)
    for k in range(46):
        u = rng.uniform(); v = rng.uniform(); sp = rng.uniform(6, 16); ph = rng.uniform(0, 100)
        yy = ltop + (ST_G - ltop) * ((v + t * sp / 900) % 1.0)
        spread = (yy - ltop) / (ST_G - ltop)
        xx = lx + 110 * LS + (u - 0.5) * (40 + 650 * spread) + 150 * spread * LS + 6 * math.sin(t * 0.8 + ph)
        a = 0.35 * math.sin(math.pi * ((v + t * sp / 900) % 1.0)) * rng.uniform(0.4, 1)
        ctx.set_source_rgba(1, 1, 1, a); ctx.arc(xx, yy, rng.uniform(1.2, 2.6), 0, 2 * math.pi); ctx.fill()


def light_pool(ctx, x, G, H, a):
    ctx.save(); ctx.translate(x, G + 0.1 * H); ctx.scale(1, 0.25)
    rg = cairo.RadialGradient(0, 0, 0, 0, 0, 2.6 * H)
    rg.add_color_stop_rgba(0, 1, 1, 1, a); rg.add_color_stop_rgba(1, 1, 1, 1, 0)
    ctx.set_source(rg); ctx.arc(0, 0, 2.6 * H, 0, 2 * math.pi); ctx.fill(); ctx.restore()
    ctx.save(); ctx.translate(x, G + 0.12 * H); ctx.scale(1, 0.2)
    rg = cairo.RadialGradient(0, 0, 0, 0, 0, 1.0 * H)
    rg.add_color_stop_rgba(0, 0, 0, 0, 0.55); rg.add_color_stop_rgba(1, 0, 0, 0, 0)
    ctx.set_source(rg); ctx.arc(0, 0, 1.0 * H, 0, 2 * math.pi); ctx.fill(); ctx.restore()


# ======================================================================== fx (world)
def burst(ctx, c, dt, H, col):
    """snap: fx.py sparkles popping around the piece as it lands (style sheet effect)"""
    if dt < 0 or dt > 0.55: return
    for k, (a, rr, d0) in enumerate(((-2.4, 0.9, 0.0), (-0.6, 1.0, 0.04), (0.5, 0.8, 0.08), (2.2, 0.95, 0.03), (-1.5, 1.2, 0.10))):
        d = dt - d0
        if d < 0 or d > 0.42: continue
        u = d / 0.42
        r = 0.32 * H * math.sin(math.pi * min(u * 1.6, 1.0)) * (1 - 0.3 * u)
        p = (c[0] + math.cos(a) * rr * H * (0.7 + 0.4 * u), c[1] + math.sin(a) * rr * H * (0.7 + 0.4 * u))
        sparkle(ctx, p[0], p[1], r)


def twinkles(ctx, s, dt, seed, color=(1, 1, 1)):
    if dt < 0 or dt > 1.2: return
    rng = np.random.default_rng(seed); H = s['H']; J = s['J']
    cx, cy = s['x'], (J['hip'][1] + J['top'][1]) / 2
    for i in range(8):
        d = dt - i * 0.07
        if d < 0 or d > 0.7: continue
        a = rng.uniform(0, 2 * math.pi); rad = H * rng.uniform(1.0, 1.9)
        x = cx + rad * math.cos(a) * 0.8; y = cy + rad * math.sin(a) * 1.4 - d * H * 0.5
        k = d / 0.7; r = H * 0.28 * math.sin(math.pi * k)
        ctx.save(); ctx.translate(x, y); ctx.rotate(math.pi / 4 * (i % 2))
        ctx.new_path(); ctx.move_to(0, -r); ctx.curve_to(0, 0, 0, 0, r, 0); ctx.curve_to(0, 0, 0, 0, 0, r)
        ctx.curve_to(0, 0, 0, 0, -r, 0); ctx.curve_to(0, 0, 0, 0, 0, -r); ctx.close_path()
        ctx.set_source_rgb(*color); ctx.fill(); ctx.restore()


def coin_rain(ctx, s, dt):
    if dt < 0 or dt > 1.3: return
    rng = np.random.default_rng(42); H = s['H']; J = s['J']; hx, hy = J['head']
    for i in range(9):
        d = dt - i * 0.05
        if d < 0: continue
        vx = rng.uniform(-1.6, 1.6) * H; vy = -rng.uniform(2.5, 4.0) * H
        x = hx + vx * d; y = hy - 0.6 * H + vy * d + 6.0 * H * d * d
        a = clamp(1.3 - d * 1.1)
        sz = 0.22 * H; sq = abs(math.cos(d * 9 + i))
        ctx.save(); ctx.translate(x, y); ctx.scale(max(0.15, sq), 1)
        ctx.rectangle(-sz / 2, -sz / 2, sz, sz); ctx.set_source_rgba(1.0, 0.82, 0.25, a); ctx.fill()
        ctx.rectangle(-sz / 2, -sz / 2, sz, sz * 0.25); ctx.set_source_rgba(1, 1, 1, a * 0.5); ctx.fill()
        ctx.restore()


def dust_puff(ctx, p, dt, H):
    if dt < 0 or dt > 0.6: return
    k = dt / 0.6
    for i in range(6):
        a = -math.pi / 2 + (i - 2.5) * 0.55
        d = H * (0.25 + 0.9 * k); r = H * (0.06 + 0.07 * k)
        ctx.new_path(); ctx.arc(p[0] + d * math.cos(a), p[1] + d * math.sin(a) * 0.7, r, 0, 2 * math.pi)
        ctx.set_source_rgba(1, 1, 1, 0.5 * (1 - k)); ctx.fill()


def draw_flying(ctx, t, women, sub=5):
    for idx, it in enumerate(ITEMS):
        ti, kind, col, ta, key, wi = it
        R, f = THROWS[ti]['R'], THROWS[ti]['f']
        if women[wi] is None: continue
        H = women[wi]['H']
        group = [i for i in ITEMS if i[0] == ti]; k = group.index(it)
        if R - 0.62 <= t < R:
            hp = throw_hand(t, f)
            sc = popin(t - (R - 0.62), 0.25) * 0.62
            ctx.save(); ctx.translate(hp[0] + (k - 1) * 0.3 * H, hp[1] - 0.35 * H - k * 0.12 * H); ctx.scale(sc, sc)
            draw_item(ctx, kind, col, H); ctx.restore()
        elif R <= t < ta:
            start = throw_hand(R, f); end = attach_point(women[wi], key)
            arc = H * (2.4 + 0.7 * k)

            def at(u):
                ue = 1 - (1 - u) ** 1.6                       # floaty: fast out, soft landing
                return start + (end - start) * ue - np.array([0, arc * 4 * ue * (1 - ue)]), ue
            u = (t - R) / (ta - R)
            # speed streaks (style sheet: white line with black edge)
            pa, _ = at(clamp(u - 0.10)); pb, _ = at(u)
            d = pb - pa; L = np.linalg.norm(d)
            if L > 2:
                dd = d / L; nn = np.array([-dd[1], dd[0]])
                for k2, off in enumerate((-0.35, 0.0, 0.35)):
                    q0 = pb - dd * (0.9 + 0.5 * (k2 == 1)) * H + nn * off * H; q1 = pb - dd * 0.45 * H + nn * off * H
                    ctx.new_path(); ctx.move_to(*q0); ctx.line_to(*q1); ctx.set_line_cap(cairo.LINE_CAP_ROUND)
                    ctx.set_source_rgba(*BLACK, 0.9); ctx.set_line_width(0.09 * H); ctx.stroke_preserve()
                    ctx.set_source_rgb(1, 1, 1); ctx.set_line_width(0.045 * H); ctx.stroke()
            # motion blur: accumulate sub-shutter copies
            for s_ in range(sub):
                us = clamp(u - (s_ / sub) * 0.5 / FPS / (ta - R))
                p, ue = at(us)
                ctx.save(); ctx.translate(*p); ctx.rotate(ue * 3 * math.pi * f); sc = 0.62 + 0.38 * ue; ctx.scale(sc, sc)
                ctx.push_group(); draw_item(ctx, kind, col, H); ctx.pop_group_to_source(); ctx.paint_with_alpha(1.0 / sub * (1.6 if s_ == 0 else 1))
                ctx.restore()


# ======================================================================== overlay (screen): text, emoji, palettes
def tracked_text(ctx, text, x, y, size, track, alpha=1.0, align='center', reveal=None, color=(1, 1, 1)):
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL); ctx.set_font_size(size)
    adv = [ctx.text_extents(ch).x_advance + track for ch in text]
    total = sum(adv) - track
    x0 = x - total / 2 if align == 'center' else x
    cx = x0
    for i, ch in enumerate(text):
        a = alpha
        if reveal is not None:
            a *= clamp(reveal * len(text) - i)
        if a > 0.003:
            ctx.move_to(cx, y); ctx.set_source_rgba(*color, a); ctx.show_text(ch)
        cx += adv[i]
    return total


def text_width(text, size, track):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 4, 4); c = cairo.Context(s)
    c.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL); c.set_font_size(size)
    return sum(c.text_extents(ch).x_advance + track for ch in text) - track


CHIP, ROW, LSIZE, LTRACK = 30, 44, 25, 3


def draw_palette(ctx, wd, t, ax, ay):
    maxw = max(text_width(n, LSIZE, LTRACK) for n, _ in wd['rows'])
    left = ax - (CHIP + 16 + maxw) / 2
    vis = clamp((wd['pal_out'] - t) / 0.35) if t < PAL_BACK else 1.0
    for i, (name, col) in enumerate(wd['rows']):
        u = clamp((t - wd['row_t'][i]) / 0.35)
        if t >= HIT_T: u = clamp((t - HIT_T - 0.3 - 0.25 * WOMEN.index(wd) - 0.1 * i) / 0.35)
        u *= vis
        if u <= 0: continue
        e = ease_io(u)
        y = ay + i * ROW + (1 - e) * 14
        ctx.save()
        ctx.push_group()
        PX.voxel_chip(ctx, left, y, CHIP, col, metal=(col == SILVER))
        tracked_text(ctx, name, left + CHIP + 16, y + CHIP / 2 + LSIZE * 0.38, LSIZE, LTRACK, align='left')
        ctx.pop_group_to_source(); ctx.paint_with_alpha(e)
        ctx.restore()
        if wd['newrow'] == i and 0 < t - wd['row_t'][i] < 0.6:     # the colour that completes the look
            k = (t - wd['row_t'][i]) / 0.6
            ctx.new_path(); ctx.rectangle(left - 6 - 10 * k, y - 6 - 10 * k, CHIP + 12 + 20 * k, CHIP + 12 + 20 * k)
            ctx.set_source_rgba(*col, 1 - k); ctx.set_line_width(3); ctx.stroke()


def draw_emoji(ctx, ch, cx, cy, size, scale, alpha=1.0):
    if scale <= 0.01: return
    surf, w, h = EMO[ch]
    s = size / (w * 0.62) * scale                  # sprite has glow padding; ~62% of it is the face
    ctx.save(); ctx.translate(cx, cy); ctx.scale(s, s)
    ctx.set_source_surface(surf, -w / 2, -h / 2); ctx.get_source().set_filter(cairo.FILTER_GOOD); ctx.paint_with_alpha(alpha)
    ctx.restore()


def emoji_confetti(ctx, cx, cy, dt, seed):
    if dt < 0 or dt > 0.45: return
    rng = np.random.default_rng(seed); k = dt / 0.45
    for i in range(10):
        a = rng.uniform(0, 2 * math.pi); d = rng.uniform(55, 95) * (1 - (1 - k) ** 2)
        s = 9 * (1 - k)
        ctx.rectangle(cx + math.cos(a) * d - s / 2, cy + math.sin(a) * d - s / 2, s, s)
        ctx.set_source_rgba(1.0, 0.80, 0.25, 1 - k); ctx.fill()


def current_emoji(wd, t):
    ch, tc = wd['emoji'][0][1], wd['emoji'][0][0]
    for t0, e in wd['emoji']:
        if t >= t0: ch, tc = e, t0
    return ch, tc


# ======================================================================== compositing helpers
def surf_np(s):
    s.flush()
    return np.ndarray((HT, s.get_stride() // 4, 4), np.uint8, s.get_data())[:, :W].astype(np.float32) / 255.0


def down(a, k): return a.reshape(a.shape[0] // k, k, a.shape[1] // k, k, -1).mean((1, 3))


_UPS = {}


def up(a, k):
    """bilinear upsample via cairo"""
    h, w = a.shape[:2]
    src = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    b = np.ndarray((h, src.get_stride() // 4, 4), np.uint8, src.get_data())
    q = np.clip(a * 255, 0, 255).astype(np.uint8)
    b[:, :w, :3] = q[..., :3]; b[:, :w, 3] = 255
    src.mark_dirty()
    dst = cairo.ImageSurface(cairo.FORMAT_ARGB32, w * k, h * k); c = cairo.Context(dst)
    c.scale(k, k); c.set_source_surface(src, 0, 0); c.get_source().set_filter(cairo.FILTER_BILINEAR)
    c.get_source().set_extend(cairo.EXTEND_PAD); c.paint(); dst.flush()
    return np.ndarray((h * k, dst.get_stride() // 4, 4), np.uint8, dst.get_data())[:, :w * k, :3].astype(np.float32) / 255.0


def blur_rgb(a, sigma, k):
    d = down(a, k)
    d = np.stack([gaussian_filter(d[..., i], sigma / k) for i in range(d.shape[2])], -1)
    return up(d, k)


GRAIN = np.random.default_rng(1).normal(0, 1, (8, HT // 2, W // 2)).astype(np.float32)
yy, xx = np.mgrid[0:HT, 0:W].astype(np.float32)
VIG = (1 - 0.55 * np.clip((((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - HT * 0.47) / (HT * 0.62)) ** 2) - 0.25, 0, 1) ** 1.2)[..., None]
del yy, xx


# ======================================================================== frame
EMO = None


def render_frame(t, cam, surfs):
    sb, sr, sa, sf, so = surfs
    cx, cy, z = cam

    def wctx(s):
        c = cairo.Context(s); c.set_operator(cairo.OPERATOR_CLEAR); c.paint(); c.set_operator(cairo.OPERATOR_OVER)
        c.translate(W / 2, HT / 2); c.scale(z, z); c.translate(-cx, -cy); return c

    def scr(p): return ((p[0] - cx) * z + W / 2, (p[1] - cy) * z + HT / 2)
    st = stylist_state(t)
    women = [woman_state(i, t) for i in range(3)]
    present = [i for i in range(3) if women[i] is not None]
    active = int(np.argmin([abs(t - s_) for s_ in SN])) if CUTS[1] <= t < CUTS[4] else None

    # background + light pools
    cb = wctx(sb); draw_bg(cb, t)
    light_pool(cb, st['x'], st['G'], st['H'], 0.0)
    for i in present:
        s = women[i]; light_pool(cb, s['x'], s['G'], s['H'], 0.10 if i == active else 0.05)

    # actors (depth sorted) + reflections
    cr = wctx(sr); ca = wctx(sa)
    order = sorted([(st['G'], -1)] + [(women[i]['G'], i) for i in present])
    for G, i in order:
        s = st if i < 0 else women[i]
        draw_actor(ca, s)
        cr.save(); cr.push_group()
        cr.translate(0, 2 * s['G'] + 0.25 * s['H']); cr.scale(1, -1); draw_actor(cr, s)
        pat = cr.pop_group(); cr.restore()
        m = cairo.LinearGradient(0, s['G'], 0, s['G'] + 3.2 * s['H'])
        m.add_color_stop_rgba(0, 0, 0, 0, 0.30); m.add_color_stop_rgba(1, 0, 0, 0, 0.0)
        cr.set_source(pat); cr.mask(m)

    # fx
    cf = wctx(sf)
    draw_flying(cf, t, women)
    for ti, kind, col, ta, key, wi in ITEMS:
        if women[wi] is not None: burst(cf, attach_point(women[wi], key), t - ta, women[wi]['H'], col)
    if women[0] is not None: twinkles(cf, women[0], t - WOMEN[0]['emoji'][2][0], 1)
    if women[1] is not None: twinkles(cf, women[1], t - WOMEN[1]['emoji'][2][0], 2)
    if women[2] is not None: coin_rain(cf, women[2], t - WOMEN[2]['emoji'][2][0])
    for td in DUST_T:
        dust_puff(cf, st['J']['armB'][2], t - td, st['H'])

    # overlay: palettes, emoji, text
    co = cairo.Context(so); co.set_operator(cairo.OPERATOR_CLEAR); co.paint(); co.set_operator(cairo.OPERATOR_OVER)
    for i in present:
        s = women[i]
        ax, ay = scr((s['x'], s['G']))
        draw_palette(co, WOMEN[i], t, ax, ay + 18 + 0.3 * s['H'] * z)
        ch, tc = current_emoji(WOMEN[i], t)
        if tc > 0:
            sc = 1.0 + 0.28 * math.exp(-(t - tc) * 9) * math.cos((t - tc) * 22)
        else:
            sc = popin(t - 0.25 - 0.15 * i, 0.4) if t < CUTS[1] else 1.0
        hx, hy = scr((s['J']['head'][0], s['J']['head'][1] - 0.5 * s['H']))
        bob = 4 * math.sin(2 * math.pi * t / (2 * BEAT) + i)
        esz = clamp(0.95 * s['H'] * z, 60, 108)
        ey = hy - esz * 0.95 - 10 + bob
        draw_emoji(co, ch, hx, ey, esz, sc)
        if tc > 0: emoji_confetti(co, hx, ey, t - tc, i * 7 + int(tc * 10))
    if t < 2.0:
        a = clamp((1.95 - t) / 0.35)
        tracked_text(co, "THE STREET STYLIST", W / 2, 230, 46, 7, alpha=a, reveal=clamp((t - 0.25) / 0.9))
        ln = clamp((t - 0.9) / 0.5) * a
        co.set_source_rgba(1, 1, 1, 0.5 * ln); co.rectangle(W / 2 - 160 * ln, 258, 320 * ln, 2); co.fill()
    if t >= FINAL_T:
        tracked_text(co, "THREE COLORS.", W / 2, 205, 50, 7, reveal=clamp((t - FINAL_T) / 0.55))
        tracked_text(co, "BETTER FITS.", W / 2, 285, 50, 7, reveal=clamp((t - FINAL_T2) / 0.5))

    # ---- composite (premultiplied float)
    bg = surf_np(sb)[..., :3]
    rf = surf_np(sr); rfb = blur_rgb(rf[..., :3], 3.0, 2)
    img = bg * (1 - np.clip(blur_rgb(rf[..., 3:].repeat(3, -1), 3.0, 2), 0, 1) * 0.0) + rfb
    ac = surf_np(sa)
    halo = blur_rgb(ac[..., 3:].repeat(3, -1), 22, 4)
    img = img + halo * np.array([0.16, 0.16, 0.17], np.float32)
    img = ac[..., :3] + img * (1 - ac[..., 3:])
    fx_ = surf_np(sf); img = fx_[..., :3] + img * (1 - fx_[..., 3:])
    ov = surf_np(so); img = ov[..., :3] + img * (1 - ov[..., 3:])
    # bloom
    lum = img.max(-1, keepdims=True)
    bright = img * np.clip((lum - 0.55) / 0.45, 0, 1)
    img = img + blur_rgb(bright, 28, 4) * 0.55 + blur_rgb(bright, 7, 2) * 0.35
    # grade: gentle S-curve, vignette, grain, fades
    img = img * VIG
    img = img / (1 + img * 0.12)
    g = GRAIN[int(t * FPS) % len(GRAIN)]
    g = np.repeat(np.repeat(g, 2, 0), 2, 1)[..., None]
    img = img + g * 0.010
    fade = clamp(t / 0.5) * clamp((DUR - t) / 0.45)
    img = np.clip(img * fade, 0, 1)
    return (img * 255 + 0.5).astype(np.uint8)


# ======================================================================== audio
SR = 44100


def make_audio(path):
    from scipy.signal import butter, sosfilt, fftconvolve
    N = int((DUR + 0.2) * SR)
    rng = np.random.default_rng(11)

    def tt(d): return np.arange(int(d * SR)) / SR
    def bp(x, lo, hi): return sosfilt(butter(2, [lo, hi], btype='band', fs=SR, output='sos'), x)
    def hp(x, fc): return sosfilt(butter(2, fc, btype='high', fs=SR, output='sos'), x)
    def lp(x, fc): return sosfilt(butter(2, fc, btype='low', fs=SR, output='sos'), x)

    dry = np.zeros((N, 2)); wet = np.zeros((N, 2))

    def add(sig, t0, gain=1.0, pan=0.0, send=0.3):
        i = int(round(t0 * SR)); n = min(len(sig), N - i)
        if n <= 0: return
        a = (pan + 1) * math.pi / 4
        st = np.stack([sig[:n] * math.cos(a), sig[:n] * math.sin(a)], 1) * 1.414 * gain
        dry[i:i + n] += st; wet[i:i + n] += st * send

    def mtof(m): return 440 * 2 ** ((m - 69) / 12)

    # --- instruments
    def kick():
        t = tt(0.5); f = 48 + 70 * np.exp(-t / 0.03)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.22) + rng.standard_normal(len(t)) * np.exp(-t / 0.003) * 0.08

    def snare():
        t = tt(0.4)
        n = bp(rng.standard_normal(len(t)), 1200, 6000) * np.exp(-t / 0.09)
        return n * 0.7 + np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05) * 0.4

    def hat(open_=False):
        t = tt(0.25 if open_ else 0.07)
        return hp(rng.standard_normal(len(t)), 8000) * np.exp(-t / (0.08 if open_ else 0.015))

    def epiano(midi, d=2.6, vel=1.0):
        t = tt(d); f = mtof(midi)
        mod = np.sin(2 * np.pi * f * 2 * t) * 1.2 * np.exp(-t / 0.4)
        s = np.sin(2 * np.pi * f * t + mod) * np.exp(-t / 1.6)
        s += 0.18 * np.sin(2 * np.pi * f * 3 * t) * np.exp(-t / 0.3)
        s *= np.minimum(t / 0.006, 1) * (1 + 0.12 * np.sin(2 * np.pi * 4.5 * t)) * vel
        return s

    def sub(midi, d):
        t = tt(d); f = mtof(midi)
        env = np.minimum(t / 0.02, 1) * np.minimum((d - t) / 0.08, 1)
        return (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t)) * env

    def whoosh(d=0.6):
        t = tt(d); n = rng.standard_normal(len(t)); u = t / d
        fc = 300 + 1600 * np.sin(np.pi * np.minimum(u * 1.1, 1)) ** 2
        y = np.zeros(len(t)); low = band = 0.0
        for i in range(len(t)):
            fco = 2 * math.sin(math.pi * fc[i] / SR)
            hi = n[i] - low - 1.1 * band; band += fco * hi; low += fco * band; y[i] = band
        return y * np.sin(np.pi * u) ** 2 * 0.45

    def snap():
        t = tt(0.2)
        s = hp(rng.standard_normal(len(t)), 2200) * np.exp(-t / 0.008) * 1.1
        s += np.sin(2 * np.pi * 1800 * t) * np.exp(-t / 0.01) * 0.35
        s += np.sin(2 * np.pi * 150 * t) * np.exp(-t / 0.05) * 0.5
        return s

    def chime(notes, gap=0.06, dec=0.6, amp=0.3):
        out = np.zeros(int((len(notes) * gap + 1.6) * SR))
        for k, m in enumerate(notes):
            t = tt(1.5); f = mtof(m)
            s = (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2.01 * f * t) + 0.1 * np.sin(2 * np.pi * 4.2 * f * t))
            s *= np.minimum(t / 0.002, 1) * np.exp(-t / dec) * amp
            i = int(k * gap * SR); out[i:i + len(s)] += s
        return out

    def chaching():
        out = np.zeros(int(2.0 * SR)); t = tt(0.1)
        out[:len(t)] += bp(rng.standard_normal(len(t)), 2500, 7500) * np.exp(-t / 0.025) * 0.7 + np.sin(2 * np.pi * 95 * t) * np.exp(-t / 0.03) * 0.6
        for off, base in ((0.09, 2637.0), (0.11, 3520.0)):
            t = tt(1.6); s = np.zeros(len(t))
            for ratio, dec, amp in ((1.0, 0.8, 1.0), (2.76, 0.35, 0.45), (5.4, 0.18, 0.25), (0.5, 0.6, 0.2)):
                s += amp * np.sin(2 * np.pi * base * ratio * t) * np.exp(-t / dec)
            i = int(off * SR); out[i:i + len(s)] += s[:len(out) - i] * 0.35
        return out

    def blip(m, d=0.09):                      # 8-bit pop for the pixel emoji
        t = tt(d); f = mtof(m) * (1 + 0.5 * (t < 0.03))
        return np.sign(np.sin(2 * np.pi * f * t)) * np.exp(-t / 0.035) * 0.18

    def brush():
        t = tt(0.18); return bp(rng.standard_normal(len(t)), 1500, 6000) * np.sin(np.pi * t / 0.18) ** 2 * 0.3

    # --- music: Am9 - Fmaj7 - Cmaj7 - Em7, one bar = 4 beats
    bar = 4 * BEAT
    chords = [(57, 60, 64, 67, 71), (53, 57, 60, 64), (48, 55, 59, 64), (52, 55, 59, 62)]
    roots = [33, 29, 36, 28]
    for b in range(4):
        t0 = b * bar
        if t0 >= HIT_T: break
        for j, m in enumerate(chords[b]):
            add(epiano(m + 12 * (m < 50), d=bar + 0.6, vel=0.55), t0 + j * 0.012, 0.32, pan=(-0.25 + 0.5 * j / 4), send=0.5)
        add(sub(roots[b], min(bar, HIT_T - t0)), t0, 0.55, send=0.05)
        for k in range(4):
            bt = t0 + k * BEAT
            if bt >= HIT_T - 0.01: break
            if k in (0,) or (k == 2 and b % 2 == 1): add(kick(), bt, 0.85, send=0.05)
            if k == 2 and b % 2 == 0: add(kick(), bt + BEAT / 2, 0.6, send=0.05)
            if k in (1, 3): add(snare(), bt, 0.38, send=0.45)
            for h in range(2):
                ht = bt + h * BEAT / 2 + (0.035 if h else 0)
                if ht < HIT_T - 0.05: add(hat(), ht, 0.10 if h else 0.07, pan=0.3, send=0.1)
    # final: everything resolves on a wide Am9 with a deep sub drop
    for j, m in enumerate((45, 57, 60, 64, 67, 71, 76)):
        add(epiano(m, d=3.0, vel=0.7), HIT_T + j * 0.02, 0.32, pan=(-0.4 + 0.8 * j / 6), send=0.7)
    add(kick(), HIT_T, 1.0, send=0.2); add(sub(33, 2.4), HIT_T, 0.7, send=0.1)
    t = tt(3.0); add(hp(rng.standard_normal(len(t)), 5000) * np.exp(-t / 0.9) * 0.08, HIT_T, 1.0, send=0.6)
    # vinyl texture
    noise = lp(rng.standard_normal(N), 4000) * 0.006
    clicks = (rng.random(N) < 0.00012) * rng.uniform(0.05, 0.15, N)
    dry[:, 0] += noise + clicks; dry[:, 1] += noise + clicks

    # --- sound design (whoosh -> snap -> sparkle / cha-ching)
    for th in THROWS: add(whoosh(), th['R'] - 0.08, 0.9, -0.3, send=0.35)
    for ti, kind, col, ta, key, wi in ITEMS: add(snap(), ta, 0.75, -0.2, send=0.45)
    add(chime([84, 88, 91, 96]), WOMEN[0]['emoji'][2][0], 0.9, 0.2, send=0.6)
    add(chime([86, 89, 93, 98]), WOMEN[1]['emoji'][2][0], 0.9, -0.2, send=0.6)
    add(chaching(), WOMEN[2]['emoji'][2][0] - 0.09, 1.0, 0.0, send=0.5)
    for wd in WOMEN:
        for t0, e in wd['emoji'][1:]: add(blip(84 if e in '😍💅🤑' else 79), t0 + 0.01, 0.6, 0.1, send=0.2)
    for td in DUST_T: add(brush(), td - 0.06, 0.8, 0.3, send=0.3)
    for k in range(len("THE STREET STYLIST")):
        add(blip(96, 0.03) * 0.5, 0.25 + k * 0.9 / 18, 0.35, 0, send=0.2)

    # reverb: synthetic stereo IR
    ir_t = tt(2.2)
    ir = np.stack([rng.standard_normal(len(ir_t)), rng.standard_normal(len(ir_t))], 1) * np.exp(-ir_t / 0.55)[:, None]
    ir[:, 0] = lp(ir[:, 0], 6000); ir[:, 1] = lp(ir[:, 1], 6000)
    rev = np.stack([fftconvolve(wet[:, c], ir[:, c])[:N] for c in range(2)], 1) * 0.06
    mix = dry + rev
    mix = np.tanh(mix * 0.9)
    mix *= 0.88 / np.abs(mix).max()
    fade = int(0.5 * SR); mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
    mix[:int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))[:, None]
    data = (mix[:int(DUR * SR)] * 32767).astype(np.int16)
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR); wf.writeframes(data.tobytes())


# ======================================================================== main
def main():
    global EMO
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview', default=None)
    ap.add_argument('--out', default=os.path.join(HERE, 'street_stylist.mp4'))
    ap.add_argument('--audio-only', action='store_true')
    a = ap.parse_args()
    if a.audio_only:
        make_audio(os.path.join(HERE, 'audio.wav')); return
    EMO = PX.build_all(10)
    n = int(round(DUR * FPS))
    cams = camera_track(n)
    surfs = [cairo.ImageSurface(cairo.FORMAT_ARGB32, W, HT) for _ in range(5)]
    if a.preview:
        from PIL import Image
        for ts in a.preview.split(','):
            t = float(ts); f = min(int(round(t * FPS)), n - 1)
            Image.fromarray(render_frame(t, cams[f], surfs)[..., ::-1]).save(os.path.join(HERE, f'p2_{t:05.2f}.png'))
        return
    wav = os.path.join(HERE, 'audio.wav'); make_audio(wav)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{HT}', '-r', str(FPS),
           '-i', '-', '-i', wav, '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '256k', '-shortest', '-movflags', '+faststart', a.out]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(n):
        pr.stdin.write(np.ascontiguousarray(render_frame(f / FPS, cams[f], surfs)).tobytes())
        if f % 30 == 0: print(f'frame {f}/{n}', flush=True)
    pr.stdin.close(); pr.wait(); print('wrote', a.out)


if __name__ == '__main__':
    main()
