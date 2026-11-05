"""
Stick-figure rig — art style source.

Construction (all sizes in head-diameters, H):
  head     : circle, d = 1.0 H
  torso    : capsule, width 0.60 H, length 2.35 H
  limbs    : capsules, width 0.48 H   (upper arm 1.20, forearm 1.08, thigh 1.50, shin 1.50, foot 0.40)
  shoulders: arms start BESIDE the torso with a small gap (not welded on); legs sit side-by-side under it
  outline  : black stroke 0.12 x limb width + a black drop-shadow offset (+0.11w, +0.10w)
  depth    : far-side limbs one shade darker than near-side
Pose dict keys: hip (x,y), lean (rad), view (0 side .. 1 front), face (+1 right / -1 left),
  head (dx,dy in H), hA/hB hand targets, fA/fB foot targets, eA/eB/kA/kB elbow/knee bend hints,
  footlift_A/B (tiptoe angle).  Arms/legs are solved with 2-bone IK.
Requires: pycairo, numpy
"""
import math, cairo
import numpy as np

BLACK = (0.04, 0.04, 0.045)
SCHEMES = {
    "white": dict(front=(1, 1, 1), back=(0.80, 0.80, 0.82), glow=0.55),
    "grey":  dict(front=(0.62, 0.62, 0.64), back=(0.47, 0.47, 0.49), glow=0.0),
}


def v(a): return np.array(a, dtype=float)
def norm(a):
    n = np.linalg.norm(a); return a / n if n > 1e-9 else a * 0


def ik(root, target, l1, l2, pref):
    root, target = v(root), v(target)
    d = target - root
    dist = np.linalg.norm(d)
    dist_c = min(max(dist, abs(l1 - l2) + 1e-3), l1 + l2 - 1e-3)
    base = math.atan2(d[1], d[0])
    a = math.acos(max(-1, min(1, (l1 * l1 + dist_c * dist_c - l2 * l2) / (2 * l1 * dist_c))))
    best = None
    for s in (1, -1):
        j = root + l1 * v((math.cos(base + s * a), math.sin(base + s * a)))
        score = np.dot(j - (root + target) / 2, v(pref))
        if best is None or score > best[0]:
            best = (score, j)
    j = best[1]
    end = j + l2 * norm(target - j) if dist > 1e-6 else j
    return j, end


def capsule_path(ctx, a, b, r):
    a, b = v(a), v(b)
    d = b - a
    ang = math.atan2(d[1], d[0])
    ctx.new_path()
    ctx.arc(b[0], b[1], r, ang - math.pi / 2, ang + math.pi / 2)
    ctx.arc(a[0], a[1], r, ang + math.pi / 2, ang + 3 * math.pi / 2)
    ctx.close_path()


class Figure:
    def __init__(self, H, scheme):
        self.H = H; self.w = 0.48 * H; self.wt = 0.60 * H
        self.torso = 2.35 * H; self.ua = 1.2 * H; self.fa = 1.08 * H
        self.th = 1.5 * H; self.sh = 1.5 * H; self.foot = 0.40 * H
        self.sc = SCHEMES[scheme]
        self.ow = 0.12 * self.w

    def stand_hip_y(self, ground):
        return ground - (self.th + self.sh) - self.w * 0.5 + 0.18 * self.H

    def solve(self, p):
        H = self.H
        hip = v(p["hip"]); lean = p.get("lean", 0.0); view = p.get("view", 0.0); face = p.get("face", 1)
        up = v((math.sin(lean), -math.cos(lean))); perp = v((math.cos(lean), math.sin(lean)))
        top = hip + up * self.torso
        gap = 2.6 * self.ow
        sx = view * (self.wt / 2 + gap + self.w / 2)      # arms sit BESIDE the torso with a small gap
        hx = view * (self.w / 2 + 1.6 * self.ow)               # legs side by side, not merged
        shoff = (self.w / 2 - self.wt / 2) + 0.04 * H    # arm top cap level with torso top cap
        shA = top - perp * sx - up * shoff; shB = top + perp * sx - up * shoff
        hpA = hip - perp * hx - up * 0.18 * H; hpB = hip + perp * hx - up * 0.18 * H
        hd = p.get("head", (0, 0))
        headc = top + up * (0.47 * H + self.wt * 0.5 - 0.05 * H) + v(hd) * H
        # default hands: hanging
        def hang(sh, side):
            return sh + v((face * 0.10 * H * (1 - view) + side * 0.30 * H * view, 2.24 * H))
        hA = v(p.get("hA", hang(shA, -1))); hB = v(p.get("hB", hang(shB, 1)))
        def stand_foot(hp, side):
            return v((hp[0] + side * 0.08 * H * view, hp[1] + self.th + self.sh))
        fA = v(p.get("fA", stand_foot(hpA, -1))); fB = v(p.get("fB", stand_foot(hpB, 1)))
        # bend preferences
        side_e = v((-face, 0.6)); side_k = v((face, 0))
        eA = v(p.get("eA", (1 - view) * side_e + view * v((-1, 0.4))))
        eB = v(p.get("eB", (1 - view) * side_e + view * v((1, 0.4))))
        kA = v(p.get("kA", (1 - view) * side_k + view * v((-1, 0))))
        kB = v(p.get("kB", (1 - view) * side_k + view * v((1, 0))))
        elA, hA2 = ik(shA, hA, self.ua, self.fa, eA)
        elB, hB2 = ik(shB, hB, self.ua, self.fa, eB)
        knA, fA2 = ik(hpA, fA, self.th, self.sh, kA)
        knB, fB2 = ik(hpB, fB, self.th, self.sh, kB)
        def footdir(side, kn, an):
            sd = v((face, 0.12)); fd = v((side * 0.55, 0.85))
            d = norm((1 - view) * sd + view * fd)
            fl = p.get("footlift_" + ("A" if side < 0 else "B"), 0.0)
            ang = math.atan2(d[1], d[0]) + fl * face
            L = self.foot * (1 - 0.8 * view)
            return an + L * v((math.cos(ang), math.sin(ang)))
        return dict(tgt=dict(hA=hA, hB=hB, fA=fA, fB=fB), hip=hip, top=top, up=up, perp=perp, head=headc,
                    armA=[shA, elA, hA2], armB=[shB, elB, hB2],
                    legA=[hpA, knA, fA2, footdir(-1, knA, fA2)],
                    legB=[hpB, knB, fB2, footdir(1, knB, fB2)], view=view, face=face)

    # --- drawing ---------------------------------------------------------
    def _poly(self, ctx, pts):
        ctx.new_path(); ctx.move_to(*pts[0])
        for q in pts[1:]: ctx.line_to(*q)

    def _part(self, ctx, pts, color, width=None, shadow=True):
        w = width or self.w; ow = self.ow
        ctx.set_line_cap(cairo.LINE_CAP_ROUND); ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        if shadow:
            ctx.save(); ctx.translate(0.11 * w, 0.10 * w)
            self._poly(ctx, pts); ctx.set_source_rgb(*BLACK); ctx.set_line_width(w + 2 * ow); ctx.stroke()
            ctx.restore()
        self._poly(ctx, pts); ctx.set_source_rgb(*BLACK); ctx.set_line_width(w + 2 * ow); ctx.stroke()
        self._poly(ctx, pts); ctx.set_source_rgb(*color); ctx.set_line_width(w); ctx.stroke()

    def _head(self, ctx, c, color):
        r = 0.5 * self.H; ow = self.ow
        ctx.save(); ctx.translate(0.11 * self.w, 0.10 * self.w)
        ctx.new_path(); ctx.arc(c[0], c[1], r + ow, 0, 2 * math.pi); ctx.set_source_rgb(*BLACK); ctx.fill(); ctx.restore()
        ctx.new_path(); ctx.arc(c[0], c[1], r + ow, 0, 2 * math.pi); ctx.set_source_rgb(*BLACK); ctx.fill()
        ctx.new_path(); ctx.arc(c[0], c[1], r, 0, 2 * math.pi); ctx.set_source_rgb(*color); ctx.fill()

    def draw(self, ctx, p):
        J = self.solve(p); sc = self.sc; view = J["view"]
        front, back = sc["front"], sc["back"]
        order_front = view >= 0.5
        armA_front = p.get("armA_front", False); armB_back = p.get("armB_back", False)

        def arm(name, color): self._part(ctx, J[name], color)

        def leg(name, color): self._part(ctx, J[name], color)

        def torso(): self._part(ctx, [J["hip"], J["top"]], front, width=self.wt)

        bA = back; bB = front
        if not order_front:
            if not armA_front: arm("armA", bA)
            leg("legA", bA)
            torso(); leg("legB", bB)
            self._head(ctx, J["head"], front)
            if armA_front: arm("armA", bA)
            if not armB_back: arm("armB", bB)
        else:
            leg("legA", bA); leg("legB", bB); torso()
            self._head(ctx, J["head"], front)
            arm("armA", bA); arm("armB", bB)
        return J


def new_surface(W=1080, H=1920):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    c = cairo.Context(s); c.set_antialias(cairo.ANTIALIAS_BEST)
    return s, c


def surface_to_rgba(s):
    """premultiplied BGRA -> float32 RGBA (premultiplied), shape H,W,4"""
    buf = np.ndarray((s.get_height(), s.get_width(), 4), np.uint8, s.get_data()).astype(np.float32) / 255.0
    return buf[..., [2, 1, 0, 3]]
