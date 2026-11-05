"""Fabric-rendered garments for the rig: shaded capsules, woven textures, folds, tailoring details."""
import math
import numpy as np
import cairo

BLACK = (0.04, 0.04, 0.045)
LIGHT = np.array([-0.55, -0.83])          # direction TO the key light (street lamp, upper left)


def mixc(a, b, u): return tuple(x + (y - x) * u for x, y in zip(a, b))
def mulc(a, k): return tuple(max(0.0, min(1.0, x * k)) for x in a)


def lum(c): return 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]


# ------------------------------------------------------------------ textures (seamless, periodic)
def _pnoise(n, sx, sy, rng):
    f = np.fft.fft2(rng.standard_normal((n, n)))
    ky = np.fft.fftfreq(n)[:, None]; kx = np.fft.fftfreq(n)[None, :]
    g = np.exp(-0.5 * ((kx * sx * 2 * np.pi) ** 2 + (ky * sy * 2 * np.pi) ** 2))
    a = np.real(np.fft.ifft2(f * g)); a -= a.mean(); return a / (a.std() + 1e-6)


def make_texture(kind, n=256, seed=0):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    P = 2 * np.pi
    if kind == 'twill':      # cotton twill: fine diagonal ribs
        v = 0.55 * np.sin(P * (x + y) / 8) + 0.45 * _pnoise(n, 0.8, 0.8, rng)
    elif kind == 'canvas':   # plain weave
        v = 0.5 * np.sin(P * x / 6) * np.sin(P * y / 6) + 0.25 * _pnoise(n, 0.8, 0.8, rng) + 0.25 * _pnoise(n, 8, 8, rng)
    elif kind == 'linen':    # slubby horizontal threads + soft vertical warp
        v = 0.5 * _pnoise(n, 14, 0.9, rng) + 0.25 * np.sin(P * x / 5) + 0.25 * _pnoise(n, 1, 1, rng)
    elif kind == 'knit':     # ribbed knit with v-stitches
        v = 0.55 * np.abs(np.sin(P * x / 12)) + 0.35 * np.sin(P * (y / 9 + np.abs((x % 12) - 6) / 12)) + 0.2 * _pnoise(n, 1, 1, rng)
    elif kind == 'suede':
        v = 0.6 * _pnoise(n, 3, 3, rng) + 0.4 * _pnoise(n, 14, 14, rng)
    elif kind == 'wool':
        v = 0.55 * _pnoise(n, 1.2, 1.2, rng) + 0.45 * _pnoise(n, 7, 7, rng)
    elif kind == 'leather':
        v = 0.7 * _pnoise(n, 2.2, 2.2, rng) + 0.3 * _pnoise(n, 10, 10, rng)
    else:                    # jersey
        v = 0.7 * _pnoise(n, 0.7, 0.7, rng) + 0.3 * _pnoise(n, 6, 6, rng)
    v = (v - v.min()) / (v.max() - v.min())
    g = (0.5 + (v - 0.5) * 0.9)
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, n, n)
    b = np.ndarray((n, s.get_stride() // 4, 4), np.uint8, s.get_data())
    q = (g * 255).astype(np.uint8)
    b[:, :n, 0] = q; b[:, :n, 1] = q; b[:, :n, 2] = q; b[:, :n, 3] = 255
    s.mark_dirty()
    return s


TEX = {}


def tex(kind):
    if kind not in TEX: TEX[kind] = make_texture(kind, seed=hash(kind) % 1000)
    return TEX[kind]


# fabric of each garment colour  (kind, texture strength, sheen)
FABRIC = {}


def set_fabric(col, kind, strength=0.55, sheen=0.0):
    FABRIC[tuple(round(c, 4) for c in col)] = (kind, strength, sheen)


def fabric_of(col):
    return FABRIC.get(tuple(round(c, 4) for c in col), ('jersey', 0.35, 0.0))


# ------------------------------------------------------------------ shading helpers
def shade_stops(col):
    """matte cloth: no specular, gentle light-to-shadow roll-off"""
    L = lum(col)
    if L > 0.8:
        return mixc(col, (1, 1, 1), 0.5), col, mixc(col, (0.78, 0.79, 0.85), 0.55), mixc(col, (0.68, 0.69, 0.76), 0.65)
    hi = mixc(col, (1, 1, 1), 0.07)
    sh = mixc(mulc(col, 0.80), (0.10, 0.11, 0.15), 0.06)
    core = mixc(mulc(col, 0.64), (0.06, 0.07, 0.10), 0.10)
    return hi, col, sh, core


def matte_fill(ctx, centre, axis, half, col):
    nn = axis if np.dot(axis, LIGHT) > 0 else -axis
    g = cairo.LinearGradient(*(centre + nn * half), *(centre - nn * half))
    hi, base, sh, core = shade_stops(col)
    g.add_color_stop_rgb(0, *hi); g.add_color_stop_rgb(0.4, *base); g.add_color_stop_rgb(0.8, *sh); g.add_color_stop_rgb(1, *core)
    ctx.set_source(g); ctx.paint()


def capsule_path(ctx, a, b, r):
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a; ang = math.atan2(d[1], d[0])
    ctx.new_path()
    ctx.arc(b[0], b[1], r, ang - math.pi / 2, ang + math.pi / 2)
    ctx.arc(a[0], a[1], r, ang + math.pi / 2, ang + 3 * math.pi / 2)
    ctx.close_path()


def cyl_gradient(a, b, r, col, metal=False):
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a; L = np.linalg.norm(d)
    n = np.array([-d[1], d[0]]) / L if L > 1e-6 else np.array([1.0, 0.0])
    if np.dot(n, LIGHT) < 0: n = -n
    m = (a + b) / 2
    p0, p1 = m + n * r, m - n * r
    g = cairo.LinearGradient(p0[0], p0[1], p1[0], p1[1])
    if metal:
        for s_, c in ((0, (0.97, 0.98, 1.0)), (0.18, (0.80, 0.82, 0.86)), (0.42, (0.55, 0.57, 0.62)), (0.6, (0.93, 0.94, 0.97)),
                      (0.82, (0.62, 0.64, 0.70)), (1, (0.42, 0.44, 0.50))):
            g.add_color_stop_rgb(s_, *c)
    else:
        hi, base, sh, core = shade_stops(col)
        g.add_color_stop_rgb(0, *hi); g.add_color_stop_rgb(0.4, *base); g.add_color_stop_rgb(0.8, *sh); g.add_color_stop_rgb(1, *core)
    return g, n


def apply_texture(ctx, col, scale_H, angle=0.0, alpha_mul=1.0):
    kind, strength, sheen = fabric_of(col)
    pat = cairo.SurfacePattern(tex(kind)); pat.set_extend(cairo.EXTEND_REPEAT); pat.set_filter(cairo.FILTER_GOOD)
    m = cairo.Matrix(); k = 256 / (1.6 * scale_H)
    m.rotate(-angle); m.scale(k, k)   # pattern space
    pat.set_matrix(cairo.Matrix(k * math.cos(angle), -k * math.sin(angle), k * math.sin(angle), k * math.cos(angle), 0, 0))
    ctx.set_source(pat); ctx.set_operator(cairo.OPERATOR_SOFT_LIGHT); ctx.paint_with_alpha(strength * alpha_mul)
    ctx.set_operator(cairo.OPERATOR_OVER)


def outline_poly(ctx, pts, w, ow, sh):
    ctx.set_line_cap(cairo.LINE_CAP_ROUND); ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    for (dx, dy) in (sh, (0, 0)):
        ctx.save(); ctx.translate(dx, dy); ctx.new_path(); ctx.move_to(*pts[0])
        for q in pts[1:]: ctx.line_to(*q)
        ctx.set_source_rgb(*BLACK); ctx.set_line_width(w + 2 * ow); ctx.stroke(); ctx.restore()


def cloth_segment(ctx, a, b, w, col, H, metal=False, texture=True, cap_end=True):
    """one shaded, textured cloth tube (no outline); cap_end=False cuts it flat at b (sleeve / trouser end)"""
    g, n = cyl_gradient(a, b, w / 2, col, metal)
    ctx.save()
    if cap_end:
        capsule_path(ctx, a, b, w / 2)
    else:
        a_, b_ = np.asarray(a, float), np.asarray(b, float); d = b_ - a_; L = np.linalg.norm(d); u = d / L
        nn = np.array([-u[1], u[0]]) * w / 2; ang = math.atan2(u[1], u[0])
        ctx.new_path(); ctx.arc(a_[0], a_[1], w / 2, ang + math.pi / 2, ang + 3 * math.pi / 2)
        ctx.line_to(*(b_ - nn)); ctx.line_to(*(b_ + nn)); ctx.close_path()
    ctx.clip()
    ctx.set_source(g); ctx.paint()
    if texture and not metal:
        d = np.asarray(b, float) - np.asarray(a, float)
        apply_texture(ctx, col, H, math.atan2(d[1], d[0]))
    ctx.restore()


def cloth_limb(ctx, pts, w, col, H, ow, sh, metal=False, folds=True):
    outline_poly(ctx, pts, w, ow, sh)
    for a, b in zip(pts, pts[1:]): cloth_segment(ctx, a, b, w, col, H, metal)
    if folds and len(pts) >= 3:
        fold_marks(ctx, pts[1], pts[0], pts[2], w, col, H)


def fold_marks(ctx, joint, p_prev, p_next, w, col, H):
    """soft drag folds: blurred shadow bands bunching towards the joint, clipped to the limb"""
    j = np.asarray(joint, float)
    for p_other, sgn in ((p_prev, -1), (p_next, 1)):
        d = (np.asarray(p_other, float) - j); L = np.linalg.norm(d)
        if L < 1e-3: continue
        u = d / L; n = np.array([-u[1], u[0]])
        ctx.save(); capsule_path(ctx, j, j + u * min(L, 0.6 * H), w / 2); ctx.clip()
        for k, off in enumerate((0.12, 0.26, 0.42)):
            c = j + u * off * H
            p0 = c + n * w * 0.6; p1 = c - n * w * 0.6 + u * 0.08 * H
            for lw, a in ((0.10 * H, 0.06), (0.05 * H, 0.08), (0.018 * H, 0.10)):
                ctx.new_path(); ctx.move_to(*p0); ctx.curve_to(*(c + n * 0.2 * w + u * 0.05 * H), *(c - n * 0.2 * w + u * 0.02 * H), *p1)
                ctx.set_source_rgba(*mulc(col, 0.45), a * (1 - 0.25 * k)); ctx.set_line_width(lw); ctx.stroke()
            q0 = p0 + u * 0.035 * H; q1 = p1 + u * 0.035 * H
            ctx.new_path(); ctx.move_to(*q0); ctx.line_to(*q1)
            ctx.set_source_rgba(1, 1, 1, 0.05); ctx.set_line_width(0.03 * H); ctx.stroke()
        ctx.restore()


def crease(ctx, a, b, H, col):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ctx.new_path(); ctx.move_to(*(a + (b - a) * 0.08)); ctx.line_to(*(a + (b - a) * 0.92))
    ctx.set_source_rgba(*mixc(col, (1, 1, 1), 0.5), 0.18); ctx.set_line_width(0.03 * H); ctx.stroke()


# ------------------------------------------------------------------ garments
def jacket_body(ctx, hip, top, up, perp, H, view, face, col, ow, sh, wt, kind='jacket', inner=None):
    """torso garment at the rig's torso width: straight sides, hem below the hip, collar, lapels, button, pockets"""
    half = wt / 2 * 1.02
    hem = (0.40 if kind == 'jacket' else 0.06) * H
    T = top + up * (wt / 2) * 0.9; B = hip - up * hem
    r_top, r_bot = half * 0.95, half * 0.25

    def path():
        ctx.new_path()
        c1 = T - up * r_top
        ctx.move_to(*(B - perp * half + up * r_bot)); ctx.line_to(*(c1 - perp * half))
        ang = math.atan2(-up[1], -up[0])  # direction 'down' along body
        ctx.arc(c1[0], c1[1], half, ang + math.pi / 2, ang + 3 * math.pi / 2)
        ctx.line_to(*(B + perp * half + up * r_bot))
        ctx.curve_to(*(B + perp * half), *(B + perp * half), *(B + perp * (half - r_bot)))
        ctx.line_to(*(B - perp * (half - r_bot)))
        ctx.curve_to(*(B - perp * half), *(B - perp * half), *(B - perp * half + up * r_bot))
        ctx.close_path()
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.save(); ctx.translate(*sh); path(); ctx.set_source_rgb(*BLACK); ctx.set_line_width(2 * ow); ctx.stroke_preserve(); ctx.fill(); ctx.restore()
    path(); ctx.set_source_rgb(*BLACK); ctx.set_line_width(2 * ow); ctx.stroke()
    ctx.save(); path(); ctx.clip()
    matte_fill(ctx, (T + B) / 2, perp, half, col)
    apply_texture(ctx, col, H, math.atan2(up[1], up[0]))
    vg = cairo.LinearGradient(*T, *B); vg.add_color_stop_rgba(0, 1, 1, 1, 0.04); vg.add_color_stop_rgba(1, 0, 0, 0, 0.16)
    ctx.set_source(vg); ctx.paint()
    det = mulc(col, 0.55)
    front = 0.0 if view > 0.6 else -face * half * 0.55        # where the front opening sits in side / 3-4 view
    Fc = lambda p: p + perp * front
    if inner is not None:                                     # open jacket shows the top underneath
        ctx.new_path(); ctx.move_to(*Fc(T - perp * half * 0.40)); ctx.line_to(*Fc(T + perp * half * 0.40))
        ctx.line_to(*Fc(B + perp * half * 0.16)); ctx.line_to(*Fc(B - perp * half * 0.16)); ctx.close_path()
        ctx.set_source_rgb(*inner); ctx.fill_preserve(); ctx.set_source_rgba(0, 0, 0, 0.6); ctx.set_line_width(0.025 * H); ctx.stroke()
    if kind == 'jacket':
        # collar + lapels
        for s_ in (-1, 1):
            p0 = Fc(T + perp * s_ * half * 0.45 - up * 0.02 * H)
            p2 = Fc(T + perp * s_ * half * 0.62 - up * 0.42 * H)
            p1 = Fc(T + perp * s_ * half * 0.06 - up * 0.92 * H)
            ctx.new_path(); ctx.move_to(*p0); ctx.line_to(*p2); ctx.line_to(*p1)
            ctx.set_source_rgba(*det, 0.9); ctx.set_line_width(0.028 * H); ctx.stroke()
            ctx.new_path(); ctx.move_to(*p0); ctx.line_to(*p2); ctx.line_to(*p1); ctx.line_to(*Fc(T + perp * s_ * 0.0 - up * 0.05 * H)); ctx.close_path()
            ctx.set_source_rgba(1, 1, 1, 0.06); ctx.fill()
        # front edge + button
        ctx.new_path(); ctx.move_to(*Fc(T - up * 0.92 * H)); ctx.line_to(*Fc(B + up * 0.02 * H))
        ctx.set_source_rgba(*det, 0.8); ctx.set_line_width(0.022 * H); ctx.stroke()
        if inner is None:
            bt = Fc(T - up * 1.05 * H + perp * 0.05 * H)
            ctx.new_path(); ctx.arc(*bt, 0.045 * H, 0, 2 * math.pi); ctx.set_source_rgb(*mulc(col, 0.4)); ctx.fill()
        # pocket welts
        for s_ in (-1, 1):
            pc = Fc(B + up * 0.42 * H + perp * s_ * half * 0.45)
            ctx.new_path(); ctx.move_to(*(pc - perp * 0.10 * H)); ctx.line_to(*(pc + perp * 0.10 * H))
            ctx.set_source_rgba(*det, 0.75); ctx.set_line_width(0.025 * H); ctx.stroke()
        # hem stitch
        ctx.set_dash([0.03 * H, 0.025 * H])
        ctx.new_path(); ctx.move_to(*(B - perp * half * 0.9 + up * 0.06 * H)); ctx.line_to(*(B + perp * half * 0.9 + up * 0.06 * H))
        ctx.set_source_rgba(*det, 0.6); ctx.set_line_width(0.012 * H); ctx.stroke(); ctx.set_dash([])
    else:
        nk = Fc(T - up * 0.02 * H)
        ctx.new_path(); ctx.move_to(*(nk - perp * 0.14 * H)); ctx.curve_to(*(nk - up * 0.14 * H), *(nk - up * 0.14 * H), *(nk + perp * 0.14 * H))
        ctx.set_source_rgba(*det, 0.7); ctx.set_line_width(0.028 * H); ctx.stroke()
    ctx.restore()


def sleeve(ctx, pts, w, col, H, ow, sh, skin):
    """sleeve over the arm, cuff before the hand, skin hand cap"""
    a, e, h = [np.asarray(p, float) for p in pts]
    cuff = e + (h - a * 0 - e) * 0.80
    outline_poly(ctx, [a, e, h], w * 1.04, ow, sh)
    # hand
    ctx.new_path(); ctx.arc(*h, w * 0.46, 0, 2 * math.pi); ctx.set_source_rgb(*skin); ctx.fill()
    cloth_segment(ctx, a, e, w * 1.04, col, H)
    cloth_segment(ctx, e, cuff, w * 1.04, col, H)
    fold_marks(ctx, e, a, cuff, w, col, H)
    d = cuff - e; L = np.linalg.norm(d); u = d / L; n = np.array([-u[1], u[0]])
    ctx.new_path(); ctx.move_to(*(cuff - u * 0.08 * H + n * w * 0.5)); ctx.line_to(*(cuff - u * 0.08 * H - n * w * 0.5))
    ctx.set_source_rgba(*mulc(col, 0.45), 0.6); ctx.set_line_width(0.03 * H); ctx.stroke()
    # edge of the cuff over the hand
    ctx.new_path(); ctx.arc(*cuff, w * 0.52, math.atan2(u[1], u[0]) - math.pi / 2, math.atan2(u[1], u[0]) + math.pi / 2)
    ctx.set_source_rgba(0, 0, 0, 0.55); ctx.set_line_width(ow * 0.8); ctx.stroke()


def trouser_leg(ctx, pts, w, col, H, ow, sh):
    hp, kn, an = [np.asarray(p, float) for p in pts[:3]]
    ww = w * 1.06
    outline_poly(ctx, [hp, kn, an], ww, ow, sh)
    cloth_segment(ctx, hp, kn, ww, col, H); cloth_segment(ctx, kn, an, ww, col, H)
    crease(ctx, hp, kn, H, col); crease(ctx, kn, an, H, col)
    fold_marks(ctx, kn, hp, an, ww, col, H)


def shoe(ctx, ankle, toe, H, col, style, ow, sh, view, w=None):
    a = np.asarray(ankle, float); t = np.asarray(toe, float)
    d = t - a; L = np.linalg.norm(d)
    if L < 0.12 * H:
        u = np.array([0.0, 1.0]) if L < 1e-3 else d / L
        heel = a - np.array([0, 0.02 * H]); tip = a + np.array([0, 0.10 * H])
    else:
        u = d / L; heel = a - u * 0.06 * H + np.array([0, 0.04 * H]); tip = a + u * 0.42 * H + np.array([0, 0.05 * H])
    ww = w if w is not None else 0.40 * H
    metal = style == 'metal'
    outline_poly(ctx, [heel, tip], ww, ow, sh)
    cloth_segment(ctx, heel, tip, ww, col, H, metal=metal, texture=style in ('sneaker',))
    v = tip - heel; Lv = np.linalg.norm(v); uu = v / Lv if Lv > 1e-3 else np.array([1.0, 0.0])
    nrm = np.array([-uu[1], uu[0]]);
    if nrm[1] < 0: nrm = -nrm                              # points to the ground
    if style == 'sneaker':
        ctx.new_path(); ctx.move_to(*(heel + nrm * ww * 0.36)); ctx.line_to(*(tip + nrm * ww * 0.36))
        ctx.set_source_rgb(0.97, 0.97, 0.98); ctx.set_line_width(0.11 * H); ctx.set_line_cap(cairo.LINE_CAP_ROUND); ctx.stroke()
        for k in range(3):
            c = heel + v * (0.45 + 0.13 * k) - nrm * ww * 0.18
            ctx.new_path(); ctx.move_to(*(c - uu * 0.04 * H - nrm * 0.05 * H)); ctx.line_to(*(c + uu * 0.04 * H + nrm * 0.05 * H))
            ctx.set_source_rgba(1, 1, 1, 0.85); ctx.set_line_width(0.025 * H); ctx.stroke()
    elif style in ('heel', 'metal', 'loafer'):
        ctx.new_path(); ctx.move_to(*(heel + nrm * ww * 0.40)); ctx.line_to(*(tip + nrm * ww * 0.40))
        ctx.set_source_rgba(0.05, 0.05, 0.06, 0.9); ctx.set_line_width(0.05 * H); ctx.set_line_cap(cairo.LINE_CAP_ROUND); ctx.stroke()
        if style in ('heel', 'metal') and L >= 0.12 * H:
            hb = heel + nrm * ww * 0.35
            ctx.new_path(); ctx.move_to(*hb); ctx.line_to(*(hb + nrm * 0.16 * H))
            ctx.set_source_rgb(*mulc(col, 0.6)); ctx.set_line_width(0.07 * H); ctx.stroke()
        # gloss
        ctx.new_path(); ctx.move_to(*(heel + v * 0.35 - nrm * ww * 0.22)); ctx.line_to(*(heel + v * 0.8 - nrm * ww * 0.2))
        ctx.set_source_rgba(1, 1, 1, 0.55 if style != 'metal' else 0.95); ctx.set_line_width(0.035 * H); ctx.stroke()


def bag(ctx, col, H, ow, metal=False):
    """structured leather bag hanging from the hand at the origin"""
    bw, bh = 0.84 * H, 0.62 * H
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.new_path(); ctx.arc(0, 0.30 * H, 0.25 * H, math.pi, 2 * math.pi)
    ctx.set_source_rgb(*BLACK); ctx.set_line_width(0.10 * H + 2 * ow); ctx.stroke_preserve()
    ctx.set_source_rgb(*mulc(col, 0.85) if not metal else (0.8, 0.82, 0.86)); ctx.set_line_width(0.10 * H); ctx.stroke()

    def body():
        x, y, w_, h_, r = -bw / 2, 0.28 * H, bw, bh, 0.14 * H
        ctx.new_path()
        ctx.arc(x + w_ - r, y + r, r, -math.pi / 2, 0); ctx.arc(x + w_ - r, y + h_ - r, r, 0, math.pi / 2)
        ctx.arc(x + r, y + h_ - r, r, math.pi / 2, math.pi); ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi); ctx.close_path()
    ctx.save(); ctx.translate(0.05 * H, 0.05 * H); body(); ctx.set_source_rgb(*BLACK); ctx.fill_preserve(); ctx.set_line_width(2 * ow); ctx.stroke(); ctx.restore()
    body(); ctx.set_source_rgb(*BLACK); ctx.set_line_width(2 * ow); ctx.stroke()
    ctx.save(); body(); ctx.clip()
    if metal:
        g = cairo.LinearGradient(-bw / 2, 0.28 * H, bw / 2, 0.9 * H)
        for s_, c in ((0, (0.98, 0.98, 1.0)), (0.25, (0.70, 0.72, 0.77)), (0.45, (0.95, 0.96, 0.98)), (0.7, (0.52, 0.54, 0.60)), (1, (0.85, 0.87, 0.9))):
            g.add_color_stop_rgb(s_, *c)
        ctx.set_source(g); ctx.paint()
    else:
        hi, base, shd, core = shade_stops(col)
        g = cairo.LinearGradient(-bw / 2, 0.28 * H, bw / 2, 0.9 * H)
        g.add_color_stop_rgb(0, *hi); g.add_color_stop_rgb(0.35, *base); g.add_color_stop_rgb(1, *shd)
        ctx.set_source(g); ctx.paint()
        pat = cairo.SurfacePattern(tex('leather')); pat.set_extend(cairo.EXTEND_REPEAT)
        k = 256 / (1.4 * H); pat.set_matrix(cairo.Matrix(k, 0, 0, k, 0, 0))
        ctx.set_source(pat); ctx.set_operator(cairo.OPERATOR_SOFT_LIGHT); ctx.paint_with_alpha(0.5); ctx.set_operator(cairo.OPERATOR_OVER)
    # flap, stitching, clasp, gloss
    ctx.new_path(); ctx.move_to(-bw / 2, 0.50 * H); ctx.curve_to(-bw / 4, 0.58 * H, bw / 4, 0.58 * H, bw / 2, 0.50 * H)
    ctx.set_source_rgba(0, 0, 0, 0.45); ctx.set_line_width(0.03 * H); ctx.stroke()
    ctx.set_dash([0.035 * H, 0.03 * H]); ctx.new_path(); ctx.move_to(-bw / 2 + 0.06 * H, 0.47 * H)
    ctx.curve_to(-bw / 4, 0.54 * H, bw / 4, 0.54 * H, bw / 2 - 0.06 * H, 0.47 * H)
    ctx.set_source_rgba(1, 1, 1, 0.35); ctx.set_line_width(0.012 * H); ctx.stroke(); ctx.set_dash([])
    ctx.rectangle(-0.06 * H, 0.53 * H, 0.12 * H, 0.08 * H); ctx.set_source_rgb(0.85, 0.86, 0.9); ctx.fill()
    ctx.new_path(); ctx.move_to(-bw / 2 + 0.12 * H, 0.36 * H); ctx.curve_to(-bw / 4, 0.32 * H, 0, 0.32 * H, bw / 6, 0.34 * H)
    ctx.set_source_rgba(1, 1, 1, 0.45 if not metal else 0.9); ctx.set_line_width(0.035 * H); ctx.stroke()
    ctx.restore()


def beret(ctx, col, H, ow, tilt=0.0):
    def b():
        ctx.new_path(); ctx.save(); ctx.rotate(tilt); ctx.scale(1, 0.55)
        ctx.arc(0, 0, 0.64 * H, math.pi, 2 * math.pi); ctx.close_path(); ctx.restore()
    ctx.save(); ctx.translate(0.04 * H, 0.04 * H); b(); ctx.set_source_rgb(*BLACK); ctx.fill_preserve(); ctx.set_line_width(2 * ow); ctx.stroke(); ctx.restore()
    b(); ctx.set_source_rgb(*BLACK); ctx.set_line_width(2 * ow); ctx.stroke()
    ctx.save(); b(); ctx.clip()
    g = cairo.RadialGradient(-0.25 * H, -0.3 * H, 0.05 * H, 0, -0.1 * H, 0.75 * H)
    hi, base, shd, core = shade_stops(col)
    g.add_color_stop_rgb(0, *hi); g.add_color_stop_rgb(0.45, *base); g.add_color_stop_rgb(1, *shd)
    ctx.set_source(g); ctx.paint(); apply_texture(ctx, col, H * 0.6, 0.0); ctx.restore()
    ctx.save(); ctx.rotate(tilt)
    ctx.new_path(); ctx.arc(0, -0.37 * H, 0.06 * H, 0, 2 * math.pi); ctx.set_source_rgb(*mulc(col, 0.8)); ctx.fill()
    ctx.restore()
