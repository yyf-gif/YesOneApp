import skia, numpy as np, math, subprocess, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))

W, H = 1080, 1920
FPS = 60
DUR = 14.5
F = 1330
R = 34; TORSO = 140; THIGH = 102; SHIN = 102; UA = 80; FA = 76; FOOT = 24
SW = 26; TW = 32; OUTL = 10
T_GRAB = 0.58; T_PULL = 0.80; T_SNAP = 2.50
T_REL = 2.95
L_TIMES = [4.20, 5.10, 6.00, 6.90, 7.80, 8.70]
R_OFF = 0.08
R_TIMES = [x + R_OFF for x in L_TIMES]
T_S3END = 9.05
T_GROW = 2.97                          # each half regrows into a full person
T_SHOVE = 9.16                         # racks shoved off
T_CGRAB = 9.62; T_YANK = 9.74; T_UP = 10.10   # curtain grab / yank / fully up
T_POOF = 10.22                         # stylists vanish
T_POSE = 10.30                         # models pose
T_Q = 10.15
SHO = 33                              # half shoulder width: arms hang from round shoulders, gap to the torso                           # question lands as the backgrounds are revealed
CX = 540
DMAX = 170; EMAX = 52
HALF_REST = 400
S3_BASE = 190

FONT = skia.Typeface.MakeFromFile(os.path.join(HERE, 'fonts', 'ChakraPetch-SemiBold.ttf'))
FONT_LIGHT = skia.Typeface.MakeFromFile(os.path.join(HERE, 'fonts', 'ChakraPetch-Light.ttf'))
ITEM_L = [('RACING JACKET', (0.96, 0.42, 0.44)), ('CROSSBODY BAG', (0.80, 0.80, 0.84)), ('CARGO JEANS', (0.62, 0.74, 0.92)),
          ('SKATE SHOES', (0.58, 0.64, 1.00)), ('SKATEBOARD', (0.96, 0.96, 0.98)), ('NAVY BEANIE', (0.58, 0.64, 1.00))]
ITEM_R = [('FLORAL SHIRT', (1.00, 0.66, 0.32)), ('SUEDE JACKET', (0.70, 0.78, 0.42)), ('PLEATED TROUSERS', (0.93, 0.88, 0.76)),
          ('LEATHER BOOTS', (0.84, 0.58, 0.40)), ('SADDLE BAG', (0.84, 0.58, 0.40)), ('SUNGLASSES', (0.92, 0.62, 0.36))]
ACC_TXT_L = (1.00, 0.30, 0.72); ACC_TXT_R = (1.00, 0.70, 0.32)
NAME_L, NAME_R = 'SKATER', 'VINTAGE'

# ---------------- math ----------------
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def lerp(a, b, u): return a + (b - a) * u
def sstep(u): u = clamp(u); return u * u * u * (u * (u * 6 - 15) + 10)
def ease_out(u): u = clamp(u); return 1 - (1 - u) ** 3
def track(keys, t, ease=sstep):
    if t <= keys[0][0]: return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1: return lerp(v0, v1, ease((t - t0) / (t1 - t0)))
    return keys[-1][1]
def spring(t, w=20.0, z=0.45):
    if t <= 0: return 0.0
    wd = w * math.sqrt(1 - z * z)
    return 1 - math.exp(-z * w * t) * (math.cos(wd * t) + z * w / wd * math.sin(wd * t))
def v_add(a, b): return (a[0] + b[0], a[1] + b[1])
def v_sub(a, b): return (a[0] - b[0], a[1] - b[1])
def v_mul(a, s): return (a[0] * s, a[1] * s)
def v_len(a): return math.hypot(a[0], a[1])
def v_lerp(a, b, u): return (lerp(a[0], b[0], u), lerp(a[1], b[1], u))

def ik(a, t, l1, l2, hint):
    v = v_sub(t, a); dl = max(v_len(v), 1e-3)
    d = clamp(dl, 1e-3, l1 + l2 - 0.5)
    ux, uy = v[0] / dl, v[1] / dl
    ca = clamp((l1 * l1 + d * d - l2 * l2) / (2 * l1 * d), -1, 1)
    ang = math.acos(ca)
    best = None
    for s in (1, -1):
        c, sn = math.cos(s * ang), math.sin(s * ang)
        m = (a[0] + l1 * (ux * c - uy * sn), a[1] + l1 * (ux * sn + uy * c))
        score = (m[0] - a[0]) * hint[0] + (m[1] - a[1]) * hint[1]
        if best is None or score > best[0]: best = (score, m)
    return best[1], (a[0] + ux * d, a[1] + uy * d)

def foot_x(t, steps, desired, lift=26):
    x = desired(0.0)
    for ts, te in steps:
        if t >= te: x = desired(te)
        elif t > ts:
            u = (t - ts) / (te - ts)
            return lerp(x, desired(te), sstep(u)), math.sin(math.pi * u) * lift
        else: break
    return x, 0.0

def hit_bob(t, times, amp=6):
    v = 0.0
    for tk in times:
        if t > tk: v += amp * math.exp(-(t - tk) * 9) * max(0.0, math.sin((t - tk) * 22))
    return v

def pulse(t, a, p, b):
    if t <= a or t >= b: return 0.0
    if t < p: return sstep((t - a) / (p - a))
    return 1 - sstep((t - p) / (b - p))

# ---------------- halves / boyfriend ----------------
BF_HIP0 = F - 198
def half_x(t):
    return lerp(CX - DMAX / 2, HALF_REST, spring(t - T_SNAP, 24, 0.42))

def grow(t):
    if t < T_GROW: return 0.0
    return clamp(spring(t - T_GROW, 26, 0.38), 0, 1.25)

def half_hip(t, side):
    breathe = math.sin(t * 5.0) * 1.0
    ts = t - T_SNAP
    hop = -34 * math.sin(math.pi * clamp(ts / 0.32))
    times = L_TIMES if side < 0 else R_TIMES
    h = BF_HIP0 + hop + breathe + hit_bob(t, times, 7)
    if t >= T_GROW: h += 6 * math.exp(-(t - T_GROW) * 12) * math.sin((t - T_GROW) * 30)
    h += -4 * sstep((t - T_POSE) / 0.4)
    return h

def bf_state(t):
    s = {}
    breathe = math.sin(t * 5.0) * 2.0
    if t < T_SNAP:
        jolt = 0.0
        if t > T_GRAB: jolt = -12 * math.exp(-(t - T_GRAB) * 9) * math.sin(min((t - T_GRAB) * 25, math.pi))
        u = clamp((t - T_PULL) / (T_SNAP - T_PULL))
        d = DMAX * (0.25 * u + 0.75 * u ** 2.3) + 3.5 * math.sin(t * 95) * u ** 3
        e = EMAX * u ** 1.7
        xL, xR = CX - d / 2, CX + d / 2
        hip = BF_HIP0 + 0.06 * d + breathe * 0.5 + jolt
        s.update(snapped=False, d=d, e=e, xL=xL, xR=xR, hip=hip, hipL=hip, hipR=hip)
        s['neck'] = hip - TORSO; s['sy'] = s['neck'] + 12; s['head'] = s['neck'] - R - 7
        idleL = (CX - 62 + breathe * 0.3, hip + 4)
        if t < T_GRAB: GL = idleL
        elif t < T_PULL:
            uu = (t - T_GRAB) / (T_PULL - T_GRAB)
            GL = v_lerp(idleL, (CX - 150, s['sy'] + 16), ease_out(uu * 1.15))
        else:
            GL = (xL - 150 - e, s['sy'] + 16 + 4 * math.sin(t * 7))
        s['GL'] = GL; s['GR'] = (W - GL[0], GL[1])
        s['pinch'] = 0.6 * clamp(d / DMAX) ** 1.1 + 0.38 * sstep((t - (T_SNAP - 0.28)) / 0.28)
        fx = CX - 36 - 0.42 * d
        s['footL'] = fx; s['footR'] = W - fx
        s['glance'] = track([(0, 0), (0.6, 0), (0.75, -7), (1.3, -7), (1.55, 7), (2.0, 7), (2.2, 0)], t)
        return s
    ts = t - T_SNAP
    xL = half_x(t); xR = W - xL
    s.update(snapped=True, ts=ts, d=DMAX, e=EMAX, xL=xL, xR=xR)
    s['hipL'] = half_hip(t, -1); s['hipR'] = half_hip(t, 1)
    s['db'] = sstep((t - 2.88) / 0.3)
    fx0 = CX - 36 - 0.42 * DMAX
    o = lerp(10, 24, s['db'])
    s['footL'] = lerp(fx0, xL - o, sstep(ts / 0.32))
    s['footR'] = W - s['footL']
    s['glance'] = track([(11.4, 0), (11.6, 6), (12.4, 6), (12.6, 0)], t)
    s['GL'] = None; s['GR'] = None
    return s

def pose_u(t): return sstep((t - T_POSE) / 0.38)

def model_hand(t, kind, s, x, hip, held):
    """Hand of a model on side s. Returns (pos, pocket) where pocket=1 means the hand is hidden in a pocket."""
    hang = (x + s * 60, hip + 36)
    if kind == 'street': pk = (x - 48, hip + 8) if s < 0 else None   # skater: one hand in the jeans pocket, the other on the board
    else: pk = (x + s * 46, hip + 8)                                    # vintage: both hands in the jacket pockets
    u = pose_u(t)
    if pk is not None and u > 0: return v_lerp(hang, pk, u), u
    if held is None or t >= T_REL + 1.0: return hang, 0.0
    if t < T_REL: return held, 0.0
    return v_lerp(held, hang, clamp(spring(t - T_REL, 16, 0.55), 0, 1.15)), 0.0

# ---------------- puller ----------------
def gf_core(t):
    hx = track([(0, 205), (0.30, 205), (0.56, 330)], t)
    lean = track([(0, 0.02), (0.30, 0.0), (0.52, -0.55)], t)
    hy = track([(0, F - 200), (0.30, F - 200), (0.45, F - 182), (0.56, F - 172)], t)
    return hx, hy, lean

def post_track(ts): return track([(0, 0), (0.18, -42), (0.7, -18)], ts)
def post_lean(ts): return track([(0, 0.52), (0.14, 0.82), (0.75, 0.12)], ts)
def post_hy(ts): return track([(0, F - 162), (0.16, F - 150), (0.7, F - 192)], ts)
HX0 = CX - DMAX / 2 - 150 - EMAX - 82

RACK_DX = 117
SLOT_HOOK = [(100, -385), (70, -385), (40, -385), (62, -64), (126, -300), (126, -215)]
SLOT_GRAB = [(100, -340), (70, -340), (40, -340), (62, -64), (126, -288), (126, -190)]
SLAP_L = [(-0.30, 8, 44), (-0.30, 8, 44), (-0.45, 35, 50), (-1.0, 105, 80), (-0.35, 20, 44), (-0.18, -12, 46)]
SLAP_NECK = (-0.28, 4, 46)
GRAB_P = [(-0.20, 0, -30), (-0.20, 0, -30), (-0.20, 0, -30), (-0.75, 78, -34), (-0.22, 0, -28), (-0.22, 0, -28)]
REST_OFF = (20, 78)

def rack_x(t):
    if t < 3.0: return -320
    if t < T_SHOVE:
        x = track([(3.0, -320), (3.14, -78), (3.42, 5)], t, ease=lambda u: 1 - (1 - clamp(u)) ** 2)
        if t > 3.42: x += 9 * math.exp(-(t - 3.42) * 12) * math.sin((t - 3.42) * 32)
        return x
    return lerp(5, -360, ease_out((t - T_SHOVE) / 0.30) ** 1.4)

def face_at(t, times):
    if t < T_REL: return 1.0
    if t >= T_S3END: return track([(T_S3END, 1.0), (9.10, -1.0), (9.36, -1.0), (9.46, 1.0)], t)
    keys = [(T_REL, 1.0), (3.03, -1.0)]
    for i, tk in enumerate(times):
        keys += [(tk - 0.42, -1.0), (tk - 0.30, 1.0)]
        if i < len(times) - 1: keys += [(tk + 0.10, 1.0), (tk + 0.22, -1.0)]
    return track(keys, t)

def gf_hipx(t):
    if t < T_GRAB: return gf_core(t)[0]
    if t < T_SNAP:
        tgt = bf_state(t)['GL'][0] - 82 if t >= T_PULL else CX - 150 - 82
        return lerp(330, tgt, ease_out(clamp((t - T_GRAB) / 0.2)))
    if t < T_REL: return HX0 + post_track(t - T_SNAP)
    if t < T_S3END: return S3_BASE
    return S3_BASE - 14 * pulse(t, 9.08, T_SHOVE + 0.04, 9.42)

def foot_offsets(tt):
    if tt < T_GRAB: return (28, -30) if tt >= 0.3 else (20, -17)
    if tt < T_SNAP: return 72, -62
    return 50, -66

FRONT_A = [(0.34, 0.54), (1.10, 1.30), (1.85, 2.05), (2.60, 2.80)]
BACK_A = [(0.30, 0.44), (0.62, 0.78), (1.45, 1.65), (2.20, 2.38), (2.51, 2.67)]
FRONT_E = [(9.10, 9.22), (9.38, 9.50)]
BACK_E = [(9.12, 9.24), (9.40, 9.52)]

def foot_x2(t, steps, desired, x0, lift=26):
    x = x0
    for ts, te in steps:
        if t >= te: x = desired(te)
        elif t > ts:
            u = (t - ts) / (te - ts)
            return lerp(x, desired(te), sstep(u)), math.sin(math.pi * u) * lift
        else: break
    return x, 0.0

def gf_body(t, times, neck=False, phase=0.0):
    breathe = math.sin(t * 4.3 + phase) * 2
    if t < T_GRAB:
        hx, hy, lean = gf_core(t); hy += breathe * 0.4
    elif t < T_SNAP:
        hx = gf_hipx(t)
        u = clamp((t - T_GRAB) / (T_PULL - T_GRAB + 0.1))
        lean = lerp(-0.55, 0.36, ease_out(u))
        pu = clamp((t - T_PULL) / (T_SNAP - T_PULL))
        lean += 0.16 * pu + 0.025 * math.sin(t * 57 + phase) * pu
        hy = lerp(F - 172, F - 158, ease_out(u)) - 4 * pu
        hx += 2.5 * math.sin(t * 71 + phase) * pu
    elif t < T_REL:
        ts = t - T_SNAP
        hx = gf_hipx(t); lean = post_lean(ts); hy = post_hy(ts) + breathe * 0.4
    elif t < T_S3END:
        r = T_REL - T_SNAP
        hx = track([(T_REL, HX0 + post_track(r)), (3.12, 122), (3.42, S3_BASE)], t)
        lean = lerp(post_lean(r), 0.03, sstep((t - T_REL) / 0.15)) + track([(3.0, 0), (3.12, -0.32), (3.30, 0.30), (3.48, 0)], t)
        hy = lerp(post_hy(r), F - 197, sstep((t - T_REL) / 0.2)) + track([(3.0, 0), (3.12, 10), (3.30, 14), (3.48, 0)], t) + breathe * 0.4
        for i, tk in enumerate(times):
            gl, gd, gs = GRAB_P[i]
            pg = pulse(t, tk - 0.72, tk - 0.52, tk - 0.40)
            sl, sd, sx = SLAP_NECK if (neck == 'street' and i == 4) else SLAP_L[i]
            ps = pulse(t, tk - 0.30, tk - 0.02, tk + 0.22)
            lean += gl * pg + sl * ps; hy += gd * pg + sd * ps; hx += gs * pg + sx * ps
    else:
        hx = gf_hipx(t)
        lean = 0.03 - 0.34 * pulse(t, 9.08, T_SHOVE + 0.04, 9.42)               # shove the rack
        hy = F - 197 + breathe * 0.4
        cr = pulse(t, 9.44, T_CGRAB, T_YANK + 0.06)                              # crouch for the curtain hem
        lean += -0.62 * cr; hy += 46 * cr
        yk = pulse(t, T_YANK, T_YANK + 0.12, T_UP + 0.05)                        # yank: stretch tall + little hop
        lean += 0.10 * yk; hy -= 26 * yk
    return hx, hy, lean, face_at(t, times)

def frame_of(hx, hy, lean):
    up = (-math.sin(lean), -math.cos(lean))
    neck = v_add((hx, hy), v_mul(up, TORSO))
    sh = v_add(neck, v_mul(up, -12))
    head = v_add(neck, v_add(v_mul(up, R + 7), (R * 0.18, 0)))
    return neck, sh, head

def to_local(w, hx, face): return (hx + (w[0] - hx) * (1 if face >= 0 else -1), w[1])

def contact_world(i, tk, kind):
    cut = half_x(tk); hip = half_hip(tk, -1); sy = hip - TORSO + 12; headY = hip - TORSO - R - 7
    if i == 0 or (i == 1 and kind == 'lux'): return (cut - 46, (sy + hip) / 2)
    if i == 1: return (cut - 56, hip - 30)
    if i == 2: return (cut - 44, hip + 85)
    if i == 3: return (cut - 40, F - 26)
    if i == 4: return (cut - 26, sy - 4) if kind == 'street' else (cut - 56, hip + 6)
    return (cut - 26, headY - 18) if kind == 'street' else (cut - 34, sy + 8)

def curtain_y(t):
    """Bottom edge of the black roller curtains."""
    if t < T_YANK: return F - 4
    if t < T_YANK + 0.14: return lerp(F - 4, F - 470, sstep((t - T_YANK) / 0.14) ** 0.8)
    return lerp(F - 470, -160, ease_out((t - T_YANK - 0.14) / (T_UP - T_YANK - 0.14)))
CURT_GX = 64   # grab point in front of the stylist's hip

def off_at(kt, wpt, times, neck, phase):
    hx, hy, lean, face = gf_body(kt, times, neck, phase)
    _, sh, _ = frame_of(hx, hy, lean)
    return v_sub(to_local(wpt, hx, face), sh)

def ghold_world(t, times, neck, phase):
    hx, hy, lean, face = gf_body(t, times, neck, phase)
    _, sh, _ = frame_of(hx, hy, lean)
    half_sh = (half_x(t), half_hip(t, -1) - TORSO + 12)
    dv = v_sub(half_sh, sh); dl = max(v_len(dv), 1)
    Gp = v_add(sh, v_mul(dv, 138 / dl))
    G_pre = (CX - DMAX / 2 - 150 - EMAX, half_hip(t, -1) - TORSO + 28)
    return v_lerp(G_pre, Gp, sstep((t - T_SNAP) / 0.06))

def vtrack(keys, t):
    if t <= keys[0][0]: return keys[0][1]
    for (a0, p0), (a1, p1) in zip(keys, keys[1:]):
        if t <= a1: return v_lerp(p0, p1, sstep((t - a0) / max(a1 - a0, 1e-4)))
    return keys[-1][1]

def gf_state(t, bf, phase=0.0, times=L_TIMES, neck=False):
    s = {}
    hx, hy, lean, face = gf_body(t, times, neck, phase)
    neckp, sh, head = frame_of(hx, hy, lean)
    s.update(hip=(hx, hy), lean=lean, neck=neckp, sh=sh, head=head, face=face, fold=0.0, carry=None)
    hint_n = (-0.3, 1); hint_f = (-0.3, 1)
    if t < T_GRAB:
        reach = clamp((t - 0.36) / (T_GRAB - 0.36))
        G = v_lerp(v_add(s['hip'], (14, 4)), bf['GL'], ease_out(reach)); G2 = v_add(G, (-6, 6))
    elif t < T_SNAP:
        G = bf['GL']; G2 = v_add(G, (-6, 6))
    elif t < T_REL:
        G = ghold_world(t, times, neck, phase); G2 = v_add(G, (-6, 6))
    elif t < T_S3END:
        rest = v_add(sh, REST_OFF)
        if t < 3.03:
            Gh = ghold_world(T_REL - 1e-3, times, neck, phase)
            G = v_lerp(Gh, rest, sstep((t - T_REL) / 0.08))
        elif t < 3.12:
            post = (rack_x(3.12) + RACK_DX, F - 250)
            G = v_lerp(rest, v_add(sh, off_at(3.12, post, times, neck, phase)), sstep((t - 3.03) / 0.09))
        elif t < 3.50:
            G = to_local((rack_x(t) + RACK_DX, F - 250), hx, face)
        else:
            keys = [(3.50, off_at(3.50, (rack_x(3.5) + RACK_DX, F - 250), times, neck, phase)), (3.62, REST_OFF)]
            for i, tk in enumerate(times):
                slot = (5 + SLOT_GRAB[i][0], F + SLOT_GRAB[i][1])
                keys += [(tk - 0.68, REST_OFF), (tk - 0.52, off_at(tk - 0.52, slot, times, neck, phase)),
                         (tk - 0.42, REST_OFF), (tk - 0.30, REST_OFF),
                         (tk, off_at(tk, contact_world(i, tk, neck), times, neck, phase)), (tk + 0.20, REST_OFF)]
            G = v_add(sh, vtrack(keys, t))
        if 3.12 <= t < 3.50: G2 = v_add(G, (5, 36))
        else: G2 = v_add(sh, (-8, 86))
        for i, tk in enumerate(times):
            if tk - 0.52 <= t < tk - 0.07: s['carry'] = i
    else:
        rest = v_add(sh, REST_OFF)
        G, G2 = rest, v_add(sh, (-8, 86))
        post = to_local((rack_x(min(t, T_SHOVE + 0.07)) + RACK_DX, F - 250), hx, face)
        G = v_lerp(G, post, pulse(t, 9.06, T_SHOVE, 9.40))
        bar = (hx + CURT_GX, curtain_y(t) - 6)
        if t < T_YANK + 0.16:
            G = v_lerp(G, bar, sstep((t - 9.46) / (T_CGRAB - 9.46)))
        else:
            G = v_lerp(v_add(sh, (40, -150)), rest, sstep((t - T_UP + 0.1) / 0.2))
            hint_n = (0.4, -0.2)
    s['G'] = G; s['G2'] = G2; s['hint_n'] = hint_n; s['hint_f'] = hint_f
    # feet (local coords)
    des_f = lambda tt: gf_hipx(tt) + foot_offsets(tt)[0]
    des_b = lambda tt: gf_hipx(tt) + foot_offsets(tt)[1]
    if t < T_REL:
        s['footF'] = foot_x(t, FRONT_A, des_f); s['footB'] = foot_x(t, BACK_A, des_b)
    elif t < T_S3END:
        wf = foot_x(T_REL, FRONT_A, des_f)[0]; wb = foot_x(T_REL, BACK_A, des_b)[0]
        u = sstep((t - T_REL) / 0.1)
        lift = 18 * (1 - abs(face))
        s['footF'] = (lerp(wf, hx + 30, u), lift); s['footB'] = (lerp(wb, hx - 30, u), lift * 0.6)
    else:
        b0 = gf_body(T_S3END, times, neck, phase)[0]
        s['footF'] = foot_x2(t, FRONT_E, des_f, b0 + 30); s['footB'] = foot_x2(t, BACK_E, des_b, b0 - 30)
    return s

def mirror_state(s):
    m = dict(s)
    for k in ('hip', 'neck', 'sh', 'head', 'G', 'G2'):
        m[k] = (W - s[k][0], s[k][1])
    for k in ('footF', 'footB'):
        m[k] = (W - s[k][0], s[k][1])
    m['hint_n'] = (-s['hint_n'][0], s['hint_n'][1]); m['hint_f'] = (-s['hint_f'][0], s['hint_f'][1])
    return m

def eff_face(f): return f if abs(f) >= 0.14 else (0.14 if f >= 0 else -0.14)
def hand_world(s, key='G'):
    hx = s['hip'][0]; f = eff_face(s['face'])
    return (hx + (s[key][0] - hx) * f, s[key][1])

# ---------------- primitives ----------------
OUT_COL = skia.Color4f(0.015, 0.015, 0.02, 1)
def col(v, a=1.0): return skia.Color4f(v, v, v, a)
def rgb(r, g, b, a=1.0): return skia.Color4f(r, g, b, a)
def paint_stroke(w, c):
    p = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=w, Color4f=c)
    p.setStrokeCap(skia.Paint.kRound_Cap); p.setStrokeJoin(skia.Paint.kRound_Join); return p
def paint_fill(c): return skia.Paint(AntiAlias=True, Style=skia.Paint.kFill_Style, Color4f=c)
def polyline(pts):
    path = skia.Path(); path.moveTo(*pts[0])
    for p in pts[1:]: path.lineTo(*p)
    return path
def polygon(pts):
    p = polyline(pts); p.close(); return p

def chain(cv, pts, w, c, gloss=True):
    path = polyline(pts)
    cv.drawPath(path, paint_stroke(w + OUTL, OUT_COL))
    cv.drawPath(path, paint_stroke(w, c))
    if gloss:
        o = -w * 0.17
        cv.drawPath(polyline([(p[0] + o, p[1] + o) for p in pts]), paint_stroke(w * 0.28, skia.Color4f(1, 1, 1, 0.42)))

def shape(cv, path, c, rim=0.0):
    cv.drawPath(path, paint_stroke(OUTL, OUT_COL))
    cv.drawPath(path, paint_fill(c))
    if rim > 0:
        cv.save(); cv.clipPath(path, doAntiAlias=True)
        cv.drawPath(path, paint_stroke(5, skia.Color4f(1, 1, 1, rim)))
        cv.restore()

def circle_path(c, r):
    p = skia.Path(); p.addCircle(c[0], c[1], r); return p

def leg_profile(hip, foot, dirx, lift):
    ankle = (foot[0], F - SW / 2 - 4 - lift)
    knee, ankle = ik(hip, ankle, THIGH, SHIN, (dirx, -0.2))
    return [hip, knee, ankle, (ankle[0] + dirx * FOOT, ankle[1] + (2 if lift < 1 else -3))]

def arm(sh, hand, hint, l1=UA, l2=FA):
    el, h = ik(sh, hand, l1, l2, hint); return [sh, el, h]

def draw_ponytail(cv, head, hist, dirx, shade):
    vx = (head[0] - hist[0]) / 0.07
    swing = clamp(-vx * 0.0016 * dirx, -0.9, 0.9)
    base = v_add(head, (-dirx * R * 0.55, -R * 0.55))
    ang = (math.pi - 0.6 + swing) if dirx > 0 else (0.6 - swing)
    L = 66
    p1 = v_add(base, (math.cos(ang - 0.5 * dirx) * L * 0.45, math.sin(ang - 0.5 * dirx) * L * 0.45 - 6))
    p2 = v_add(base, (math.cos(ang) * L, math.sin(ang) * L + 18))
    tip = v_add(p2, (-dirx * 6, 22))
    pts = []
    for i in range(17):
        u = i / 16; a = (1-u)**3; b = 3*(1-u)**2*u; c = 3*(1-u)*u*u; d = u**3
        pts.append((a*base[0]+b*p1[0]+c*p2[0]+d*tip[0], a*base[1]+b*p1[1]+c*p2[1]+d*tip[1]))
    left, right = [], []
    for i, p in enumerate(pts):
        q = pts[min(i+1, 16)]; o = pts[max(i-1, 0)]
        tx, ty = q[0]-o[0], q[1]-o[1]; l = math.hypot(tx, ty) or 1
        nx, ny = -ty/l, tx/l; wdt = 13 * (1 - i/16) ** 0.8 + 2.5
        left.append((p[0]+nx*wdt, p[1]+ny*wdt)); right.append((p[0]-nx*wdt, p[1]-ny*wdt))
    shape(cv, polygon(left + right[::-1]), col(shade * 0.92))

def fold_arm(sh, pts, dirx, fe, far):
    if fe <= 0: return pts
    el = v_add(sh, (dirx * (34 if far else 28), 60 if far else 64))
    hd = v_add(sh, (dirx * (-8 if far else 2), 50 if far else 56))
    return [v_lerp(a, b, fe) for a, b in zip(pts, [sh, el, hd])]

def draw_profile(cv, s, dirx, shade, accessory, hist):
    near = col(shade); far = col(shade * 0.72)
    hip, sh, head = s['hip'], s['sh'], s['head']
    fe = s.get('fold', 0.0)
    f = eff_face(s.get('face', 1.0))
    cv.save(); cv.translate(hip[0], 0); cv.scale(f, 1); cv.translate(-hip[0], 0)
    chain(cv, leg_profile(hip, (s['footB'][0], 0), dirx, s['footB'][1]), SW, far)
    chain(cv, fold_arm(sh, arm(sh, s['G2'], s['hint_f']), dirx, fe, True), SW, far)
    if accessory == 'pony': draw_ponytail(cv, head, hist, dirx, shade)
    chain(cv, [hip, s['neck']], TW, near)
    shape(cv, circle_path(head, R), near)
    if accessory == 'cap':
        r2 = R + 3; cap = skia.Path()
        cap.addArc(skia.Rect.MakeXYWH(head[0]-r2, head[1]-r2, 2*r2, 2*r2), 180, 180); cap.close()
        shape(cv, cap, col(shade * 0.42), rim=0.25)
        chain(cv, [(head[0] + dirx * R * 0.3, head[1] - 3), (head[0] + dirx * (R + 24), head[1] + 1)], 10, col(shade * 0.42), gloss=False)
    chain(cv, leg_profile(hip, (s['footF'][0], 0), dirx, s['footF'][1]), SW, near)
    chain(cv, fold_arm(sh, arm(sh, s['G'], s['hint_n']), dirx, fe, False), SW, near)
    cv.restore()

def capsule_v(x, y0, y1, w):
    p = skia.Path(); p.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(x - w/2, y0 - w/2, x + w/2, y1 + w/2), w/2, w/2)); return p

def taffy(xL, xR, y0, y1, pinch_px, kind):
    if kind == 'head':
        a = circle_path((xL, y0), R); b = circle_path((xR, y0), R); top, bot = y0 - R, y0 + R
    else:
        a = capsule_v(xL, y0, y1, TW); b = capsule_v(xR, y0, y1, TW); top, bot = y0 - TW/2 + 6, y1 + TW/2 - 6
    p = skia.Op(a, b, skia.PathOp.kUnion_PathOp)
    if xR - xL > 1:
        dx = xR - xL; br = skia.Path(); br.moveTo(xL, top)
        br.cubicTo(xL + dx*0.33, top + pinch_px*1.33, xL + dx*0.67, top + pinch_px*1.33, xR, top)
        br.lineTo(xR, bot)
        br.cubicTo(xL + dx*0.67, bot - pinch_px*1.33, xL + dx*0.33, bot - pinch_px*1.33, xL, bot); br.close()
        p = skia.Op(p, br, skia.PathOp.kUnion_PathOp)
    return p

def half_piece(x, y0, y1, side, stub, kind):
    if kind == 'head':
        full = circle_path((x, y0), R); top, bot = y0 - R, y0 + R; mid = y0
    else:
        full = capsule_v(x, y0, y1, TW); top, bot = y0 - TW/2, y1 + TW/2; mid = (y0 + y1) / 2
    clip = skia.Path()
    if side < 0: clip.addRect(skia.Rect.MakeLTRB(x - 200, top - 50, x, bot + 50))
    else: clip.addRect(skia.Rect.MakeLTRB(x, top - 50, x + 200, bot + 50))
    p = skia.Op(full, clip, skia.PathOp.kIntersect_PathOp)
    if abs(stub) > 1.5:
        tip = x - side * stub; h = bot - top; tg = skia.Path()
        tg.moveTo(x, top + 2)
        tg.cubicTo(lerp(x, tip, 0.5), top + h*0.30, tip, mid - 4, tip, mid)
        tg.cubicTo(tip, mid + 4, lerp(x, tip, 0.5), bot - h*0.30, x, bot - 2); tg.close()
        p = skia.Op(p, tg, skia.PathOp.kUnion_PathOp)
    return p

def rubber_arm(sh, hand, side, base_len=UA + FA):
    dist = v_len(v_sub(hand, sh))
    if dist < base_len - 2: return arm(sh, hand, (side * 0.6, 1)), SW
    return [sh, hand], SW * clamp((base_len / dist) ** 0.75, 0.45, 1)

# ---------------- clothes ----------------
def c4(c, a=None):
    return skia.Color4f(c.fR, c.fG, c.fB, c.fA if a is None else a)

def smooth_path(pts, closed=True, k=1.0, skip=None):
    """Catmull-Rom through points. A point given as (x, y, 1) is a sharp corner.
    skip(i) -> True leaves segment i out (used to drop the seam edge from outlines)."""
    P = [(p[0], p[1]) for p in pts]; sharp = [len(p) > 2 for p in pts]; n = len(P)
    path = skia.Path(); path.moveTo(*P[0])
    segs = n if closed else n - 1
    for i in range(segs):
        if skip is not None and skip(i):
            path.moveTo(*P[(i + 1) % n]); continue
        p0 = P[(i - 1) % n] if (closed or i > 0) else P[i]
        p1 = P[i]; p2 = P[(i + 1) % n]
        p3 = P[(i + 2) % n] if (closed or i + 2 < n) else p2
        if sharp[i]: c1 = (p1[0] + (p2[0] - p1[0]) / 3, p1[1] + (p2[1] - p1[1]) / 3)
        else: c1 = (p1[0] + (p2[0] - p0[0]) / 6 * k, p1[1] + (p2[1] - p0[1]) / 6 * k)
        if sharp[(i + 1) % n]: c2 = (p2[0] - (p2[0] - p1[0]) / 3, p2[1] - (p2[1] - p1[1]) / 3)
        else: c2 = (p2[0] - (p3[0] - p1[0]) / 6 * k, p2[1] - (p3[1] - p1[1]) / 6 * k)
        path.cubicTo(c1[0], c1[1], c2[0], c2[1], p2[0], p2[1])
    if closed and skip is None: path.close()
    return path

def sample_curve(pts, n=24):
    """Points along a smooth open Catmull-Rom curve."""
    P = [(p[0], p[1]) for p in pts]; out = []; m = len(P)
    if m == 2: return [v_lerp(P[0], P[1], i / (n - 1)) for i in range(n)]
    for i in range(m - 1):
        p0 = P[max(i - 1, 0)]; p1 = P[i]; p2 = P[i + 1]; p3 = P[min(i + 2, m - 1)]
        steps = max(2, n // (m - 1))
        for j in range(steps):
            u = j / steps; u2 = u * u; u3 = u2 * u
            out.append(tuple(0.5 * ((2 * p1[d]) + (-p0[d] + p2[d]) * u + (2 * p0[d] - 5 * p1[d] + 4 * p2[d] - p3[d]) * u2
                                    + (-p0[d] + 3 * p1[d] - 3 * p2[d] + p3[d]) * u3) for d in (0, 1)))
    out.append(P[-1]); return out

CL = dict(rec=None, soft=False, base=None, caps=None)   # garment merge: record body paths / cut sleeve outlines / draw seams


def cloth(cv, pts, base, side, x, acc, shade=0.42, white=None, rim_from=12, smooth=True, light=0.10):
    path = smooth_path(pts) if smooth else polygon([(p[0], p[1]) for p in pts])
    n_ = len(pts)
    on_seam = [side != 0 and abs(p[0] - x) < 0.6 for p in pts]
    if any(on_seam[i] and on_seam[(i + 1) % n_] for i in range(n_)):
        sk = lambda i: on_seam[i] and on_seam[(i + 1) % n_]
        if smooth: opath = smooth_path(pts, skip=sk)
        else:
            opath = skia.Path(); opath.moveTo(*pts[0][:2])
            for i in range(n_):
                q = pts[(i + 1) % n_]
                if sk(i): opath.moveTo(q[0], q[1])
                else: opath.lineTo(q[0], q[1])
    else: opath = path
    if CL['soft']:                     # inside one garment: NO line between parts — it is one piece of fabric
        pass
    else:
        cv.drawPath(opath, paint_stroke(OUTL, OUT_COL))
    if CL['rec'] is not None and white is None:
        CL['rec'].append(path)
        b_ = path.computeTightBounds(); ar = b_.width() * b_.height()
        if CL['base'] is None or ar > CL['base'][1]: CL['base'] = (base, ar)   # main fabric = biggest piece
    if white is not None:
        cv.drawPath(path, paint_fill(white)); return path
    cv.drawPath(path, paint_fill(base))
    b = path.computeTightBounds()
    cv.save(); cv.clipPath(path, doAntiAlias=True)
    sp = skia.Paint(AntiAlias=True)
    if side != 0 and not CL['soft']:   # darker toward the outer edge and the bottom
        sp.setShader(skia.GradientShader.MakeLinear([(x + side * 6, 0), (x + side * 70, 0)],
                     [skia.Color4f(0, 0, 0, 0).toColor(), skia.Color4f(0, 0, 0, shade).toColor()]))
        cv.drawRect(b.makeOutset(20, 20), sp)
    sp2 = skia.Paint(AntiAlias=True)
    sp2.setShader(skia.GradientShader.MakeLinear([(0, b.top()), (0, b.bottom())],
                  [skia.Color4f(1, 1, 1, light).toColor(), skia.Color4f(1, 1, 1, 0).toColor(), skia.Color4f(0, 0, 0, shade * 0.6).toColor()],
                  [0.0, 0.35, 1.0]))
    cv.drawRect(b.makeOutset(20, 20), sp2)
    if acc is not None and not CL['soft']:   # colored rim light on the outer edge only
        if side != 0:
            cv.save()
            r = skia.Rect.MakeLTRB(x + rim_from, b.top() - 40, b.right() + 40, b.bottom() + 40) if side > 0 else \
                skia.Rect.MakeLTRB(b.left() - 40, b.top() - 40, x - rim_from, b.bottom() + 40)
            cv.clipRect(r)
        cv.drawPath(path, paint_stroke(9, skia.Color4f(*acc, 0.30)))
        cv.drawPath(path, paint_stroke(4, skia.Color4f(*acc, 0.95)))
        if side != 0: cv.restore()
    cv.restore()
    return path

def fold(cv, pts, w, c, hi=None, hi_off=(1.6, -1.6)):
    """Tapered fold line (thick in the middle, pointed ends) with optional highlight beside it."""
    S = sample_curve(pts, 20); n = len(S); L, Rr = [], []
    for i, p in enumerate(S):
        q = S[min(i + 1, n - 1)]; o = S[max(i - 1, 0)]
        tx, ty = q[0] - o[0], q[1] - o[1]; l = math.hypot(tx, ty) or 1
        nx, ny = -ty / l, tx / l; u = i / (n - 1)
        wd = w * 0.5 * (math.sin(math.pi * u) ** 0.8) + 0.25
        L.append((p[0] + nx * wd, p[1] + ny * wd)); Rr.append((p[0] - nx * wd, p[1] - ny * wd))
    if hi is not None:
        cv.drawPath(polygon([(p[0] + hi_off[0], p[1] + hi_off[1]) for p in L + Rr[::-1]]), paint_fill(hi))
    cv.drawPath(polygon(L + Rr[::-1]), paint_fill(c))

def tube_outline(pts, w0, w1, bulge=0.0):
    S = sample_curve(pts, 26); n = len(S); L, Rr = [], []
    for i, p in enumerate(S):
        q = S[min(i + 1, n - 1)]; o = S[max(i - 1, 0)]
        tx, ty = q[0] - o[0], q[1] - o[1]; l = math.hypot(tx, ty) or 1
        nx, ny = -ty / l, tx / l; u = i / (n - 1)
        wd = (lerp(w0, w1, u) + bulge * math.sin(math.pi * u)) / 2
        L.append((p[0] + nx * wd, p[1] + ny * wd)); Rr.append((p[0] - nx * wd, p[1] - ny * wd))
    return L + Rr[::-1], S

def frame_at(S, u):
    i = min(int(u * (len(S) - 1)), len(S) - 2)
    p = S[i]; q = S[i + 1]; tx, ty = q[0] - p[0], q[1] - p[1]; l = math.hypot(tx, ty) or 1
    return p, (tx / l, ty / l), (-ty / l, tx / l)

def ribs(cv, a0, a1, b0, b1, n, c, w=1.4):
    """Vertical rib lines across a band: a0->a1 is the top edge, b0->b1 the bottom edge."""
    for i in range(1, n):
        u = i / n
        cv.drawLine(*v_lerp(a0, a1, u), *v_lerp(b0, b1, u), paint_stroke(w, c))

def braid(cv, center, amp, per, dark, light, w=3.2):
    """Cable-knit braid along a polyline of samples."""
    tot = sum(v_len(v_sub(center[i + 1], center[i])) for i in range(len(center) - 1))
    cells = max(1, int(tot / per))
    def at(s):
        acc_ = 0.0
        for i in range(len(center) - 1):
            seg = v_len(v_sub(center[i + 1], center[i]))
            if acc_ + seg >= s or i == len(center) - 2:
                u = clamp((s - acc_) / (seg or 1)); p = v_lerp(center[i], center[i + 1], u)
                d = v_sub(center[i + 1], center[i]); l = v_len(d) or 1
                return p, (-d[1] / l, d[0] / l)
            acc_ += seg
    for k in range(cells):
        s0 = k * per + (tot - cells * per) / 2; s1 = s0 + per
        p0, n0 = at(s0); p1, n1 = at(s1); pm, nm = at((s0 + s1) / 2)
        a = v_add(p0, v_mul(n0, amp)); b = v_sub(p1, v_mul(n1, amp))
        c_ = v_sub(p0, v_mul(n0, amp)); d = v_add(p1, v_mul(n1, amp))
        # under strand (broken in the middle)
        for seg in ((c_, v_lerp(c_, d, 0.36)), (v_lerp(c_, d, 0.64), d)):
            cv.drawLine(*seg[0], *seg[1], paint_stroke(w + 2.2, dark)); cv.drawLine(*seg[0], *seg[1], paint_stroke(w, light))
        mid = v_add(pm, v_mul(nm, 0))
        path = smooth_path([a, mid, b], closed=False)
        cv.drawPath(path, paint_stroke(w + 2.2, dark)); cv.drawPath(path, paint_stroke(w, light))


# ---------------- garments (full models) ----------------
ACC_ST = (1.00, 0.30, 0.72)   # skater accent (neon pink, like the skate-park neon)
ACC_OM = (1.00, 0.70, 0.32)   # vintage accent (warm lamp amber)
GLOW_L = (1.00, 0.22, 0.74)   # glow around the finished fits
GLOW_R = (1.00, 0.66, 0.26)

# streetwear
HOOD = rgb(0.44, 0.13, 0.19); HOOD_D = rgb(0.24, 0.06, 0.10); HOOD_L = rgb(0.60, 0.26, 0.31); HOOD_W = rgb(0.66, 0.36, 0.40)
JEAN = rgb(0.58, 0.69, 0.82); JEAN_D = rgb(0.36, 0.46, 0.61); JEAN_L = rgb(0.78, 0.86, 0.94); STITCH = rgb(0.86, 0.66, 0.38)
SNK = rgb(0.96, 0.96, 0.97); SNK_G = rgb(0.62, 0.63, 0.66); SNK_GD = rgb(0.42, 0.43, 0.46)
CAP = rgb(0.08, 0.08, 0.09); CAP_L = rgb(0.22, 0.22, 0.24)
SILV = rgb(0.80, 0.82, 0.86); SILV_D = rgb(0.48, 0.50, 0.55); SILV_L = rgb(0.96, 0.97, 0.99); CUSH = rgb(0.16, 0.16, 0.18)
BAG = rgb(0.08, 0.08, 0.09); BAG_L = rgb(0.22, 0.22, 0.24); STRAP = rgb(0.14, 0.14, 0.15)
TEEW = rgb(0.95, 0.95, 0.96)
# old money
SHIRT = rgb(0.97, 0.97, 0.98); SHIRT_D = rgb(0.74, 0.77, 0.82)
KNIT = rgb(0.93, 0.89, 0.80); KNIT_D = rgb(0.72, 0.66, 0.54); KNIT_L = rgb(0.99, 0.97, 0.91)
NAVY = rgb(0.10, 0.13, 0.26); NAVY_D = rgb(0.04, 0.05, 0.12); NAVY_L = rgb(0.22, 0.28, 0.46)
TROU = rgb(0.84, 0.78, 0.66); TROU_D = rgb(0.64, 0.58, 0.46); TROU_L = rgb(0.93, 0.89, 0.80)
LOAF = rgb(0.25, 0.14, 0.08); LOAF_D = rgb(0.10, 0.05, 0.03); LOAF_L = rgb(0.52, 0.34, 0.22)
DIAL = rgb(0.06, 0.09, 0.20)

def blob(cv, c, r, col_):
    p = paint_fill(col_); p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, r * 0.45))
    cv.drawCircle(c[0], c[1], r, p)

# ---- streetwear ----
def g_hoodie(P, side, N, sy, H):
    def f(cv, side_, x, acc, white):
        cloth(cv, [P(0, H + 22, 1), P(46, H + 22), P(47, H + 35, 1), P(24, H + 37), P(0, H + 38, 1)], TEEW, side, x, acc, 0.25, white)
        hood = [P(0, N - 17, 1), P(16, N - 23), P(34, N - 13), P(42, N + 4), P(33, N + 16), P(14, N + 14), P(0, N + 12, 1)]
        hp_ = cloth(cv, hood, HOOD, side, x, acc, 0.32, white, light=0.18)
        if white is None:
            cv.save(); cv.clipPath(hp_, doAntiAlias=True)
            fold(cv, [P(4, N - 6), P(18, N - 10), P(31, N - 2)], 3.6, HOOD_D)
            fold(cv, [P(10, N + 3), P(24, N + 5), P(35, N + 10)], 2.4, c4(HOOD_L, 0.9))
            cv.restore()
        pts = [P(0, N + 9, 1), P(18, N + 5), P(34, N + 9), P(49, sy + 16), P(52, sy + 44), P(49, H + 6), P(50, H + 30),
               P(48, H + 31, 1), P(0, H + 31, 1)]
        path = cloth(cv, pts, HOOD, side, x, acc, 0.36, white, light=0.12)
        if white is not None: return
        cv.save(); cv.clipPath(path, doAntiAlias=True)
        for c_, r_ in (((24, sy + 30), 16), ((12, H - 50), 12), ((38, H - 6), 14)):   # washed, faded patches
            blob(cv, P(*c_), r_, c4(HOOD_W, 0.35))
        pk = [P(0, H - 42, 1), P(24, H - 42), P(38, H - 6), P(38, H + 14, 1), P(0, H + 14, 1)]
        cv.drawPath(smooth_path(pk, closed=False), paint_stroke(2.6, HOOD_D))
        fold(cv, [P(24, H - 41), P(31, H - 24), P(37, H - 7)], 3.8, HOOD_D, HOOD_L)
        fold(cv, [P(6, H - 30), P(16, H - 20), P(20, H - 4)], 2.4, c4(HOOD_L, 0.8))
        fold(cv, [P(46, sy + 26), P(36, sy + 44), P(30, sy + 66)], 3.6, HOOD_D, HOOD_L)
        fold(cv, [P(28, sy + 16), P(22, sy + 32)], 2.6, HOOD_D)
        fold(cv, [P(43, H - 26), P(46, H - 10), P(44, H + 6)], 2.6, HOOD_D)
        cv.drawPath(polyline([P(0, H + 17), P(50, H + 17)]), paint_stroke(2.6, HOOD_D))
        ribs(cv, P(0, H + 18), P(50, H + 18), P(0, H + 31), P(48, H + 31), 14, c4(HOOD_D, 0.8), 1.5)
        cv.restore()
        cv.drawPath(smooth_path([P(0, N + 12), P(12, N + 9), P(24, N + 9)], closed=False), paint_stroke(3, HOOD_D))
        a, b, c_ = P(7, N + 13), P(9, sy + 30), P(8, sy + 52)
        pth = smooth_path([a, b, c_], closed=False)
        cv.drawPath(pth, paint_stroke(5.5, OUT_COL)); cv.drawPath(pth, paint_stroke(3.2, TEEW))
        cv.drawLine(*c_, c_[0], c_[1] + 7, paint_stroke(6.5, OUT_COL)); cv.drawLine(*c_, c_[0], c_[1] + 7, paint_stroke(4.2, SILV))
    return f

def g_hoodie_sleeve(S, E, cuff0, Hd):
    def f(cv, side, x, acc, white):
        fv = v_sub(Hd, cuff0); l = v_len(fv) or 1; fu = (fv[0] / l, fv[1] / l)
        wrist = v_add(cuff0, v_mul(fu, 2))
        pts, C = tube_outline([v_add(S, (0, -4)), E, wrist], 46, 40, 5)
        path = cloth(cv, pts, HOOD, side, x, acc, 0.36, white, rim_from=-999, smooth=False, light=0.12)
        cpts, CC = tube_outline([v_sub(wrist, v_mul(fu, 2)), v_add(wrist, v_mul(fu, 11))], 31, 29)
        cloth(cv, cpts, HOOD, side, x, None, 0.3, white, rim_from=-999, smooth=False)
        if white is not None: return
        cv.save(); cv.clipPath(path, doAntiAlias=True)
        p, t_, n_ = frame_at(C, 0.3); blob(cv, p, 13, c4(HOOD_W, 0.3))
        for u, k in ((0.42, 1), (0.52, -1), (0.70, 1), (0.80, -1), (0.88, 1)):
            p, t_, n_ = frame_at(C, u)
            fold(cv, [v_add(p, v_mul(n_, -16 * k)), v_add(v_add(p, v_mul(t_, 4)), v_mul(n_, 2 * k)), v_add(v_add(p, v_mul(t_, -2)), v_mul(n_, 17 * k))],
                 2.8, HOOD_D, c4(HOOD_L, 0.8) if u > 0.6 else None)
        p, t_, n_ = frame_at(C, 0.16)
        fold(cv, [v_add(p, v_mul(n_, 14)), v_add(v_add(p, v_mul(t_, 18)), v_mul(n_, 6))], 2.6, HOOD_D)
        cv.restore()
        cv.save(); cv.clipPath(polygon(cpts), doAntiAlias=True)
        n_ = (-fu[1], fu[0])
        ribs(cv, v_add(CC[0], v_mul(n_, 16)), v_sub(CC[0], v_mul(n_, 16)), v_add(CC[-1], v_mul(n_, 16)), v_sub(CC[-1], v_mul(n_, 16)), 8, c4(HOOD_D, 0.8), 1.4)
        cv.restore()
    return f

def g_jeans(P, side, H, F_):
    def f(cv, side_, x, acc, white):
        pts = [P(0, H - 8, 1), P(40, H - 8, 1), P(48, H + 40), P(55, H + 110), P(58, F_ - 34), P(57, F_ - 20, 1),
               P(2, F_ - 20, 1), P(4, H + 84), P(2, H + 60), P(0, H + 52, 1)]
        path = cloth(cv, pts, JEAN, side, x, acc, 0.30, white, light=0.16)
        if white is not None: return
        cv.save(); cv.clipPath(path, doAntiAlias=True)
        blob(cv, P(26, H + 36), 18, c4(JEAN_L, 0.55)); blob(cv, P(30, H + 112), 16, c4(JEAN_L, 0.5))   # faded thigh + knee
        cv.drawPath(polyline([P(0, H + 3), P(42, H + 3)]), paint_stroke(2.4, JEAN_D))                        # waistband
        cv.drawPath(polyline([P(0, H + 6), P(42, H + 6)]), paint_stroke(1.1, STITCH))
        cv.drawPath(polyline([P(30, H - 8), P(30, H + 4)]), paint_stroke(4.5, JEAN_D))                       # belt loop
        cv.drawPath(smooth_path([P(26, H + 4), P(32, H + 18), P(44, H + 22)], closed=False), paint_stroke(2.2, JEAN_D))   # front pocket
        cv.drawPath(smooth_path([P(27, H + 7), P(33, H + 20), P(44, H + 25)], closed=False), paint_stroke(1.0, STITCH))
        cv.drawPath(smooth_path([P(46, H + 8), P(52, H + 70), P(56, F_ - 26)], closed=False), paint_stroke(1.2, STITCH))  # side seam
        for k in range(3):   # whiskers
            fold(cv, [P(4 + k * 3, H + 22 + k * 7), P(14 + k * 3, H + 24 + k * 6)], 2.2, c4(JEAN_L, 0.85))
        fold(cv, [P(8, H + 120), P(24, H + 128), P(40, H + 124)], 2.6, JEAN_D, JEAN_L)
        for yy, dx in ((F_ - 70, 0), (F_ - 56, 6), (F_ - 42, -4), (F_ - 30, 4)):   # stacking at the ankle
            fold(cv, [P(6, yy + 4), P(24 + dx, yy - 3), P(52, yy + 5)], 3.0, JEAN_D, JEAN_L)
        cv.drawPath(polyline([P(2, F_ - 23), P(57, F_ - 23)]), paint_stroke(1.0, STITCH))
        cv.restore()
        cv.drawCircle(*P(2, H - 2), 3.4, paint_fill(rgb(0.72, 0.52, 0.28)))    # button
    return f

def g_sneaker(P, side, F_):
    def f(cv, side_, x, acc, white):
        sole = [P(1, F_ - 15, 1), P(62, F_ - 14), P(67, F_ - 8), P(65, F_, 1), P(1, F_, 1)]
        up = [P(3, F_ - 36), P(20, F_ - 40), P(36, F_ - 34), P(52, F_ - 24), P(64, F_ - 17), P(63, F_ - 13, 1), P(2, F_ - 13, 1)]
        path = cloth(cv, up, SNK, side, x, acc, 0.22, white, light=0.2)
        if white is None:
            cv.save(); cv.clipPath(path, doAntiAlias=True)
            cloth(cv, [P(40, F_ - 28), P(52, F_ - 22), P(62, F_ - 15), P(60, F_ - 12, 1), P(38, F_ - 12, 1), P(36, F_ - 20)], SNK_G, side, x, None, 0.15, None)
            cloth(cv, [P(0, F_ - 32, 1), P(10, F_ - 33), P(12, F_ - 14, 1), P(0, F_ - 14, 1)], SNK_G, side, x, None, 0.15, None)
            cv.drawPath(smooth_path([P(12, F_ - 17), P(24, F_ - 21), P(36, F_ - 30)], closed=False), paint_stroke(6.5, SNK_GD))
            for k in range(3):
                cv.drawLine(*P(22 + k * 7, F_ - 37 + k * 2), *P(27 + k * 7, F_ - 33 + k * 2), paint_stroke(2.6, SNK_GD))
            cv.restore()
        cloth(cv, [P(0, F_ - 41, 1), P(9, F_ - 44), P(13, F_ - 36), P(3, F_ - 33, 1)], SNK_G, side, x, None, 0.1, white, light=0.3)
        sp_ = cloth(cv, sole, SNK, side, x, acc, 0.12, white, light=0.0)
        if white is None:
            cv.save(); cv.clipPath(sp_, doAntiAlias=True)
            cv.drawPath(polyline([P(1, F_ - 7), P(66, F_ - 6)]), paint_stroke(1.8, SNK_G))
            for k in range(9): cv.drawLine(*P(5 + k * 7, F_ - 1), *P(5 + k * 7, F_ - 4), paint_stroke(1.6, SNK_G))
            cv.restore()
    return f

def g_headphones(P, side, N):
    def f(cv, side_, x, acc, white):
        band = smooth_path([P(0, N + 24), P(14, N + 20), P(27, N + 3)], closed=False)
        cv.drawPath(band, paint_stroke(8 + OUTL, OUT_COL)); cv.drawPath(band, paint_stroke(8, white or SILV))
        if white is None: cv.drawPath(band, paint_stroke(2.4, SILV_L))
        cup = [P(18, N - 10), P(34, N - 13), P(43, N + 2), P(39, N + 18), P(25, N + 21), P(17, N + 6)]
        path = cloth(cv, cup, SILV, side, x, acc, 0.3, white, rim_from=20, light=0.3)
        if white is not None: return
        cloth(cv, [P(16, N - 6), P(22, N - 9), P(24, N + 6), P(20, N + 16), P(15, N + 10)], CUSH, side, x, None, 0.1, None)
        cv.save(); cv.clipPath(path, doAntiAlias=True)
        cv.drawPath(smooth_path([P(28, N - 8), P(37, N - 1), P(37, N + 11)], closed=False), paint_stroke(2.2, SILV_D))
        cv.drawPath(smooth_path([P(24, N - 6), P(30, N - 9)], closed=False), paint_stroke(3, SILV_L))
        cv.restore()
    return f

def g_bag(x, N, sy, H, bs):
    """Crossbody: strap from the far shoulder across the chest, bag on side bs."""
    Q = lambda o, y, s=None: (x + bs * o, y) if s is None else (x + bs * o, y, 1)
    def f(cv, side_, x_, acc, white):
        strap = smooth_path([Q(-34, sy + 2), Q(-8, sy + 40), Q(20, H - 40), Q(36, H - 30)], closed=False)
        cv.drawPath(strap, paint_stroke(9 + OUTL, OUT_COL)); cv.drawPath(strap, paint_stroke(9, white or STRAP))
        if white is None:
            cv.drawPath(strap, paint_stroke(1.2, BAG_L))
            cloth(cv, [Q(-12, sy + 30, 1), Q(-2, sy + 34, 1), Q(-6, sy + 44, 1), Q(-16, sy + 40, 1)], SILV, bs, x, None, 0.1, None, smooth=False)
        bag = [Q(28, H - 44), Q(58, H - 48), Q(66, H - 32), Q(64, H - 14), Q(34, H - 8), Q(26, H - 24)]
        path = cloth(cv, bag, BAG, bs, x, acc, 0.3, white, rim_from=20, light=0.2)
        if white is not None: return
        cv.save(); cv.clipPath(path, doAntiAlias=True)
        cv.drawPath(smooth_path([Q(29, H - 32), Q(46, H - 38), Q(65, H - 36)], closed=False), paint_stroke(2.2, SILV))
        cv.drawPath(smooth_path([Q(30, H - 36), Q(46, H - 42), Q(62, H - 43)], closed=False), paint_stroke(1.2, BAG_L))
        fold(cv, [Q(36, H - 20), Q(50, H - 22), Q(60, H - 18)], 2.4, c4(BAG_L, 0.8))
        cv.restore()
        cv.drawCircle(*Q(52, H - 39), 3.2, paint_fill(SILV_L))
    return f

def g_cap(x, headY, bs, glance=0.0):
    def f(cv, side_, x_, acc, white):
        cx = x + glance; r = R + 4
        brim = [(cx + bs * 8, headY - r * 0.62), (cx + bs * (r + 30), headY - r * 0.92), (cx + bs * (r + 36), headY - r * 0.70),
                (cx + bs * (r + 6), headY - r * 0.40)]
        cloth(cv, brim, CAP, 0, cx, acc, 0.3, white, light=0.25)
        dome = skia.Path(); dome.moveTo(cx - r, headY - 2)
        dome.cubicTo(cx - r, headY - r * 1.45, cx + r, headY - r * 1.45, cx + r, headY - 2)
        dome.cubicTo(cx + r * 0.5, headY - 8, cx - r * 0.5, headY - 8, cx - r, headY - 2); dome.close()
        cv.drawPath(dome, paint_stroke(OUTL, OUT_COL)); cv.drawPath(dome, paint_fill(white or CAP))
        if white is not None: return
        cv.save(); cv.clipPath(dome, doAntiAlias=True)
        sp = skia.Paint(AntiAlias=True)
        sp.setShader(skia.GradientShader.MakeRadial((cx - r * 0.3, headY - r * 0.9), r * 1.2,
                     [skia.Color4f(1, 1, 1, 0.22).toColor(), skia.Color4f(1, 1, 1, 0).toColor()]))
        cv.drawRect(skia.Rect.MakeXYWH(cx - r - 4, headY - r * 1.6, 2 * r + 8, r * 1.8), sp)
        cv.drawPath(dome, paint_stroke(6, skia.Color4f(*acc, 0.9)))
        for k in (-0.45, 0.45):   # panel seams
            cv.drawPath(smooth_path([(cx, headY - r * 1.08), (cx + k * r * 0.8, headY - r * 0.6), (cx + k * r, headY - 6)], closed=False), paint_stroke(1.6, CAP_L))
        # snapback opening (the back of the cap faces the camera)
        op = skia.Path(); op.addArc(skia.Rect.MakeXYWH(cx - 11, headY - 24, 22, 26), 180, 180); op.close()
        cv.drawPath(op, paint_fill(col(0.97)))
        cv.drawLine(cx - 12, headY - 10, cx + 12, headY - 10, paint_stroke(4, CAP_L))
        cv.restore()
        cv.drawCircle(cx, headY - r * 1.08, 3.4, paint_fill(CAP_L))
    return f

# ---- old money ----
def g_shirt(P, side, N, sy, H):
    def f(cv, side_, x, acc, white):
        pts = [P(0, N + 2, 1), P(14, N - 2), P(26, N + 2), P(36, sy + 8), P(39, sy + 26), P(37, H - 10), P(38, H + 24),
               P(20, H + 28), P(0, H + 26, 1)]
        path = cloth(cv, pts, SHIRT, side, x, acc, 0.26, white)
        if white is not None: return
        cv.save(); cv.clipPath(path, doAntiAlias=True)
        cv.drawLine(*P(5, N + 14), *P(5, H + 26), paint_stroke(1.4, SHIRT_D))     # placket
        for k in range(5): cv.drawCircle(*P(1, N + 26 + k * 24), 2.3, paint_fill(SHIRT_D))
        fold(cv, [P(30, sy + 30), P(22, sy + 52), P(24, sy + 70)], 2.4, c4(SHIRT_D, 0.8))
        fold(cv, [P(32, H - 20), P(24, H + 2)], 2.2, c4(SHIRT_D, 0.7))
        cv.restore()
    return f

def g_collar(P, side, N):
    def f(cv, side_, x, acc, white):
        cloth(cv, [P(0, N + 4, 1), P(9, N - 6, 1), P(18, N - 4), P(22, N + 6), P(10, N + 21, 1)], SHIRT, side, x, None, 0.18, white)
        if white is None: fold(cv, [P(8, N + 6), P(12, N + 14)], 1.8, SHIRT_D)
    return f

def g_shirt_sleeve(S, E, Hd):
    def f(cv, side, x, acc, white):
        fv = v_sub(Hd, E); l = v_len(fv) or 1; fu = (fv[0] / l, fv[1] / l)
        end = v_sub(Hd, v_mul(fu, 8))
        pts, C = tube_outline([S, E, end], 28, 23, 3)
        cloth(cv, pts, SHIRT, side, x, acc, 0.22, white, rim_from=-999, smooth=False)
        if white is None:
            p, t_, n_ = frame_at(C, 0.86)
            cv.drawLine(*v_add(p, v_mul(n_, 11)), *v_sub(p, v_mul(n_, 11)), paint_stroke(1.6, SHIRT_D))
            p, t_, n_ = frame_at(C, 0.5)
            fold(cv, [v_add(p, v_mul(n_, -7)), v_add(v_add(p, v_mul(t_, 6)), v_mul(n_, 7))], 2.0, SHIRT_D)
    return f

def g_knit(P, side, N, sy, H):
    def f(cv, side_, x, acc, white):
        pts = [P(0, N + 5, 1), P(13, N - 2), P(25, N + 1), P(36, sy + 8), P(41, sy + 26), P(38, H - 22), P(39, H + 6),
               P(37, H + 17, 1), P(0, H + 17, 1)]
        path = cloth(cv, pts, KNIT, side, x, acc, 0.38, white)
        if white is not None: return
        cv.save(); cv.clipPath(path, doAntiAlias=True)
        for o in (19, 33):
            cv.drawLine(*P(o, sy + 4), *P(o + 1, H + 4), paint_stroke(2.2, c4(KNIT_D, 0.55)))
        braid(cv, [P(10, sy + 4), P(11, H + 2)], 4.2, 13, c4(KNIT_D, 0.85), KNIT_L, 2.6)
        braid(cv, [P(26, sy + 10), P(27, H + 2)], 4.0, 13, c4(KNIT_D, 0.85), KNIT_L, 2.4)
        fold(cv, [P(33, H - 30), P(29, H - 16), P(33, H - 4)], 3.2, c4(KNIT_D, 0.8))
        fold(cv, [P(38, sy + 22), P(31, sy + 34), P(29, sy + 46)], 2.6, c4(KNIT_D, 0.7))
        cv.drawPath(polyline([P(0, H + 3), P(38, H + 4)]), paint_stroke(2.4, KNIT_D))
        ribs(cv, P(0, H + 4), P(38, H + 5), P(0, H + 17), P(37, H + 17), 11, c4(KNIT_D, 0.75), 1.5)
        cv.restore()
        nb = smooth_path([P(0, N + 8), P(10, N + 4), P(17, N)], closed=False)
        cv.drawPath(nb, paint_stroke(7 + OUTL * 0.6, OUT_COL)); cv.drawPath(nb, paint_stroke(7, KNIT_D))
    return f

def g_knit_sleeve(S, E, cuff0, Hd):
    def f(cv, side, x, acc, white):
        pts, C = tube_outline([S, E, cuff0], 32, 25, 3)
        path = cloth(cv, pts, KNIT, side, x, acc, 0.36, white, rim_from=-999, smooth=False)
        if white is not None: return
        cv.save(); cv.clipPath(path, doAntiAlias=True)
        braid(cv, C[2:-7], 3.6, 12, c4(KNIT_D, 0.85), KNIT_L, 2.3)
        p, t_, n_ = frame_at(C, 0.48)
        for k in (-1, 1):
            fold(cv, [v_add(p, v_mul(n_, 7 * k)), v_add(v_add(p, v_mul(t_, 6)), v_mul(n_, 12 * k))], 2.4, c4(KNIT_D, 0.85))
        p, t_, n_ = frame_at(C, 0.84)
        a0 = v_add(p, v_mul(n_, 14)); a1 = v_sub(p, v_mul(n_, 14))
        cv.drawLine(*a0, *a1, paint_stroke(2.2, KNIT_D))
        ribs(cv, a0, a1, v_add(C[-1], v_mul(n_, 14)), v_sub(C[-1], v_mul(n_, 14)), 7, c4(KNIT_D, 0.8), 1.4)
        cv.restore()
    return f

def g_trousers(P, side, H, F_):
    def f(cv, side_, x, acc, white):
        pts = [P(0, H - 8, 1), P(37, H - 8, 1), P(41, H + 34), P(45, H + 110), P(49, F_ - 22), P(51, F_ - 12, 1),
               P(4, F_ - 12, 1), P(6, H + 84), P(2, H + 60), P(0, H + 52, 1)]
        path = cloth(cv, pts, TROU, side, x, acc, 0.30, white)
        if white is not None: return
        cv.save(); cv.clipPath(path, doAntiAlias=True)
        cv.drawPath(polyline([P(0, H + 3), P(38, H + 3)]), paint_stroke(2.4, TROU_D))
        cv.drawPath(polyline([P(24, H - 8), P(24, H + 3)]), paint_stroke(4, TROU_D))
        cv.drawPath(smooth_path([P(25, H + 10), P(27, H + 90), P(29, F_ - 16)], closed=False), paint_stroke(2.2, TROU_L))
        fold(cv, [P(17, H + 4), P(18, H + 20), P(20, H + 34)], 2.6, TROU_D)
        fold(cv, [P(34, H + 3), P(38, H + 20), P(41, H + 34)], 2.2, TROU_D)
        fold(cv, [P(10, H + 104), P(22, H + 100), P(32, H + 106)], 2.4, c4(TROU_D, 0.7), TROU_L)
        fold(cv, [P(8, F_ - 38), P(22, F_ - 30), P(42, F_ - 36)], 2.8, TROU_D, TROU_L)
        fold(cv, [P(30, F_ - 24), P(40, F_ - 18), P(48, F_ - 22)], 2.2, TROU_D)
        cv.restore()
    return f

def g_loafer(P, side, F_):
    def f(cv, side_, x, acc, white):
        sole = [P(5, F_ - 6, 1), P(58, F_ - 7), P(62, F_ - 4), P(59, F_, 1), P(5, F_, 1)]
        up = [P(6, F_ - 24), P(20, F_ - 26), P(36, F_ - 21), P(50, F_ - 14), P(60, F_ - 8), P(58, F_ - 5, 1), P(5, F_ - 5, 1), P(4, F_ - 14)]
        cloth(cv, sole, LOAF_D, side, x, acc, 0.1, white)
        path = cloth(cv, up, LOAF, side, x, acc, 0.25, white, light=0.22)
        if white is not None: return
        cv.save(); cv.clipPath(path, doAntiAlias=True)
        fold(cv, [P(12, F_ - 21), P(30, F_ - 20), P(50, F_ - 12)], 3.0, c4(LOAF_L, 0.9))
        cv.drawPath(smooth_path([P(31, F_ - 21), P(46, F_ - 16), P(56, F_ - 9)], closed=False), paint_stroke(1.4, c4(LOAF_L, 0.9)))
        cv.restore()
        cloth(cv, [P(26, F_ - 23, 1), P(40, F_ - 17, 1), P(38, F_ - 11, 1), P(24, F_ - 16, 1)], LOAF_D, side, x, None, 0.0, None, smooth=False)
        cv.drawPath(smooth_path([P(29, F_ - 18), P(32, F_ - 17), P(35, F_ - 15)], closed=False), paint_stroke(2.2, LOAF_L))
        cv.drawLine(*P(5, F_ - 3), *P(58, F_ - 3), paint_stroke(1.2, c4(LOAF_L, 0.7)))
    return f

def g_watch(band_a, band_b, face, side):
    def f(cv, side_, x, acc, white):
        chain(cv, [band_a, band_b], 21, white or SILV, gloss=False)
        if white is not None:
            cv.drawCircle(face[0], face[1], 11, paint_fill(white)); return
        d = v_sub(band_b, band_a)
        cv.drawCircle(face[0], face[1], 11, paint_fill(OUT_COL))
        cv.drawCircle(face[0], face[1], 9, paint_fill(SILV))
        cv.drawCircle(face[0], face[1], 6.5, paint_fill(DIAL))
        cv.drawCircle(face[0] + side * 10, face[1], 2.0, paint_fill(SILV))
        cv.drawLine(*face, face[0] + 3, face[1] - 5, paint_stroke(1.4, SILV_L))
        cv.drawLine(*face, face[0] - 4, face[1] + 1, paint_stroke(1.4, SILV_L))
        cv.drawCircle(face[0] - 3, face[1] - 4, 2.2, paint_fill(skia.Color4f(1, 1, 1, 0.55)))
        cv.drawCircle(*face, 11, paint_stroke(2, skia.Color4f(*acc, 0.6)))
    return f

def g_navy(P, side, N, sy, H):
    """Sweater thrown over the shoulders: body lies across the back/shoulders, sleeves hang loose down the chest."""
    long_ = side > 0
    def f(cv, side_, x, acc, white):
        drape = [P(0, N + 6, 1), P(14, N - 4), P(34, N - 2), P(50, sy + 2), P(60, sy + 22), P(54, sy + 34),
                 P(42, sy + 26), P(26, sy + 14), P(10, sy + 14), P(0, sy + 16, 1)]
        path = cloth(cv, drape, NAVY, side, x, acc, 0.35, white, light=0.2)
        if white is None:
            cv.save(); cv.clipPath(path, doAntiAlias=True)
            fold(cv, [P(10, N + 8), P(30, N + 6), P(48, sy + 10)], 3.0, c4(NAVY_L, 0.95))
            fold(cv, [P(20, sy + 8), P(38, sy + 16), P(52, sy + 28)], 2.4, NAVY_D)
            cv.restore()
        end_y = sy + (118 if long_ else 86)
        sway = 6 if long_ else -4
        pts, C = tube_outline([P(30, sy + 10), P(24, sy + 40), P(18 + sway, (sy + 40 + end_y) / 2), P(15 + sway, end_y)], 26, 22, 2)
        path = cloth(cv, pts, NAVY, side, x, acc, 0.30, white, rim_from=20, smooth=False, light=0.16)
        if white is None:
            cv.save(); cv.clipPath(path, doAntiAlias=True)
            for u in (0.28, 0.5, 0.7):
                p, t_, n_ = frame_at(C, u)
                fold(cv, [v_add(p, v_mul(n_, -9)), v_add(v_add(p, v_mul(t_, 6)), v_mul(n_, 7))], 2.2, NAVY_D)
            p, t_, n_ = frame_at(C, 0.86)
            a0 = v_add(p, v_mul(n_, 12)); a1 = v_sub(p, v_mul(n_, 12))
            cv.drawLine(*a0, *a1, paint_stroke(2, NAVY_D))
            ribs(cv, a0, a1, v_add(C[-1], v_mul(n_, 11)), v_sub(C[-1], v_mul(n_, 11)), 5, c4(NAVY_L, 0.8), 1.3)
            cv.restore()
    return f

# ---------------- outfit assembly ----------------
def g_pocket_hoodie(P, side, H):
    def f(cv, side_, x, acc, white):
        pk = [P(0, H - 42, 1), P(24, H - 42), P(38, H - 6), P(38, H + 14, 1), P(0, H + 14, 1)]
        path = smooth_path(pk)
        cv.drawPath(smooth_path(pk[1:4], closed=False), paint_stroke(OUTL * 0.6, OUT_COL))
        cv.drawPath(path, paint_fill(HOOD))
        cv.save(); cv.clipPath(path, doAntiAlias=True)
        sp = skia.Paint(AntiAlias=True)
        sp.setShader(skia.GradientShader.MakeLinear([(x + side * 6, 0), (x + side * 70, 0)], [skia.Color4f(0, 0, 0, 0).toColor(), skia.Color4f(0, 0, 0, 0.36).toColor()]))
        cv.drawRect(path.computeTightBounds().makeOutset(10, 10), sp)
        blob(cv, P(12, H - 26), 12, c4(HOOD_W, 0.3))
        fold(cv, [P(6, H - 30), P(16, H - 20), P(20, H - 4)], 2.4, c4(HOOD_L, 0.8))
        cv.restore()
        fold(cv, [P(24, H - 41), P(31, H - 24), P(37, H - 7)], 3.8, HOOD_D, HOOD_L)
        cv.drawPath(smooth_path(pk[1:4], closed=False), paint_stroke(2.6, HOOD_D))
    return f

def g_pocket_trouser(P, side, H):
    def f(cv, side_, x, acc, white):
        pt = [P(30, H + 14), P(40, H + 12), P(44, H + 40), P(30, H + 44)]
        path = smooth_path(pt)
        cv.save(); cv.clipPath(polygon([P(0, H + 12), P(41, H + 12), P(44, H + 50), P(0, H + 50)]), doAntiAlias=True)
        cv.drawPath(path, paint_fill(TROU))
        sp = skia.Paint(AntiAlias=True)
        sp.setShader(skia.GradientShader.MakeLinear([(x + side * 6, 0), (x + side * 70, 0)], [skia.Color4f(0, 0, 0, 0).toColor(), skia.Color4f(0, 0, 0, 0.30).toColor()]))
        cv.drawPath(path, sp)
        cv.restore()
        fold(cv, [P(34, H + 12), P(38, H + 22), P(41, H + 34)], 2.6, TROU_D)
        cv.drawPath(polyline([P(41, H + 12), P(44, H + 46)]), paint_stroke(OUTL * 0.6, OUT_COL))
    return f

# ---------------- artwork clothing (from the user's sheets) ----------------
from PIL import Image as _PILImage
ART = {}
def art(name):
    if name not in ART:
        im = _PILImage.open(os.path.join(HERE, 'art', name + '.png')).convert('RGBA')
        ART[name] = skia.Image.fromarray(np.array(im), colorType=skia.kRGBA_8888_ColorType)
    return ART[name]

T_NOW = [0.0]
WATCH_AT = [None]
HANDS = [[]]

# sleeve cuff points in each top's artwork (fraction of width, height), for hands coming out of the cuffs
import json as _json
CUFFS = _json.load(open(os.path.join(HERE, 'art', 'cuffs.json')))
# on-screen widths of the (side-padded) top artworks
SK_TOP_W = 222; VT_TOP_W = 210; VT_SHIRT_W = 156
# belted trousers: their belt sits exactly in the gap between the jacket fronts of the final-pose top
HOLE_FRAC = 0.7291      # vt_top_pose: first row of the waist gap / image height
BELT_FRAC = 7 / 438     # vt_trousers: top row of the belt / image height
def TR_TOP(N):
    ti = art('vt_top_pose'); y = (N - 16) + HOLE_FRAC * VT_TOP_W * ti.height() / ti.width() + 1
    return (y - BELT_FRAC * (F - 26)) / (1 - BELT_FRAC)

def top_art(kind, x, hip, t, pocket):
    """Which top artwork is on the body now and where: (name, top_y, width, flip)."""
    N = hip - TORSO
    pk = pocket.get(-1, 0) > 0.5
    if kind == 'street':      # skater: racing jacket; final pose = left hand in the jeans pocket
        return ('sk_top_pose' if pk else 'sk_top'), N - 16, SK_TOP_W, False
    if t < R_TIMES[1]: return 'vt_shirt', N - 14, VT_SHIRT_W, False
    return ('vt_top_pose' if pk else 'vt_top'), N - 16, VT_TOP_W, False

def cuff_points(kind, x, hip, t, pocket):
    nm, top, w, flip = top_art(kind, x, hip, t, pocket)
    img = art(nm); h = w * img.height() / img.width()
    return [(x + (q[0] - 0.5) * w, top + q[1] * h, q[2] if len(q) > 2 else 0.0) for q in CUFFS[nm]]

def watch_on_wrist(cv, p):
    """The watch turned to sit across the wrist: round face to camera, strap cut to the wrist width."""
    img = art('watch'); iw, ih = img.width(), img.height()
    k = 12.0 / (iw * 0.58)                       # face ~12 px across
    w, h = iw * k, ih * k
    cv.save(); cv.translate(p[0], p[1])
    clip = skia.Path(); clip.addRoundRect(skia.Rect.MakeXYWH(-9, -6, 18, 12), 3, 3); cv.clipPath(clip, doAntiAlias=True)
    cv.rotate(90); cv.drawImageRect(img, skia.Rect.MakeXYWH(-w / 2, -h / 2, w, h), skia.SamplingOptions(skia.FilterMode.kLinear))
    cv.restore()

def strap_fn(x, N, hip, d=1, colr=(0.07, 0.07, 0.08)):
    """Crossbody strap: from the bag on one hip, across the chest, over the other shoulder (d=-1 mirrors it)."""
    def f(cv, side_, x_, acc, white):
        pts = [(x - d * 40, N + 70), (x + d * 6, N + 40), (x + d * 52, N + 2)]
        col_ = white if white is not None else skia.Color4f(*colr, 1)
        cv.drawPath(polyline(pts), paint_stroke(19, OUT_COL)); cv.drawPath(polyline(pts), paint_stroke(12, col_))
        if white is None:
            cv.drawPath(polyline(pts), paint_stroke(2, skia.Color4f(1, 1, 1, 0.18)))
    return f

def spr_rot(name, cx, cy, width, deg):
    """Artwork centred at (cx, cy), rotated by deg (to level the cap)."""
    def f(cv, side_, x, acc, white):
        img = art(name); w = width; h = w * img.height() / img.width()
        cv.save(); cv.translate(cx, cy); cv.rotate(deg)
        paint = skia.Paint(AntiAlias=True)
        if white is not None: paint.setColorFilter(skia.ColorFilters.Blend(white, skia.BlendMode.kSrcIn))
        cv.drawImageRect(img, skia.Rect.MakeXYWH(-w / 2, -h / 2, w, h), skia.SamplingOptions(skia.FilterMode.kLinear), paint)
        cv.restore()
    return f

def spr(name, cx, top=None, width=None, height=None, bottom=None, flip=False):
    """Op that draws an artwork piece. Size by width or height (aspect kept); place by top or bottom; centred on cx."""
    def f(cv, side_, x, acc, white):
        img = art(name); iw, ih = img.width(), img.height()
        w = width if width else height * iw / ih; h = w * ih / iw
        y0 = top if top is not None else bottom - h
        cv.save(); cv.translate(cx, y0)
        if flip: cv.scale(-1, 1)
        paint = skia.Paint(AntiAlias=True)
        if white is not None:
            paint.setColorFilter(skia.ColorFilters.Blend(white, skia.BlendMode.kSrcIn))
        cv.drawImageRect(img, skia.Rect.MakeXYWH(-w / 2, 0, w, h), skia.SamplingOptions(skia.FilterMode.kLinear), paint)
        hole = os.path.join(HERE, 'art', name + '_hole.png')
        if False and white is None and os.path.exists(hole):  # (neck hidden: head sits right on the collar)
            cv.saveLayer(None, None)
            shape(cv, capsule_v(0, -40, h * 0.3, TW), skia.Color4f(0.97, 0.97, 0.97, 1))
            dp = skia.Paint(); dp.setBlendMode(skia.BlendMode.kDstIn)
            cv.drawImageRect(art(name + '_hole'), skia.Rect.MakeXYWH(-w / 2, 0, w, h), skia.SamplingOptions(skia.FilterMode.kLinear), dp)
            cv.restore()
        cv.restore()
    return f

def board_fn(x, hip, pk):
    """Skateboard standing on its tail next to the model, its nose under the right cuff (the hand holds it)."""
    def f(cv, side_, x_, acc, white):
        cps = cuff_points('street', x, hip, T_NOW[0], pk)
        cx, cy = (max(cps)[0], max(cps)[1]) if cps else (x + 70, hip + 30)
        spr('sk_board', cx + 16, top=cy - 6, height=F + 8 - (cy - 6))(cv, side_, x_, acc, white)
    return f

def outfit(kind, x, hip, arms, glance=0.0, pockets=None):
    N = hip - TORSO; headY = N - R - 7; t = T_NOW[0]
    pk = pockets or {}
    pose = pk.get(-1, 0) > 0.5
    if kind == 'street':     # SKATER
        jk, tp, tw_, _ = top_art('street', x, hip, t, pk)
        return [
            {'anchor': (x, (N + hip) / 2), 'outer': [('fn', spr(jk, x, top=tp, width=tw_), -1)]},
            {'anchor': (x - 40, hip - 20), 'strap': [('fn', strap_fn(x, N, hip), -1), ('fn', spr('sk_bag', x - 42, top=N + 62, width=70), -1)]},
            {'anchor': (x, hip + 90), 'pants': [('fn', spr('sk_jeans', x, top=hip - 36, height=F - hip + 8), -1)]},
            {'anchor': (x, F - 16), 'shoes': [('fn', spr('sk_shoe_l', x - 27, bottom=F + 10, width=58), -1), ('fn', spr('sk_shoe_r', x + 27, bottom=F + 10, width=58), -1)]},
            {'anchor': (x + 86, F - 90), 'shoes': [('fn', board_fn(x, hip, pk), -1)]},
            {'anchor': (x, headY - 20), 'hat': [('fn', spr('sk_beanie', x + glance, bottom=headY + 4, width=86), 0)]},
        ]
    top = 'vt_top_pose' if pose else 'vt_top'   # VINTAGE
    return [
        {'anchor': (x, (N + hip) / 2), 'under': [] if t >= R_TIMES[1] + 0.07 else [('fn', spr('vt_shirt', x, top=N - 14, width=VT_SHIRT_W), 1)]},   # jacket art already has the shirt
        {'anchor': (x, (N + hip) / 2), 'mid': [('fn', spr(top, x, top=N - 16, width=VT_TOP_W), 1)]},
        {'anchor': (x, hip + 90), 'pants': [('fn', spr('vt_trousers', x, top=TR_TOP(N), height=F - 26 - TR_TOP(N)), 1)]},
        {'anchor': (x, F - 12), 'shoes': [('fn', spr('vt_boot_l', x - 25, bottom=F + 10, width=50), 1), ('fn', spr('vt_boot_r', x + 25, bottom=F + 10, width=50), 1)]},
        {'anchor': (x + 40, hip - 20), 'strap': [('fn', strap_fn(x, N, hip, -1, (0.30, 0.17, 0.09)), 1), ('fn', spr('vt_bag', x + 44, top=N + 60, width=62), 1)]},
        {'anchor': (x, headY), 'hat': [('fn', spr('vt_glasses', x + glance, top=headY - 13, width=62), 0)]},
    ]

def outfit_code(kind, x, hip, arms, glance=0.0, pockets=None):
    """arms: {side: [S, E, Hd]} for both sides. Returns pieces in dressing order."""
    N = hip - TORSO; sy = N + 12; H = hip; headY = N - R - 7
    Pf = lambda sd: (lambda o, y, s=None: (x + sd * o, y) if s is None else (x + sd * o, y, 1))
    def both(make, *a): return [('fn', make(Pf(sd), sd, *a), sd) for sd in (-1, 1)]
    def sleeves(make):
        out = []
        for sd in (-1, 1):
            S, E, Hd = arms[sd]
            fv = v_sub(Hd, E); fl = max(v_len(fv), 1); fu = (fv[0] / fl, fv[1] / fl)
            pk_ = (pockets or {}).get(sd, 0.0)
            S2 = (S[0] + sd * 2, S[1] + 30)
            out.append(('fn', make(S2, E, v_sub(Hd, v_mul(fu, lerp(22, 2, pk_))), Hd), sd))
            out.append(('fn', cap_fn(S2, sd), sd))
        return out
    P1 = Pf(-1); P2 = Pf(1)
    if kind == 'street':   # stylist on the left -> near side is -1
        return [
            {'anchor': P1(26, (sy + H) / 2), 'outer': both(g_hoodie, N, sy, H), 'osleeve': sleeves(g_hoodie_sleeve),
             'pocket': both(g_pocket_hoodie, H) if (pockets or {}).get(-1, 0) > 0.05 else []},
            {'anchor': P1(40, H - 30), 'strap': [('fn', g_bag(x, N, sy, H, -1), -1)]},
            {'anchor': P1(28, H + 90), 'pants': both(g_jeans, H, F)},
            {'anchor': P1(32, F - 16), 'shoes': both(g_sneaker, F)},
            {'anchor': P1(28, N + 4), 'acc': both(g_headphones, N)},
            {'anchor': (x - 10, headY - 20), 'hat': [('fn', g_cap(x, headY, -1, glance), 0)]},
        ]
    S, E, Hd = arms[1]
    fv = v_sub(Hd, E); fl = max(v_len(fv), 1); fu = (fv[0] / fl, fv[1] / fl)
    band_a = v_sub(Hd, v_mul(fu, 20)); band_b = v_sub(Hd, v_mul(fu, 12))
    face = v_add(v_lerp(band_a, band_b, 0.5), (3, 0))
    shirt_sl = [('fn', g_shirt_sleeve(*arms[sd]), sd) for sd in (-1, 1)]
    return [   # stylist on the right -> near side is +1
        {'anchor': P2(20, (sy + H) / 2), 'under': both(g_shirt, N, sy, H), 'usleeve': shirt_sl, 'collar': both(g_collar, N)},
        {'anchor': P2(24, (sy + H) / 2), 'mid': both(g_knit, N, sy, H), 'msleeve': sleeves(g_knit_sleeve)},
        {'anchor': P2(26, H + 90), 'pants': both(g_trousers, H, F),
         'pocket': [('fn', g_pocket_trouser(P1, -1, H), -1)] if (pockets or {}).get(-1, 0) > 0.05 else []},
        {'anchor': P2(30, F - 12), 'shoes': both(g_loafer, F)},
        {'anchor': face, 'acc': [('fn', g_watch(band_a, band_b, face, 1), 1)]},
        {'anchor': P2(24, sy + 10), 'drape': both(g_navy, N, sy, H)},
    ]

# ---------------- rack icons ----------------
ICONS_L = ['sk_top', 'sk_bag', 'sk_jeans', 'sk_shoe', 'sk_board', 'sk_beanie']
ICONS_R = ['vt_shirt', 'vt_jacket', 'vt_trousers', 'vt_boot', 'vt_bag', 'vt_glasses']

def hanger(cv):
    p = paint_stroke(3, col(0.75))
    cv.drawLine(0, 0, 0, 9, p)
    cv.drawPath(polyline([(-24, 21), (0, 9), (24, 21), (-24, 21)]), p)

def icon_top(cv, base, acc, wide=0):
    body = [(-24 - wide, 20), (0, 24), (24 + wide, 20), (40 + wide, 34), (34 + wide, 70), (24 + wide, 64), (23 + wide, 94, 1),
            (-23 - wide, 94, 1), (-24 - wide, 64), (-34 - wide, 70), (-40 - wide, 34)]
    return cloth(cv, body, base, 0, 0, acc, 0.3, None, light=0.18)

ICON_ART = dict(sk_top='sk_top', sk_bag='sk_bag', sk_jeans='sk_jeans', sk_shoe='sk_shoe_l', sk_board='sk_board', sk_beanie='sk_beanie',
                vt_shirt='vt_shirt', vt_jacket='vt_jacket', vt_trousers='vt_trousers', vt_boot='vt_boot_l', vt_bag='vt_bag', vt_glasses='vt_glasses')
TOPS = ('sk_top', 'vt_shirt', 'vt_jacket')

def draw_icon(cv, name, p, s=1.0):
    img = art(ICON_ART[name]); iw, ih = img.width(), img.height()
    bw, bh = 92 * s, 104 * s; k = min(bw / iw, bh / ih); w, h = iw * k, ih * k
    if name in TOPS:
        cv.save(); cv.translate(p[0], p[1]); cv.scale(s, s); hanger(cv); cv.restore()
    cv.drawImageRect(img, skia.Rect.MakeXYWH(p[0] - w / 2, p[1] + 12 * s, w, h), skia.SamplingOptions(skia.FilterMode.kLinear))

def draw_icon_code(cv, name, p, s=1.0):
    cv.save(); cv.translate(p[0], p[1]); cv.scale(s, s)
    if name in ('hoodie', 'shirt', 'knit', 'navy'): hanger(cv)
    if name == 'hoodie':
        cloth(cv, [(-16, 16), (0, 10), (16, 16), (12, 28), (-12, 28)], HOOD, 0, 0, ACC_ST, 0.3, None, light=0.2)
        path = icon_top(cv, HOOD, ACC_ST, 3)
        cv.save(); cv.clipPath(path, doAntiAlias=True)
        blob(cv, (-10, 44), 12, c4(HOOD_W, 0.35))
        cv.drawPath(smooth_path([(-18, 60), (-12, 52, 1), (12, 52, 1), (18, 60), (18, 80, 1), (-18, 80, 1)]), paint_stroke(2.4, HOOD_D))
        fold(cv, [(20, 36), (12, 48)], 2.4, HOOD_D)
        ribs(cv, (-26, 85), (26, 85), (-26, 94), (26, 94), 10, c4(HOOD_D, 0.8))
        cv.restore()
        for xx in (-5, 5):
            cv.drawLine(xx, 26, xx * 1.2, 48, paint_stroke(4.5, OUT_COL)); cv.drawLine(xx, 26, xx * 1.2, 48, paint_stroke(2.6, TEEW))
    elif name == 'shirt':
        path = icon_top(cv, SHIRT, ACC_OM)
        cv.save(); cv.clipPath(path, doAntiAlias=True)
        cv.drawLine(0, 30, 0, 94, paint_stroke(1.4, SHIRT_D))
        for k in range(4): cv.drawCircle(2, 40 + k * 14, 2, paint_fill(SHIRT_D))
        cv.restore()
        for sd in (-1, 1): cloth(cv, [(0, 22, 1), (sd * 12, 16, 1), (sd * 16, 26), (sd * 4, 34, 1)], SHIRT, 0, 0, None, 0.15, None, smooth=False)
    elif name == 'knit':
        path = icon_top(cv, KNIT, ACC_OM)
        cv.save(); cv.clipPath(path, doAntiAlias=True)
        for xx in (-12, 12): braid(cv, [(xx, 30), (xx, 86)], 4, 12, c4(KNIT_D, 0.85), KNIT_L, 2.4)
        cv.drawLine(0, 28, 0, 88, paint_stroke(2, c4(KNIT_D, 0.6)))
        ribs(cv, (-23, 84), (23, 84), (-23, 94), (23, 94), 9, c4(KNIT_D, 0.8))
        cv.restore()
        cv.drawPath(smooth_path([(-12, 21), (0, 28), (12, 21)], closed=False), paint_stroke(4, KNIT_D))
    elif name == 'navy':
        path = cloth(cv, [(-34, 4), (34, 4), (38, 30), (30, 36, 1), (-30, 36, 1), (-38, 30)], NAVY, 0, 0, ACC_OM, 0.3, None, light=0.2)
        cv.save(); cv.clipPath(path, doAntiAlias=True)
        fold(cv, [(-24, 14), (0, 20), (24, 14)], 2.6, NAVY_L)
        cv.restore()
        for sd in (-1, 1):
            pts, C = tube_outline([(sd * 26, 30), (sd * 30, 60), (sd * 26, 92)], 16, 13)
            cloth(cv, pts, NAVY, 0, 0, ACC_OM, 0.3, None, smooth=False, light=0.14)
            ribs(cv, (sd * 20, 82), (sd * 33, 82), (sd * 20, 92), (sd * 32, 92), 4, c4(NAVY_L, 0.8))
        cv.drawLine(0, 0, 0, 8, paint_stroke(3, col(0.75)))
    elif name == 'bag':
        for sd in (-1, 1):
            sp = smooth_path([(0, 0), (sd * 24, 30), (sd * 28, 62)], closed=False)
            cv.drawPath(sp, paint_stroke(8 + OUTL, OUT_COL)); cv.drawPath(sp, paint_stroke(8, STRAP))
        path = cloth(cv, [(-34, 62), (30, 58), (38, 76), (34, 96), (-30, 100), (-38, 82)], BAG, 0, 0, ACC_ST, 0.3, None, light=0.2)
        cv.save(); cv.clipPath(path, doAntiAlias=True)
        cv.drawPath(smooth_path([(-36, 74), (0, 70), (37, 70)], closed=False), paint_stroke(2.4, SILV))
        fold(cv, [(-20, 88), (0, 86), (22, 90)], 2.4, BAG_L)
        cv.restore()
        cv.drawCircle(14, 66, 3.4, paint_fill(SILV_L))
    elif name in ('trousers', 'jeans'):
        cv.drawLine(0, 0, 0, 10, paint_stroke(3, col(0.75)))
        tr = name == 'trousers'
        c_, d_, l_ = (TROU, TROU_D, TROU_L) if tr else (JEAN, JEAN_D, JEAN_L)
        wdt = 22 if tr else 28
        path = cloth(cv, [(-wdt, 10, 1), (wdt, 10, 1), (wdt + 6, 106, 1), (5, 106, 1), (0, 44, 1), (-5, 106, 1), (-wdt - 6, 106, 1)],
                     c_, 0, 0, ACC_OM if tr else ACC_ST, 0.3, None, smooth=False, light=0.14)
        cv.save(); cv.clipPath(path, doAntiAlias=True)
        cv.drawLine(-wdt, 17, wdt, 17, paint_stroke(2, d_))
        if tr:
            for s_ in (-1, 1): cv.drawLine(s_ * 13, 20, s_ * 15, 104, paint_stroke(2, l_))
            fold(cv, [(-14, 18), (-12, 36)], 2.2, d_); fold(cv, [(14, 18), (12, 36)], 2.2, d_)
        else:
            blob(cv, (-16, 40), 10, c4(JEAN_L, 0.6)); blob(cv, (16, 40), 10, c4(JEAN_L, 0.6))
            for sd in (-1, 1): cv.drawLine(sd * (wdt + 2), 20, sd * (wdt + 5), 104, paint_stroke(1.2, STITCH))
            for yy in (84, 96):
                for sd in (-1, 1): fold(cv, [(sd * (wdt + 4), yy), (sd * 14, yy - 4), (sd * 4, yy + 1)], 2.4, d_)
        cv.restore()
    elif name == 'loafers':
        for dx in (-26, 20):
            P = lambda o, y, s=None, dx=dx: (dx - 32 + o, y - 14) if s is None else (dx - 32 + o, y - 14, 1)
            g_loafer(P, 0, 28)(cv, 0, 0, None, None)
    elif name == 'sneakers':
        for dx in (-30, 18):
            P = lambda o, y, s=None, dx=dx: (dx - 32 + o, y - 16) if s is None else (dx - 32 + o, y - 16, 1)
            g_sneaker(P, 0, 32)(cv, 0, 0, None, None)
    elif name == 'watch':
        cv.drawCircle(0, 14, 13, paint_stroke(13, OUT_COL)); cv.drawCircle(0, 14, 13, paint_stroke(10, SILV))
        cv.drawCircle(0, 30, 12, paint_fill(OUT_COL)); cv.drawCircle(0, 30, 10, paint_fill(SILV)); cv.drawCircle(0, 30, 7, paint_fill(DIAL))
        cv.drawLine(0, 30, 3, 25, paint_stroke(1.4, SILV_L)); cv.drawCircle(-2, 27, 1.8, paint_fill(skia.Color4f(1, 1, 1, 0.6)))
    elif name == 'headphones':
        arc = skia.Path(); arc.addArc(skia.Rect.MakeXYWH(-24, 0, 48, 52), 180, 180)
        cv.drawPath(arc, paint_stroke(7 + OUTL, OUT_COL)); cv.drawPath(arc, paint_stroke(7, SILV))
        for s_ in (-1, 1):
            cloth(cv, [(s_ * 20, 18), (s_ * 34, 20), (s_ * 36, 40), (s_ * 30, 52), (s_ * 18, 50), (s_ * 15, 34)], SILV, 0, 0, ACC_ST, 0.3, None, light=0.3)
            cloth(cv, [(s_ * 14, 24), (s_ * 19, 22), (s_ * 20, 44), (s_ * 14, 46)], CUSH, 0, 0, None, 0.1, None)
    elif name == 'cap':
        cv.drawLine(0, 0, 0, 8, paint_stroke(3, col(0.75)))
        g_cap(0, 46, 1)(cv, 0, 0, ACC_ST, None)
    cv.restore()

def draw_rack(cv, rx, t, times, icons):
    chrome = col(0.62); dk = col(0.40)
    for px in (rx + 8, rx + RACK_DX):
        chain(cv, [(px, F - 385), (px, F - 14)], 8, chrome, gloss=False)
    chain(cv, [(rx - 6, F - 385), (rx + 131, F - 385)], 8, chrome, gloss=False)
    chain(cv, [(rx + 8, F - 56), (rx + RACK_DX, F - 56)], 6, dk, gloss=False)
    chain(cv, [(rx - 6, F - 14), (rx + 131, F - 14)], 8, chrome, gloss=False)
    for px in (rx + 2, rx + 123):
        cv.drawCircle(px, F - 6, 8, paint_fill(OUT_COL)); cv.drawCircle(px, F - 6, 6, paint_fill(dk))
    for i in (2, 1, 0, 3, 4, 5):
        if t < times[i] - 0.52:
            draw_icon(cv, icons[i], (rx + SLOT_HOOK[i][0], F + SLOT_HOOK[i][1]))

def piece_anim(t, tk):
    if t < tk - 0.07: return None
    u = (t - (tk - 0.07)) / 0.07
    if u < 1:
        e = ease_out(u); return (1.0, 1 - e, 1.25 - 0.25 * e, 0.0)
    v = t - tk
    return (1.0, 0.0, 1 + 0.10 * math.exp(-v * 16) * math.cos(v * 34), clamp(1 - v / 0.22))

def drop_small_holes(path, min_area=4000.0):
    """Keep only the big contours of a garment silhouette (no tiny gaps between crossed arms and body)."""
    out = skia.Path(); cur = None
    for verb, pts in path:
        if verb == skia.Path.kMove_Verb:
            if cur is not None and not cur.isEmpty():
                bb = cur.computeTightBounds()
                if bb.width() * bb.height() >= min_area: out.addPath(cur)
            cur = skia.Path(); cur.moveTo(pts[0])
        elif verb == skia.Path.kLine_Verb: cur.lineTo(pts[1])
        elif verb == skia.Path.kQuad_Verb: cur.quadTo(pts[1], pts[2])
        elif verb == skia.Path.kConic_Verb: cur.quadTo(pts[1], pts[2])
        elif verb == skia.Path.kCubic_Verb: cur.cubicTo(pts[1], pts[2], pts[3])
        elif verb == skia.Path.kClose_Verb: cur.close()
    if cur is not None and not cur.isEmpty():
        bb = cur.computeTightBounds()
        if bb.width() * bb.height() >= min_area: out.addPath(cur)
    return out


def cap_fn(S2, sd):
    """Round shoulder cap: adds a circle at the top of the sleeve to the garment silhouette (fill comes from the garment)."""
    def f(cv, side, x, acc, white):
        if CL['rec'] is not None:
            p = skia.Path(); p.addCircle(S2[0] - sd * 2, S2[1] - 8, 30); CL['rec'].append(p)
    return f


def soft_shape(path, r=22.0):
    """Round every corner of a garment silhouette (fabric is soft: no steps or sharp corners)."""
    p = skia.Paint(AntiAlias=True, Style=skia.Paint.kFill_Style)
    p.setPathEffect(skia.CornerPathEffect.Make(r))
    out = skia.Path(); p.getFillPath(path, out)
    return out


def draw_garment(cv, t, pieces, lay, sl, times, side, x, hand=None, acc=None):
    """A top + its sleeves as ONE garment: one outline around the combined silhouette, soft seams inside."""
    for i, pc in enumerate(pieces):
        ob = pc.get(lay) or []; os_ = pc.get(sl) or []
        if not ob and not os_: continue
        an = piece_anim(t, times[i])
        if an is None: continue
        alpha, fly, sc, flash = an
        ax, ay = pc['anchor']
        off = v_mul(v_sub(hand, (ax, ay)), fly) if hand else (side * 120 * fly, -30 * fly)
        cv.save(); cv.translate(ax + off[0], ay + off[1]); cv.scale(sc, sc); cv.translate(-ax, -ay)
        dummy = skia.Surface(4, 4).getCanvas()
        CL['rec'] = []
        for op in ob + os_: op[1](dummy, op[2], x, None, None)
        U = None
        for pth in CL['rec']: U = pth if U is None else skia.Op(U, pth, skia.PathOp.kUnion_PathOp)
        CL['rec'] = None
        base = CL['base'][0] if CL['base'] else None; CL['base'] = None
        if U is not None:
            U = soft_shape(drop_small_holes(U), 30.0)
            cv.drawPath(U, paint_stroke(OUTL, OUT_COL))
            if base is not None: cv.drawPath(U, paint_fill(skia.Color4f(base[0] * 0.8, base[1] * 0.8, base[2] * 0.8, 1)))   # fabric fills the softened silhouette
            cv.save(); cv.clipPath(U, doAntiAlias=True)
        CL['soft'] = True
        for op in ob + os_: op[1](cv, op[2], x, None, None)
        if flash > 0:
            for op in ob + os_: op[1](cv, op[2], x, None, skia.Color4f(1, 1, 1, 0.75 * flash))
        CL['soft'] = False
        if U is not None: cv.restore()
        if acc is not None and U is not None:
            cv.save(); cv.clipPath(U, doAntiAlias=True)
            cv.drawPath(U, paint_stroke(9, skia.Color4f(*acc, 0.30))); cv.drawPath(U, paint_stroke(4, skia.Color4f(*acc, 0.95)))
            cv.restore()
        cv.restore()


def draw_piece_layer(cv, t, pieces, layer, times, side, x, hand=None, acc=None):
    for i, pc in enumerate(pieces):
        ops = pc.get(layer)
        if not ops: continue
        an = piece_anim(t, times[i])
        if an is None: continue
        alpha, fly, sc, flash = an
        ax, ay = pc['anchor']
        off = v_mul(v_sub(hand, (ax, ay)), fly) if hand else (side * 120 * fly, -30 * fly)
        cv.save()
        cv.translate(ax + off[0], ay + off[1])
        cv.scale(sc, sc); cv.translate(-ax, -ay)
        for op in ops: op[1](cv, op[2], x, acc, None)
        if flash > 0:
            for op in ops: op[1](cv, op[2], x, acc, skia.Color4f(1, 1, 1, 0.75 * flash))
        cv.restore()

def model_arm(t, side, s, x, sy, db, hand, own):
    S = (x + s * SHO * db, sy - 4 * db)
    if own and t < T_REL + 0.1 and db < 0.5:
        pts, aw = rubber_arm((x, sy), hand, s)
        pts = [S] + pts[1:] if len(pts) == 3 else [S, pts[-1]]
    else:
        pts, aw = arm(S, hand, (s * 0.7, 0.4)), SW
    if len(pts) == 2: pts = [pts[0], v_lerp(pts[0], pts[1], 0.5), pts[1]]
    return pts, aw

def draw_model(cv, b, t, side):
    """side -1: left model (streetwear), side +1: right model (old money).
    The model starts as one torn half (on its own side of the seam) and regrows the other half."""
    kind = 'street' if side < 0 else 'lux'
    acc = ACC_ST if side < 0 else ACC_OM
    x = b['xL'] if side < 0 else b['xR']
    hip = b['hipL'] if side < 0 else b['hipR']
    neck = hip - TORSO; sy = neck + 12; headY = neck - R - 7
    db = b['db']; white = col(0.97)
    times = L_TIMES if side < 0 else R_TIMES
    held = b['GL'] if side < 0 else b['GR']
    ph = b.get('phL') if side < 0 else b.get('phR')
    g = grow(t); grown = g >= 1.0 - 1e-3 and t > T_GROW + 0.5
    gx = b['glance']
    hands = {}; pocket = {}; arms = {}; aws = {}
    for s_ in (-1, 1):
        own = s_ == side
        hands[s_], pocket[s_] = model_hand(t, kind, s_, x, hip, held if own else None)
        arms[s_], aws[s_] = model_arm(t, side, s_, x, sy, db if own else 1.0, hands[s_], own)
    T_NOW[0] = t
    pieces = outfit(kind, x, hip, arms, gx, pocket)
    ts = b['ts']
    stub = (DMAX / 2) * math.exp(-ts / 0.035) * math.cos(ts * 40)
    def grown_side(fn):
        if g <= 0.001: return
        cv.save(); cv.translate(x, 0); cv.scale(g, 1); cv.translate(-x, 0); fn(); cv.restore()
    L = lambda layer: draw_piece_layer(cv, t, pieces, layer, times, side, x, ph, acc)
    # legs
    for s_ in (-1, 1):
        def leg(s_=s_):
            Lr = (x + s_ * 16 * (db if s_ == side else 1.0), hip)
            fx = x + s_ * lerp(10, 24, db if s_ == side else 1.0)
            if s_ == side: fx = b['footL'] if side < 0 else b['footR']
            knee, ankle = ik(Lr, (fx, F - SW / 2 - 4), 92, 92, (s_, -0.1))
            chain(cv, [Lr, knee, ankle, (ankle[0] + s_ * 14, ankle[1] + 2)], SW, white)
        if t >= times[2] - 0.02: continue                         # pants on: legs are the pants
        if s_ == side: leg()
        else: grown_side(leg)
    L('shoes'); L('pants')
    # arms first (behind the torso)
    def trimmed(s_):
        pts = arms[s_]; pk_ = pocket[s_]
        if pk_ <= 0: return pts
        d = v_sub(pts[-1], pts[-2]); l = v_len(d) or 1
        return pts[:-1] + [v_sub(pts[-1], v_mul(d, min(22 * pk_, l * 0.6) / l))]
    # torso + head
    if grown and t >= times[0] - 0.02:
        shape(cv, capsule_v(x, neck, neck + 40, TW), white)        # top on: only the neck shows
    elif grown:
        shape(cv, capsule_v(x, neck, hip, TW), white)
    else:
        shape(cv, half_piece(x, neck, hip, side, stub if g < 0.05 else 0, 'torso'), white)
        grown_side(lambda: shape(cv, half_piece(x, neck, hip, -side, 0, 'torso'), white))
    top_on = t >= times[0] - 0.02                               # artwork top is on: its sleeves are the arms
    if top_on:
        nm_, tp_, tw_, _ = top_art(kind, x, hip, t, pocket); ih_ = art(nm_); h_ = tw_ * ih_.height() / ih_.width()
        for cpt in cuff_points(kind, x, hip, t, pocket):
            dx, dy = math.sin(math.radians(cpt[2])), math.cos(math.radians(cpt[2]))   # follow the sleeve direction
            chain(cv, [(cpt[0] - dx * 5, cpt[1] - dy * 5), (cpt[0] + dx * 9, cpt[1] + dy * 9)], SW - 6, white)
            pass
    for s_ in (-1, 1):
        if top_on: break
        f = lambda s_=s_: chain(cv, trimmed(s_), aws[s_], white)
        if s_ == side or grown: f()
        else: grown_side(f)
    for lay, sl in (('under', 'usleeve'), ('mid', 'msleeve'), ('outer', 'osleeve')):
        draw_garment(cv, t, pieces, lay, sl, times, side, x, ph, acc)
    L('strap')
    if grown:
        shape(cv, circle_path((x + gx, headY), R), white)
    else:
        shape(cv, half_piece(x + gx, headY, None, side, (stub if g < 0.05 else 0) * 0.8, 'head'), white)
        grown_side(lambda: shape(cv, half_piece(x + gx, headY, None, -side, 0, 'head'), white))
    # arms
    def trimmed(s_):
        pts = arms[s_]; pk_ = pocket[s_]
        if pk_ <= 0: return pts
        d = v_sub(pts[-1], pts[-2]); l = v_len(d) or 1
        return pts[:-1] + [v_sub(pts[-1], v_mul(d, min(22 * pk_, l * 0.6) / l))]

    for s_ in (-1, 1):
        hd = hands[s_]; a = 1 - clamp(pocket[s_] * 1.6)
        continue                                                      # no hand balls: arms end rounded
        def hand_draw(hd=hd, a=a):
            cv.drawCircle(hd[0], hd[1], 15 + OUTL / 2, paint_fill(skia.Color4f(0.015, 0.015, 0.02, a)))
            cv.drawCircle(hd[0], hd[1], 15, paint_fill(skia.Color4f(0.97, 0.97, 0.97, a)))
        if s_ == side or grown: hand_draw()
        else: grown_side(hand_draw)
    if kind == 'lux' and WATCH_AT[0] is not None and top_on: watch_on_wrist(cv, (WATCH_AT[0][0], WATCH_AT[0][1] + 1))
    WATCH_AT[0] = None
    L('pocket'); L('acc'); draw_garment(cv, t, pieces, 'drape', 'none', times, side, x, ph, acc); L('collar'); L('hat')
    for i, pc in enumerate(pieces):
        v = t - times[i]
        if 0 <= v < 0.28:
            ax, ay = pc['anchor']
            sparkle(cv, (ax + side * (30 + 50 * ease_out(v / 0.28)), ay - 30 * ease_out(v / 0.28)), 16 * (1 - v / 0.28) + 4, 1 - v / 0.28)
    # regrow pop: ring + sparkles on the new side
    v = t - T_GROW
    if 0 <= v < 0.35:
        u = v / 0.35
        cv.drawCircle(x, (headY + hip) / 2, 40 + 160 * ease_out(u), paint_stroke(5 * (1 - u) + 1, skia.Color4f(*acc, 0.7 * (1 - u))))
        for k in range(4):
            sparkle(cv, (x - side * (40 + 60 * ease_out(u)), headY + k * 70 - 20 * ease_out(u)), 14 * (1 - u) + 3, 1 - u)
    # seam glow (only while torn)
    a = 0.0
    if ts < 1.2: a = (0.35 + 0.65 * math.exp(-ts * 5)) * (1 - sstep((t - T_GROW + 0.06) / 0.08))
    if a > 0.01:
        p = paint_stroke(4, skia.Color4f(1.0, 0.16, 0.16, a))
        cv.drawLine(x, neck - TW / 2 + 4, x, hip + TW / 2 - 4, p)
        cv.drawLine(x + gx, headY - R + 5, x + gx, headY + R - 5, p)

def draw_boyfriend(cv, b, t):
    white = col(0.97)
    if b['snapped']:
        draw_model(cv, b, t, -1); draw_model(cv, b, t, 1); return
    hip, neck, headY, sy = b['hip'], b['neck'], b['head'], b['sy']
    xL, xR = b['xL'], b['xR']
    for side, x, fx in ((-1, xL, b['footL']), (1, xR, b['footR'])):
        knee, ankle = ik((x, hip), (fx, F - SW/2 - 4), THIGH, SHIN, (side, -0.1))
        chain(cv, [(x, hip), knee, ankle, (ankle[0] + side * 14, ankle[1] + 2)], SW, white)
    for side, x, G in ((-1, xL, b['GL']), (1, xR, b['GR'])):
        pts, w = rubber_arm((x, sy), G, side); chain(cv, pts, w, white)
    pin = b['pinch']
    shape(cv, taffy(xL, xR, neck, hip, pin * ((hip - neck + TW) / 2 - 7), 'torso'), white)
    hx = b['glance']
    shape(cv, taffy(xL + hx, xR + hx, headY, None, pin * (R - 4), 'head'), white)

# ---------------- backgrounds (revealed behind the curtains) ----------------
# Drawn once into a cached image. If bg_street.png / bg_oldmoney.png sit next to this
# script, those images are used instead (cover-fit into each half of the frame).
HORIZON = 1000

def _grad_rect(cv, r, p0, p1, cols, pos=None):
    p = skia.Paint(AntiAlias=True)
    p.setShader(skia.GradientShader.MakeLinear([p0, p1], [skia.Color4f(*c).toColor() for c in cols], pos))
    cv.drawRect(r, p)

def _glow(cv, draw_fn, sigma, alpha=1.0):
    p = skia.Paint(); p.setImageFilter(skia.ImageFilters.Blur(sigma, sigma)); p.setAlphaf(alpha)
    p.setBlendMode(skia.BlendMode.kPlus)
    cv.saveLayer(None, p); draw_fn(); cv.restore()

def _persp(d, a=4.0):
    return (1 - 1 / (1 + a * d)) / (1 - 1 / (1 + a))

class Wall:
    """A wall plane receding to a vanishing point: near edge at x0 (top y0t, bottom y0b), far edge at x1."""
    def __init__(s, x0, y0t, y0b, x1, vp):
        s.x0, s.y0t, s.y0b, s.x1, s.vp = x0, y0t, y0b, x1, vp
    def at(s, d, h):   # d: 0 near .. 1 far ; h: 0 top .. 1 bottom
        x = lerp(s.x0, s.x1, _persp(d))
        k = (x - s.x0) / (s.vp[0] - s.x0)
        yt = lerp(s.y0t, s.vp[1], k); yb = lerp(s.y0b, s.vp[1], k)
        return (x, lerp(yt, yb, h))
    def scale(s, d):
        a = s.at(d, 0); b = s.at(d, 1); return (b[1] - a[1]) / (s.y0b - s.y0t)
    def quad(s, d0, d1, h0, h1):
        return [s.at(d0, h0), s.at(d1, h0), s.at(d1, h1), s.at(d0, h1)]
    def poly_uv(s, d0, d1, h0, h1, uv):
        return [s.at(lerp(d0, d1, u), lerp(h0, h1, v)) for u, v in uv]

def draw_street(cv):
    X0, X1 = 0, 540; vp = (430, HORIZON)
    cv.save(); cv.clipRect(skia.Rect.MakeLTRB(X0, 0, X1, H))
    _grad_rect(cv, skia.Rect.MakeLTRB(X0, 0, X1, HORIZON + 10), (0, 0), (0, HORIZON),
               [(0.01, 0.01, 0.03, 1), (0.05, 0.03, 0.09, 1), (0.16, 0.05, 0.16, 1)], [0, 0.6, 1])
    rng = np.random.default_rng(11)
    # skyline down the alley
    for bx, bw, bh in ((300, 70, 380), (360, 60, 560), (412, 54, 470), (458, 70, 640), (520, 60, 420), (330, 40, 250)):
        top = HORIZON - bh
        cv.drawRect(skia.Rect.MakeLTRB(bx, top, bx + bw, HORIZON + 4), paint_fill(rgb(0.035, 0.045, 0.09)))
        cv.drawLine(bx + bw, top, bx + bw, HORIZON, paint_stroke(1.5, rgb(0.20, 0.30, 0.55, 0.5)))
        for wy in range(int(top) + 12, HORIZON - 10, 13):
            for wx in range(bx + 6, bx + bw - 6, 9):
                if rng.random() < 0.32:
                    c = (1.0, 0.82, 0.55, 0.75) if rng.random() < 0.6 else (0.60, 0.80, 1.0, 0.7)
                    cv.drawRect(skia.Rect.MakeXYWH(wx, wy, 4, 6), paint_fill(skia.Color4f(*c)))
        cv.drawCircle(bx + bw / 2, top - 4, 3, paint_fill(rgb(1, 0.2, 0.2)))
    gp = skia.Paint(AntiAlias=True)
    gp.setShader(skia.GradientShader.MakeRadial(vp, 320, [skia.Color4f(1.0, 0.25, 0.6, 0.30).toColor(), skia.Color4f(0, 0, 0, 0).toColor()]))
    cv.drawRect(skia.Rect.MakeLTRB(X0, 0, X1, H), gp)
    # ground: wet asphalt + sidewalk along the wall
    _grad_rect(cv, skia.Rect.MakeLTRB(X0, HORIZON, X1, H), (0, HORIZON), (0, H),
               [(0.07, 0.04, 0.09, 1), (0.03, 0.025, 0.045, 1), (0.015, 0.015, 0.025, 1)], [0, 0.35, 1])
    wall = Wall(-260, -500, 2400, 330, vp)
    curb = Wall(-260, 2400, 2900, 330, vp)
    cv.drawPath(polygon([wall.at(0, 1), wall.at(1, 1), curb.at(1, 1), curb.at(0, 1)]), paint_fill(rgb(0.06, 0.045, 0.07)))
    cv.drawPath(polyline([curb.at(0, 1), curb.at(1, 1)]), paint_stroke(3, rgb(0.30, 0.18, 0.30)))
    # brick wall
    cv.drawPath(polygon(wall.quad(0, 1, 0, 1)), paint_fill(rgb(0.15, 0.055, 0.075)))
    cv.save(); cv.clipPath(polygon(wall.quad(0, 1, 0, 1)), doAntiAlias=True)
    nrow = 70
    for r in range(nrow + 1):
        h = r / nrow
        cv.drawPath(polyline([wall.at(0, h), wall.at(1, h)]), paint_stroke(1.6, rgb(0.06, 0.02, 0.03, 0.9)))
        if r < nrow:
            off = 0.5 if r % 2 else 0.0
            for j in range(26):
                d = (j + off) / 26
                a = wall.at(d, h); b = wall.at(d, h + 1 / nrow)
                cv.drawLine(*a, *b, paint_stroke(1.2, rgb(0.06, 0.02, 0.03, 0.8)))
    for (d0, d1) in ((0.55, 0.62), (0.82, 0.86)):   # doorways
        cv.drawPath(polygon(wall.quad(d0, d1, 0.55, 1.0)), paint_fill(rgb(0.02, 0.01, 0.02)))
        cv.drawPath(polygon(wall.quad(d0, d1, 0.55, 0.57)), paint_fill(rgb(0.30, 0.10, 0.20)))
    _grad_rect(cv, skia.Rect.MakeLTRB(0, 0, 340, H), (0, 0), (340, 0), [(0, 0, 0, 0.0), (0, 0, 0, 0.7)])
    cv.restore()
    # graffiti tags low on the wall (abstract bubble shapes, no real words)
    def tag(d0, d1, h0, h1, fill, edge):
        blobs = [(0.08, 0.5, 0.10, 0.42), (0.21, 0.46, 0.10, 0.46), (0.34, 0.52, 0.09, 0.40), (0.47, 0.47, 0.10, 0.44),
                 (0.60, 0.52, 0.09, 0.40), (0.73, 0.48, 0.09, 0.38)]
        for (u, v, ru, rv) in blobs:
            pts = [(u + ru * math.cos(a), v + rv * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 14)[:-1]]
            pp = wall.poly_uv(d0, d1, h0, h1, pts)
            sh_ = [(p[0] + 4, p[1] + 5) for p in pp]
            cv.drawPath(smooth_path(sh_), paint_fill(skia.Color4f(0, 0, 0, 0.6)))
            cv.drawPath(smooth_path(pp), paint_fill(fill)); cv.drawPath(smooth_path(pp), paint_stroke(3, edge))
            hi = wall.poly_uv(d0, d1, h0, h1, [(u - ru * 0.4, v - rv * 0.5), (u + ru * 0.1, v - rv * 0.7)])
            cv.drawLine(*hi[0], *hi[1], paint_stroke(3, skia.Color4f(1, 1, 1, 0.6)))
        for u in (0.2, 0.55, 0.8):   # drips
            a = wall.at(lerp(d0, d1, u), lerp(h0, h1, 0.9)); b = wall.at(lerp(d0, d1, u), lerp(h0, h1, 1.25))
            cv.drawLine(*a, *b, paint_stroke(2.5, fill))
    tag(0.12, 0.36, 0.60, 0.68, rgb(0.42, 0.62, 0.86), rgb(0.85, 0.90, 1.0))
    tag(0.42, 0.60, 0.64, 0.71, rgb(0.70, 0.70, 0.76), rgb(0.35, 0.70, 0.95))
    # neon crown + lamps (with glow and ground reflections)
    def cmap(u, v):   # crown painted on the wall, mild perspective shear
        return (40 + u * 140, 600 + v * 120 + u * 45)
    def crown_pts():
        uv = [(0.08, 0.78), (0.0, 0.18), (0.30, 0.52), (0.5, 0.0), (0.70, 0.52), (1.0, 0.18), (0.92, 0.78)]
        return [cmap(u, v) for u, v in uv]
    def crown_extra(stroke):
        cv.drawPath(polyline([cmap(0.06, 0.95), cmap(0.94, 0.95)]), stroke)
        for u, v in ((0.0, 0.18), (0.5, 0.0), (1.0, 0.18)):
            c_ = cmap(u, v - 0.10); cv.drawCircle(c_[0], c_[1], 7, stroke)
    def neon():
        cp = crown_pts()
        cv.drawPath(polyline(cp), paint_stroke(9, rgb(1.0, 0.25, 0.62)))
        crown_extra(paint_stroke(9, rgb(1.0, 0.25, 0.62)))
        for d in (0.25, 0.45, 0.62, 0.78):
            a = wall.at(d, 0.22); b = wall.at(d + 0.045, 0.22); sc = wall.scale(d)
            cv.drawLine(*a, *b, paint_stroke(12 * sc + 2, rgb(1.0, 0.35, 0.70)))
    _glow(cv, neon, 26, 0.9); _glow(cv, neon, 8, 0.9)
    cp = crown_pts()
    cv.drawPath(polyline(cp), paint_stroke(4, rgb(1.0, 0.85, 0.95)))
    crown_extra(paint_stroke(4, rgb(1.0, 0.85, 0.95)))
    for d in (0.25, 0.45, 0.62, 0.78):
        a = wall.at(d, 0.22); b = wall.at(d + 0.045, 0.22); sc = wall.scale(d)
        cv.drawLine(*a, *b, paint_stroke(5 * sc + 1, rgb(1.0, 0.92, 0.97)))
        cone = [a, b, wall.at(d + 0.09, 0.55), wall.at(d - 0.05, 0.55)]
        cp_ = skia.Paint(AntiAlias=True)
        cp_.setShader(skia.GradientShader.MakeLinear([a, wall.at(d, 0.55)], [skia.Color4f(1, 0.3, 0.65, 0.35).toColor(), skia.Color4f(1, 0.3, 0.65, 0).toColor()]))
        cv.drawPath(polygon(cone), cp_)
    # reflections on the wet ground
    def refl():
        for d in (0.45, 0.62, 0.78):
            base = wall.at(d + 0.02, 1.0); sc = wall.scale(d)
            r = skia.Rect.MakeXYWH(base[0] + 40 * sc, base[1] + 8, 10 * sc + 5, 300 * sc + 60)
            rp = skia.Paint(AntiAlias=True)
            rp.setShader(skia.GradientShader.MakeLinear([(0, r.top()), (0, r.bottom())], [skia.Color4f(1, 0.3, 0.65, 0.55).toColor(), skia.Color4f(1, 0.3, 0.65, 0).toColor()]))
            cv.drawRect(r, rp)
        for bx in (380, 470, 500): cv.drawRect(skia.Rect.MakeXYWH(bx, HORIZON + 8, 14, 160), paint_fill(rgb(1.0, 0.8, 0.6, 0.10)))
    _glow(cv, refl, 10, 0.8)
    for k in range(9):   # puddle glints
        px = rng.uniform(140, 540); py = rng.uniform(1120, 1880)
        cv.drawOval(skia.Rect.MakeXYWH(px, py, rng.uniform(40, 120), rng.uniform(4, 9)), paint_fill(rgb(1.0, 0.45, 0.75, 0.22)))
    _grad_rect(cv, skia.Rect.MakeLTRB(X0, HORIZON - 120, X1, HORIZON + 140), (0, HORIZON - 120), (0, HORIZON + 140),
               [(0.5, 0.2, 0.5, 0), (0.45, 0.18, 0.45, 0.16), (0.5, 0.2, 0.5, 0)])
    cv.restore()

def leaf_cluster(cv, cx, cy, rad, n, rng, sc=1.0):
    for k in range(n):
        a = rng.uniform(0, 2 * math.pi); r = rad * math.sqrt(rng.random())
        px, py = cx + r * math.cos(a), cy + r * math.sin(a) * 0.8
        c = [rgb(0.24, 0.32, 0.09), rgb(0.48, 0.58, 0.14), rgb(0.78, 0.76, 0.22), rgb(0.62, 0.66, 0.18)][int(rng.integers(0, 4))]
        cv.save(); cv.translate(px, py); cv.rotate(rng.uniform(0, 360))
        L = rng.uniform(8, 15) * sc
        lp = skia.Path(); lp.moveTo(-L, 0); lp.quadTo(0, -L * 0.55, L, 0); lp.quadTo(0, L * 0.55, -L, 0)
        cv.drawPath(lp, paint_fill(c)); cv.drawLine(-L * 0.8, 0, L * 0.8, 0, paint_stroke(0.8, rgb(0.15, 0.2, 0.05, 0.6)))
        cv.restore()

def draw_court(cv):
    X0, X1 = 540, 1080; vp = (650, HORIZON)
    cv.save(); cv.clipRect(skia.Rect.MakeLTRB(X0, 0, X1, H))
    _grad_rect(cv, skia.Rect.MakeLTRB(X0, 0, X1, HORIZON + 10), (0, 0), (0, HORIZON),
               [(0.02, 0.04, 0.10, 1), (0.07, 0.10, 0.20, 1), (0.22, 0.20, 0.26, 1)], [0, 0.6, 1])
    rng = np.random.default_rng(5)
    for k in range(10):   # distant trees
        leaf_cluster(cv, rng.uniform(540, 700), HORIZON - rng.uniform(20, 120), 60, 50, rng, 0.8)
    _grad_rect(cv, skia.Rect.MakeLTRB(X0, HORIZON - 200, X1, HORIZON + 10), (0, HORIZON - 200), (0, HORIZON),
               [(0.05, 0.07, 0.12, 0), (0.05, 0.07, 0.12, 0.6)])
    # stone floor
    floor = [(X0, HORIZON), (X1, HORIZON), (X1, H), (X0, H)]
    _grad_rect(cv, skia.Rect.MakeLTRB(X0, HORIZON, X1, H), (0, HORIZON), (0, H),
               [(0.36, 0.31, 0.25, 1), (0.62, 0.53, 0.42, 1), (0.74, 0.64, 0.50, 1)], [0, 0.4, 1])
    for k in range(-14, 22):   # tile lines toward the vanishing point
        bx = 650 + k * 70
        cv.drawLine(*vp, bx + (bx - 650) * 2.0, H + 200, paint_stroke(1.6, rgb(0.30, 0.25, 0.20, 0.5)))
    for k in range(1, 30):
        y = HORIZON + (H - HORIZON) * (k / 29) ** 2.2
        cv.drawLine(X0, y, X1, y, paint_stroke(1.4, rgb(0.30, 0.25, 0.20, 0.45)))
    # facade
    wall = Wall(1100, -160, 1500, 790, vp)
    cv.drawPath(polygon(wall.quad(0, 1, 0, 1)), paint_fill(rgb(0.86, 0.79, 0.66)))
    cv.save(); cv.clipPath(polygon(wall.quad(0, 1, 0, 1)), doAntiAlias=True)
    for r in range(1, 36):
        cv.drawPath(polyline([wall.at(0, r / 36), wall.at(1, r / 36)]), paint_stroke(1.3, rgb(0.62, 0.55, 0.44, 0.55)))
    cv.drawPath(polygon(wall.quad(0, 1, 0.08, 0.13)), paint_fill(rgb(0.93, 0.88, 0.77)))   # cornice
    cv.drawPath(polygon(wall.quad(0, 1, 0.13, 0.145)), paint_fill(rgb(0.45, 0.38, 0.30)))
    cv.drawPath(polygon(wall.quad(0, 1, 0.84, 0.88)), paint_fill(rgb(0.92, 0.87, 0.76)))    # plinth
    bays = [(0.03, 0.30), (0.40, 0.62), (0.70, 0.85)]
    for (d0, d1) in bays:
        arch = [(0.0, 1.0)] + [(0.5 + 0.5 * math.cos(a), 0.28 - 0.28 * math.sin(a)) for a in np.linspace(math.pi, 0, 24)] + [(1.0, 1.0)]
        frame_ = wall.poly_uv(d0 - 0.025, d1 + 0.025, 0.24, 0.84, [(u, v) for u, v in arch])
        cv.drawPath(polygon(frame_), paint_fill(rgb(0.95, 0.91, 0.82)))
        glass = wall.poly_uv(d0, d1, 0.28, 0.84, arch)
        gp = skia.Paint(AntiAlias=True)
        a_ = wall.at(d0, 0.3); b_ = wall.at(d1, 0.84)
        gp.setShader(skia.GradientShader.MakeLinear([a_, b_], [rgb(0.10, 0.10, 0.12).toColor(), rgb(0.30, 0.22, 0.12).toColor(), rgb(0.06, 0.06, 0.08).toColor()], [0, 0.55, 1]))
        cv.drawPath(polygon(glass), gp)
        for u in (0.33, 0.66):
            cv.drawPath(polyline(wall.poly_uv(d0, d1, 0.28, 0.84, [(u, 0.05), (u, 1.0)])), paint_stroke(3 * wall.scale(d0) + 1, rgb(0.08, 0.07, 0.06)))
        for v in (0.30, 0.52, 0.74):
            cv.drawPath(polyline(wall.poly_uv(d0, d1, 0.28, 0.84, [(0, v), (1, v)])), paint_stroke(3 * wall.scale(d0) + 1, rgb(0.08, 0.07, 0.06)))
        cv.drawPath(polygon(glass), paint_stroke(4 * wall.scale(d0) + 1, rgb(0.10, 0.08, 0.06)))
        refl = wall.poly_uv(d0, d1, 0.28, 0.84, [(0.1, 0.25), (0.3, 0.2), (0.15, 0.9), (0.02, 0.9)])
        cv.drawPath(polygon(refl), paint_fill(skia.Color4f(1.0, 0.85, 0.6, 0.12)))
    _grad_rect(cv, skia.Rect.MakeLTRB(780, 0, 1100, H), (1100, 0), (780, 0), [(0, 0, 0, 0.0), (0.05, 0.03, 0.02, 0.55)])
    cv.restore()
    cv.drawPath(polyline([wall.at(1, 0), wall.at(1, 1)]), paint_stroke(3, rgb(0.55, 0.47, 0.36)))
    # planters with boxwood along the wall
    for d in (0.88, 0.62, 0.33):
        sc = wall.scale(d); base = wall.at(d, 1.0)
        bx = base[0] - 130 * sc; by = base[1] + 20 * sc; w_ = 150 * sc; h_ = 95 * sc
        cv.drawRect(skia.Rect.MakeXYWH(bx + w_, by - h_ + 8 * sc, 26 * sc, h_ - 8 * sc), paint_fill(rgb(0.72, 0.68, 0.60)))
        cv.drawRect(skia.Rect.MakeXYWH(bx, by - h_, w_, h_), paint_fill(rgb(0.93, 0.90, 0.84)))
        cv.drawRect(skia.Rect.MakeXYWH(bx - 4 * sc, by - h_ - 8 * sc, w_ + 8 * sc, 10 * sc), paint_fill(rgb(0.97, 0.95, 0.90)))
        cv.drawRect(skia.Rect.MakeXYWH(bx, by - 6 * sc, w_ + 26 * sc, 6 * sc), paint_fill(rgb(0, 0, 0, 0.25)))
        bp = skia.Paint(AntiAlias=True)
        cxb, cyb, rb = bx + w_ / 2 + 6 * sc, by - h_ - 60 * sc, 80 * sc
        bp.setShader(skia.GradientShader.MakeRadial((cxb - rb * 0.3, cyb - rb * 0.4), rb * 1.4,
                     [rgb(0.62, 0.68, 0.22).toColor(), rgb(0.28, 0.36, 0.10).toColor(), rgb(0.10, 0.15, 0.04).toColor()], [0, 0.55, 1]))
        cv.drawOval(skia.Rect.MakeXYWH(cxb - rb, cyb - rb * 0.85, 2 * rb, rb * 1.7), bp)
        leaf_cluster(cv, cxb - rb * 0.2, cyb - rb * 0.25, rb * 0.85, int(140 * sc) + 20, rng, sc * 0.9)
    # wall lantern with warm glow
    lx, ly = 1010, 520
    def warm():
        cv.drawCircle(lx, ly + 40, 46, paint_fill(rgb(1.0, 0.72, 0.30, 0.9)))
    _glow(cv, warm, 60, 0.9); _glow(cv, warm, 18, 0.6)
    cv.drawLine(1075, ly - 10, lx + 6, ly - 10, paint_stroke(6, rgb(0.08, 0.07, 0.06)))
    cv.drawLine(lx + 6, ly - 10, lx, ly + 4, paint_stroke(5, rgb(0.08, 0.07, 0.06)))
    cv.drawPath(polygon([(lx - 22, ly + 4), (lx + 22, ly + 4), (lx + 28, ly + 14), (lx - 28, ly + 14)]), paint_fill(rgb(0.08, 0.07, 0.06)))
    cv.drawPath(polygon([(lx - 22, ly + 14), (lx + 22, ly + 14), (lx + 18, ly + 72), (lx - 18, ly + 72)]), paint_fill(rgb(1.0, 0.82, 0.48)))
    cv.drawLine(lx, ly + 14, lx, ly + 72, paint_stroke(3, rgb(0.08, 0.07, 0.06)))
    cv.drawPath(polygon([(lx - 22, ly + 14), (lx + 22, ly + 14), (lx + 18, ly + 72), (lx - 18, ly + 72)]), paint_stroke(4, rgb(0.08, 0.07, 0.06)))
    cv.drawPath(polygon([(lx - 24, ly + 72), (lx + 24, ly + 72), (lx + 14, ly + 84), (lx - 14, ly + 84)]), paint_fill(rgb(0.08, 0.07, 0.06)))
    # warm light pool on the floor + ivy hanging from above
    def pool():
        cv.drawOval(skia.Rect.MakeXYWH(760, 1250, 360, 120), paint_fill(rgb(1.0, 0.75, 0.40, 0.35)))
    _glow(cv, pool, 40, 1.0)
    for k in range(16):
        leaf_cluster(cv, rng.uniform(560, 1080), rng.uniform(-20, 170 + 120 * (k % 3 == 0)), 70, 70, rng)
    for k in range(5):
        x0 = rng.uniform(600, 900)
        pts = [(x0, -10), (x0 + rng.uniform(-30, 30), 120), (x0 + rng.uniform(-40, 40), 260)]
        cv.drawPath(smooth_path(pts, closed=False), paint_stroke(2.5, rgb(0.20, 0.16, 0.08)))
        for p in sample_curve(pts, 10)[2:]: leaf_cluster(cv, p[0], p[1], 18, 6, rng)
    gp = skia.Paint(AntiAlias=True)
    gp.setShader(skia.GradientShader.MakeRadial((900, 700), 900, [rgb(1.0, 0.75, 0.4, 0.10).toColor(), rgb(0, 0, 0, 0).toColor()]))
    cv.drawRect(skia.Rect.MakeLTRB(X0, 0, X1, H), gp)
    cv.restore()

def _cover(cv, path, rect):
    img = skia.Image.open(path)
    sc = max(rect.width() / img.width(), rect.height() / img.height())
    w, h = img.width() * sc, img.height() * sc
    cv.save(); cv.clipRect(rect)
    cv.drawImageRect(img, skia.Rect.MakeXYWH(rect.centerX() - w / 2, rect.centerY() - h / 2, w, h), skia.SamplingOptions(skia.FilterMode.kLinear))
    cv.restore()

_BG = None
def background_image():
    global _BG
    if _BG is None:
        surf = skia.Surface(W, H); c = surf.getCanvas(); c.clear(skia.Color4f(0, 0, 0, 1))
        ps, po = os.path.join(HERE, 'bg_left.png'), os.path.join(HERE, 'bg_right.png')
        if os.path.exists(ps): _cover(c, ps, skia.Rect.MakeLTRB(0, 0, W / 2, H))
        else: draw_street(c)
        if os.path.exists(po): _cover(c, po, skia.Rect.MakeLTRB(W / 2, 0, W, H))
        else: draw_court(c)
        _BG = surf.makeImageSnapshot()
    return _BG

RAIN = [(np.random.default_rng(21).uniform(0, 540), u, s_) for u, s_ in zip(np.random.default_rng(22).uniform(0, 1, 140), np.random.default_rng(23).uniform(0.6, 1.0, 140))]
def draw_rain(cv, t):
    cv.save(); cv.clipRect(skia.Rect.MakeLTRB(0, 0, 540, H))
    rr = np.random.default_rng(24); xs = rr.uniform(-40, 560, 140)
    for k, (x0, ph, sp) in enumerate(RAIN):
        y = ((ph + t * 1.6 * sp) % 1.0) * (H + 200) - 100
        x = xs[k] - 0.12 * y * 0.1
        cv.drawLine(x, y, x - 3, y + 40 * sp, paint_stroke(1.6 * sp, skia.Color4f(0.85, 0.80, 0.95, 0.30 * sp)))
    for k in range(18):   # splash ripples on the ground
        ph = (t * 1.3 + k * 0.137) % 1.0
        px = (k * 97.3) % 540; py = 1060 + (k * 211.7) % 820
        r = 6 + 26 * ph
        cv.drawOval(skia.Rect.MakeXYWH(px - r, py - r * 0.22, 2 * r, r * 0.44), paint_stroke(1.4, skia.Color4f(1, 0.7, 0.9, 0.35 * (1 - ph))))
    cv.restore()

def draw_curtains(cv, t, show):
    """Black roller blinds, one per side. show: 0..1 visibility of pleats + hem bar (they sit on the black stage)."""
    yc = curtain_y(t)
    if yc < -150: return
    for x0, x1 in ((0, 540), (540, 1080)):
        r = skia.Rect.MakeLTRB(x0 - 300 if x0 == 0 else x0, -400, x1 + 300 if x1 == 1080 else x1, yc)
        cv.drawRect(r, paint_fill(skia.Color4f(0.008, 0.008, 0.012, 1)))
        if show > 0:
            p = skia.Paint(AntiAlias=True)
            cols = []
            for k in range(13): cols.append(skia.Color4f(1, 1, 1, (0.035 if k % 2 else 0.0) * show).toColor())
            p.setShader(skia.GradientShader.MakeLinear([(x0, 0), (x1, 0)], cols))
            cv.drawRect(r, p)
            hem = skia.Rect.MakeLTRB(r.left(), yc - 16, r.right(), yc)
            cv.drawRect(hem, paint_fill(skia.Color4f(0.10, 0.10, 0.11, show)))
            cv.drawLine(r.left(), yc - 15, r.right(), yc - 15, paint_stroke(2, skia.Color4f(1, 1, 1, 0.22 * show)))
            hx = (S3_BASE + CURT_GX) if x0 == 0 else W - (S3_BASE + CURT_GX)
            cv.drawCircle(hx, yc - 2, 9, paint_stroke(4, skia.Color4f(0.6, 0.6, 0.64, show)))

# ---------------- text ----------------
def text_width(s, size, trk):
    f = skia.Font(FONT, size); return sum(f.measureText(ch) for ch in s) + trk * (len(s) - 1)
def draw_text(cv, s, x, y, size, trk, alpha=1.0, color=(1, 1, 1)):
    f = skia.Font(FONT, size); p = skia.Paint(AntiAlias=True, Color4f=skia.Color4f(*color, alpha))
    for ch in s:
        cv.drawString(ch, x, y, f, p); x += f.measureText(ch) + trk
def text_width_f(s_, size, trk, tf):
    f = skia.Font(tf, size); return sum(f.measureText(ch) for ch in s_) + trk * (len(s_) - 1)
def draw_text_f(cv, s_, x, y, size, trk, alpha, color, tf):
    f = skia.Font(tf, size); p = skia.Paint(AntiAlias=True, Color4f=skia.Color4f(*color, alpha))
    for ch in s_:
        cv.drawString(ch, x, y, f, p); x += f.measureText(ch) + trk

def draw_arrow(cv, x0, x1, y, alpha, red=True):
    c = skia.Color4f(1, 0.2, 0.2, alpha) if red else skia.Color4f(1, 1, 1, alpha)
    p = paint_stroke(5, c)
    cv.drawLine(x0, y, x1, y, p)
    d = 1 if x1 > x0 else -1
    cv.drawLine(x1, y, x1 - d * 13, y - 11, p); cv.drawLine(x1, y, x1 - d * 13, y + 11, p)

# ---------------- scene ----------------
rng = np.random.default_rng(7)
DUST = [(rng.uniform(0, W), rng.uniform(150, 1800), rng.uniform(0.8, 2.6), rng.uniform(-6, 6), rng.uniform(-14, -4), rng.uniform(0.15, 0.55)) for _ in range(70)]
BURST = [(rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(180, 620), rng.uniform(1.5, 3.5)) for _ in range(40)]

layer = skia.Surface(W, H); small = skia.Surface(W // 4, H // 4); med = skia.Surface(W // 2, H // 2)
tsurf = skia.Surface(W, H); main = skia.Surface(W, H); msurf = skia.Surface(W, H)

FWD_S, FWD_DY = 1.25, 200       # final scale + how far down the floor the models end up (feet at F + FWD_DY)
def fwd(cv, t):
    """Step forward: from the stage line (F) to the front of the revealed floor, scaled about the centre seam."""
    u = sstep((t - T_YANK) / (T_UP + 0.25 - T_YANK))
    if u <= 0: return
    s_ = 1 + (FWD_S - 1) * u
    cv.translate(W / 2, F + FWD_DY * u); cv.scale(s_, s_); cv.translate(-W / 2, -F)

def camera(t):
    z = 1.06 + 0.06 * sstep(t / T_SNAP) - 0.06 * sstep((t - T_SNAP) / 0.7)
    z += 0.10 * sstep((t - 10.8) / 3.4)
    sx = sy = 0.0
    events = [(T_GRAB, 6, 14), (T_SNAP, 22, 9), (T_GROW, 6, 14), (3.42, 5, 16), (T_SHOVE, 5, 16), (T_YANK + 0.1, 10, 11)] + [(tk, 4, 18) for tk in L_TIMES]
    for t0, amp, dec in events:
        if t >= t0 and t - t0 < 0.6:
            k = amp * math.exp(-(t - t0) * dec)
            sx += k * math.sin((t - t0) * 83); sy += k * math.cos((t - t0) * 71)
    return z, sx, sy, 1150

def sparkle(cv, c, s, a):
    p = paint_stroke(3, skia.Color4f(1, 1, 1, a))
    cv.drawLine(c[0] - s, c[1], c[0] + s, c[1], p); cv.drawLine(c[0], c[1] - s, c[0], c[1] + s, p)
    p2 = paint_stroke(2, skia.Color4f(1, 1, 1, a * 0.7)); s2 = s * 0.55
    cv.drawLine(c[0] - s2, c[1] - s2, c[0] + s2, c[1] + s2, p2); cv.drawLine(c[0] - s2, c[1] + s2, c[0] + s2, c[1] - s2, p2)

def glow_text_pass(cv, timg, strength=0.8, sigma=5):
    mc = med.getCanvas(); mc.clear(skia.Color4f(0, 0, 0, 0))
    bp = skia.Paint(); bp.setImageFilter(skia.ImageFilters.Blur(sigma, sigma))
    mc.save(); mc.scale(0.5, 0.5); mc.drawImage(timg, 0, 0, skia.SamplingOptions(skia.FilterMode.kLinear), bp); mc.restore()
    cv.drawImageRect(med.makeImageSnapshot(), skia.Rect.MakeWH(W, H), skia.SamplingOptions(skia.FilterMode.kLinear), skia.Paint(Alpha=int(255 * strength), BlendMode=skia.BlendMode.kPlus))

TITLE_Y = 565; SUB_Y = 610

def shadow_pass(cv, timg, sigma=9, alpha=0.85):
    p = skia.Paint(); p.setAlphaf(alpha)
    p.setColorFilter(skia.ColorFilters.Blend(skia.Color4f(0, 0, 0, 1).toColor(), skia.BlendMode.kSrcIn))
    p.setImageFilter(skia.ImageFilters.Blur(sigma, sigma))
    cv.drawImage(timg, 0, 4, skia.SamplingOptions(), p)


def round1_banner(c, cx, cy, sc, a):
    """Simple light-gold pill holder with dark ROUND 1 text (sits over the centre split line)."""
    if a <= 0.01: return
    c.save(); c.translate(cx, cy); c.scale(sc, sc)
    tw = text_width('ROUND 1', 40, 5); w, h = tw + 64, 66
    rr = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-w / 2, -h / 2, w, h), h / 2, h / 2)
    c.drawRRect(rr, paint_fill(skia.Color4f(0.96, 0.84, 0.52, a)))
    draw_text(c, 'ROUND 1', -tw / 2, 14, 40, 5, a, (0.10, 0.08, 0.04))
    c.restore()


def dressed(t, times):
    """0..1: how much of the outfit is on (glow builds up piece by piece, full in the final pose)."""
    return sum(clamp((t - tk + 0.05) / 0.3) for tk in times) / len(times)

def fit_glow(cv, mimg, t):
    """Soft colour glow around each model: neon pink (skater, left), warm amber (vintage, right)."""
    for (x0, x1), colr, times in (((0, W / 2), GLOW_L, L_TIMES), ((W / 2, W), GLOW_R, R_TIMES)):
        k = dressed(t, times) * (0.75 + 0.25 * pose_u(t))
        if k <= 0.01: continue
        cv.save(); cv.clipRect(skia.Rect.MakeLTRB(x0, -400, x1, H + 400))
        for sig, a_ in ((28, 0.55), (10, 0.45)):
            p = skia.Paint(); p.setColorFilter(skia.ColorFilters.Blend(skia.Color4f(*colr, 1).toColor(), skia.BlendMode.kSrcIn))
            p.setImageFilter(skia.ImageFilters.Blur(sig, sig)); p.setAlphaf(a_ * k)
            cv.drawImage(mimg, 0, 0, skia.SamplingOptions(), p)
        cv.restore()

def render(t):
    b = bf_state(t)
    ht = max(0, t - 0.07); bh = bf_state(ht)
    g = gf_state(t, b, 0.0, L_TIMES, 'street'); gh = gf_state(ht, bh, 0.0, L_TIMES, 'street')
    fr = gf_state(t, b, 1.7, R_TIMES, 'lux'); fh = gf_state(ht, bh, 1.7, R_TIMES, 'lux')
    bff = mirror_state(fr); bffh = mirror_state(fh)
    if b['snapped']:
        if t < T_REL:
            b['GL'] = g['G']; b['GR'] = bff['G']
        else:
            gr = ghold_world(T_REL - 1e-3, L_TIMES, 'street', 0.0)
            b['GL'] = gr; b['GR'] = (W - gr[0], gr[1])
        b['phL'] = hand_world(g); b['phR'] = hand_world(bff)

    lc = layer.getCanvas(); lc.clear(skia.Color4f(0, 0, 0, 0))
    rx = rack_x(t)
    if rx > -300:
        draw_rack(lc, rx, t, L_TIMES, ICONS_L)
        lc.save(); lc.translate(W, 0); lc.scale(-1, 1)
        draw_rack(lc, rx, t, R_TIMES, ICONS_R)
        lc.restore()
    pf = sstep((t - T_POOF) / 0.16)
    if pf < 1:
        for s_, d_, accs, hist in ((g, 1, 'cap', gh['head']), (bff, -1, 'pony', bffh['head'])):
            c_ = v_lerp(s_['hip'], s_['neck'], 0.4)
            lc.save(); lc.translate(*c_); lc.scale(1 - pf + 0.12 * math.sin(pf * math.pi), 1 - pf); lc.translate(-c_[0], -c_[1])
            draw_profile(lc, s_, d_, 0.80, accs, hist)
            lc.restore()
    mc = msurf.getCanvas(); mc.clear(skia.Color4f(0, 0, 0, 0))
    draw_boyfriend(mc, b, t)
    mimg = msurf.makeImageSnapshot(); lc.drawImage(mimg, 0, 0)
    if t < T_REL:
        for s_ in (g, bff):
            d_ = 1 if s_ is g else -1
            lc.save(); f = eff_face(s_['face']); lc.translate(s_['hip'][0], 0); lc.scale(f, 1); lc.translate(-s_['hip'][0], 0)
            chain(lc, arm(s_['sh'], s_['G'], s_['hint_n']), SW, col(0.80)); lc.restore()
    for s_, icons, sd in ((g, ICONS_L, 1), (bff, ICONS_R, -1)):
        if s_['carry'] is not None and t < T_S3END:
            hw = hand_world(s_)
            k = s_['carry']
            if icons[k] in ('sk_shoe', 'vt_boot'): pos = (hw[0], hw[1] - 6)
            else: pos = (hw[0], hw[1] - 8)
            draw_icon(lc, icons[k], pos, 0.9)
            lc.drawCircle(hw[0], hw[1], 12, paint_fill(col(0.80)))
    img = layer.makeImageSnapshot()

    cv = main.getCanvas()
    cv.clear(skia.Color4f(0.005, 0.005, 0.008, 1))
    z, shx, shy, cy = camera(t)
    cv.save()
    cv.translate(W/2 + shx, cy + shy); cv.scale(z, z); cv.translate(-W/2, -cy)
    ff = sstep((t - T_YANK - 0.04) / 0.30)          # stage floor -> world ground
    if t > T_YANK - 0.02:
        bgi = background_image()
        cv.drawImage(bgi, 0, 0)
        draw_rain(cv, t)
    if ff < 1:
        fp = skia.Paint(AntiAlias=True); fp.setAlphaf(1 - ff)
        fp.setShader(skia.GradientShader.MakeLinear([(0, F), (0, F + 520)], [skia.Color4f(0.075, 0.075, 0.08, 1).toColor(), skia.Color4f(0.01, 0.01, 0.012, 1).toColor()]))
        cv.drawRect(skia.Rect.MakeLTRB(-300, F, W + 300, H + 300), fp)
        hp = skia.Paint(AntiAlias=True); hp.setAlphaf(1 - ff)
        hp.setShader(skia.GradientShader.MakeLinear([(0, 0), (W, 0)], [0x00FFFFFF, 0x2EFFFFFF, 0x00FFFFFF]))
        cv.drawRect(skia.Rect.MakeLTRB(-300, F - 1, W + 300, F + 1), hp)
    draw_curtains(cv, t, sstep((t - 3.0) / 0.5))
    cv.save(); fwd(cv, t)                       # models step forward onto the floor as the backgrounds come up
    if t > T_YANK - 0.02:
        sh_ = paint_fill(skia.Color4f(0, 0, 0, 0.45 * ff)); sh_.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 10))
        for mx in (b['xL'], b['xR']): cv.drawOval(skia.Rect.MakeXYWH(mx - 80, F - 12, 160, 26), sh_)
    cv.saveLayer()
    cv.save(); cv.translate(0, 2 * F); cv.scale(1, -1)
    cv.drawImage(img, 0, 0, skia.SamplingOptions(), skia.Paint(AntiAlias=True, Alpha=int(255 * 0.30)))
    cv.restore()
    mp = skia.Paint(BlendMode=skia.BlendMode.kDstIn)
    mp.setShader(skia.GradientShader.MakeLinear([(0, F), (0, F + 300)], [0xFFFFFFFF, 0x00FFFFFF]))
    cv.drawRect(skia.Rect.MakeLTRB(-300, F, W + 300, H + 400), mp)
    cv.restore()
    fit_glow(cv, mimg, t)
    sc = small.getCanvas(); sc.clear(skia.Color4f(0, 0, 0, 0))
    sp = skia.Paint(); sp.setImageFilter(skia.ImageFilters.Blur(9, 9))
    sc.save(); sc.scale(0.25, 0.25); sc.drawImage(img, 0, 0, skia.SamplingOptions(skia.FilterMode.kLinear), sp); sc.restore()
    mc = med.getCanvas(); mc.clear(skia.Color4f(0, 0, 0, 0))
    mp2 = skia.Paint(); mp2.setImageFilter(skia.ImageFilters.Blur(4, 4))
    mc.save(); mc.scale(0.5, 0.5); mc.drawImage(img, 0, 0, skia.SamplingOptions(skia.FilterMode.kLinear), mp2); mc.restore()
    cv.drawImageRect(small.makeImageSnapshot(), skia.Rect.MakeWH(W, H), skia.SamplingOptions(skia.FilterMode.kLinear), skia.Paint(Alpha=int(255 * 0.75), BlendMode=skia.BlendMode.kPlus))
    cv.drawImageRect(med.makeImageSnapshot(), skia.Rect.MakeWH(W, H), skia.SamplingOptions(skia.FilterMode.kLinear), skia.Paint(Alpha=int(255 * 0.35), BlendMode=skia.BlendMode.kPlus))
    cv.drawImage(img, 0, 0)
    cv.restore()
    for t0, rmax, dur, burst in ((T_SNAP, 900, 0.45, True),):
        v = t - t0
        if 0 <= v < dur:
            yy = (b['hipL'] - TORSO + b['hipL']) / 2
            rr = 30 + rmax * ease_out(v / dur)
            cv.drawCircle(CX, yy, rr, paint_stroke(6 * (1 - v / dur) + 1, skia.Color4f(1, 1, 1, 0.5 * (1 - v / dur))))
            if burst:
                for (dx, dy, spd, sz) in BURST:
                    l = math.hypot(dx, dy) or 1
                    px = CX + dx / l * spd * ease_out(v / dur); py = yy + dy / l * spd * ease_out(v / dur) + 300 * v * v
                    red = dx < 0
                    cv.drawCircle(px, py, sz, paint_fill(skia.Color4f(1, 0.3 if red else 1, 0.3 if red else 1, 1 - v / dur)))
    cv.restore()

    for (x, y, r, vx, vy, a) in DUST:
        cv.drawCircle((x + vx * t) % W, (y + vy * t) % H, r, paint_fill(skia.Color4f(1, 1, 1, a * 0.5)))
    if T_SNAP + 0.06 < t:
        u = ease_out((t - T_SNAP - 0.06) / 0.35)
        half = (H / 2) * u; k = 1 - 0.55 * sstep((t - T_YANK) / 0.4)
        cv.drawLine(CX, H/2 - half, CX, H/2 + half, paint_stroke(14, skia.Color4f(1, 1, 1, 0.12 * k)))
        cv.drawLine(CX, H/2 - half, CX, H/2 + half, paint_stroke(3, skia.Color4f(1, 1, 1, 0.85 * k)))
    if 0 <= t - T_POOF < 0.45:   # stylists vanish in a puff
        v = (t - T_POOF) / 0.45
        for cx_ in (gf_hipx(T_POOF), W - gf_hipx(T_POOF)):
            cv.save(); fwd(cv, t)
            for k_ in range(9):
                a_ = k_ / 9 * 2 * math.pi + 0.4
                pr = 20 + 90 * ease_out(v)
                cv.drawCircle(cx_ + math.cos(a_) * pr, F - 230 + math.sin(a_) * pr * 0.9, 16 * (1 - v) + 4, paint_fill(skia.Color4f(1, 1, 1, 0.55 * (1 - v))))
            cv.restore()

    # ---- text ----
    tc = tsurf.getCanvas(); tc.clear(skia.Color4f(0, 0, 0, 0))
    size, trk = 42, 4
    words = [NAME_L, 'VS', NAME_R]; space = 26
    widths = [text_width(w_, size, trk) for w_ in words]
    total = sum(widths) + space * 2; x0 = W/2 - total/2
    pos = [x0, x0 + widths[0] + space, x0 + widths[0] + widths[1] + 2 * space]
    reveal = clamp((t - 0.05) / 0.45)
    split = ease_out((t - T_SNAP - 0.12) / 0.4) if t > T_SNAP else 0
    tgt = [W/4 - widths[0]/2, W/2 - widths[1]/2, 3*W/4 - widths[2]/2]
    fade_lab = 1 - sstep((t - 9.05) / 0.35)
    shown = int(reveal * sum(len(w_) for w_ in words) + 0.999); cum = 0
    if fade_lab > 0:
        for i, w_ in enumerate(words):
            n = clamp(shown - cum, 0, len(w_)); cum += len(w_)
            txt = w_[:int(n)]
            if not txt: continue
            a = (1 - split) if i == 1 else 1.0
            draw_text(tc, txt, lerp(pos[i], tgt[i], split), TITLE_Y, size, trk, a * fade_lab)
        ra = clamp((t - 0.05) / 0.2) * fade_lab                        # ROUND 1 tag above the title
        rs = 1 + 0.4 * math.exp(-max(0, t - 0.05) * 12)
        round1_banner(tc, W/2, TITLE_Y - 84, rs, ra)
        ul = ease_out((t - T_SNAP - 0.3) / 0.35) * fade_lab
        if ul > 0:   # neon underlines
            for i_, cxx, c_ in ((0, W/4, ACC_TXT_L), (2, 3*W/4, ACC_TXT_R)):
                hw = widths[i_] / 2 * ul
                tc.drawLine(cxx - hw, TITLE_Y + 22, cxx + hw, TITLE_Y + 22, paint_stroke(4, skia.Color4f(*c_, 1)))
    if fade_lab > 0 and t > 3.5:
        for items, times, cxx in ((ITEM_L, L_TIMES, W/4), (ITEM_R, R_TIMES, 3*W/4)):
            for i, (name, c) in enumerate(items):
                v = t - times[i]
                if v < 0: continue
                txt = '+ ' + name
                ww = text_width_f(txt, 27, 3, FONT_LIGHT)
                a = clamp(v / 0.06) * fade_lab
                pop = 1 + 0.35 * math.exp(-v * 16) * math.cos(v * 26)
                yy = 640 + i * 34
                tc.save(); tc.translate(cxx, yy - 9); tc.scale(pop, pop)
                draw_text_f(tc, txt, -ww/2, 9, 27, 3, a, c, FONT_LIGHT)
                tc.restore()
    if T_GRAB + 0.02 < t < 1.35:
        u = t - T_GRAB - 0.02
        s_ = 1 + 0.6 * math.exp(-u * 14) * math.cos(u * 30)
        tc.save(); tc.translate(CX + 58, b['head'] - 60); tc.scale(s_, s_)
        draw_text(tc, '!?', -10, 0, 46, 4, clamp(1 - (t - 1.1) / 0.25)); tc.restore()
    timg = tsurf.makeImageSnapshot()
    glow_text_pass(cv, timg, 0.35, 6)
    cv.drawImage(timg, 0, 0)

    # ---- final question: punch-in, big, centred in safe zone ----
    if t > T_Q:
        v = t - T_Q
        qc = tsurf.getCanvas(); qc.clear(skia.Color4f(0, 0, 0, 0))
        qs, qt = 68, 3
        l1, l2 = 'WHICH ONE', 'ARE YOU'
        w1 = text_width(l1, qs, qt); w2 = text_width(l2 + '?', qs, qt)
        sc_ = 1 + 0.55 * math.exp(-v * 13) * math.cos(v * 22) if v < 0.6 else 1.0
        a = clamp(v / 0.05)
        qc.save(); qc.translate(W/2, 640); qc.scale(sc_, sc_)
        round1_banner(qc, 0, -118, 0.92, a)
        draw_text(qc, l1, -w1/2, -14, qs, qt, a)
        draw_text(qc, l2, -w2/2, 62, qs, qt, a)
        draw_text(qc, '?', -w2/2 + text_width(l2, qs, qt) + qt, 62, qs, qt, a, (1.0, 0.22, 0.22))
        qc.restore()
        if v > 0.42:
            u1 = ease_out((v - 0.42) / 0.2); u2 = ease_out((v - 0.62) / 0.2)
            s2, t2 = 30, 3
            ya = 790
            for txt, cxx, u_, c_, d_ in ((NAME_L, b['xL'], u1, ACC_TXT_L, -1), (NAME_R, b['xR'], u2, ACC_TXT_R, 1)):
                if u_ <= 0: continue
                ww = text_width(txt, s2, t2)
                draw_text(qc, txt, cxx - ww/2 + d_ * 30 * (1 - u_), ya, s2, t2, u_)
                qc.drawLine(cxx - ww/2 * u_, ya + 16, cxx + ww/2 * u_, ya + 16, paint_stroke(4, skia.Color4f(*c_, u_)))
        qimg = tsurf.makeImageSnapshot()
        if v < 0.3:
            cv.drawCircle(W/2, 640, 420, paint_fill(skia.Color4f(1, 1, 1, 0.10 * (1 - v / 0.3))))
        shadow_pass(cv, qimg)
        glow_text_pass(cv, qimg, 0.35, 10)
        cv.drawImage(qimg, 0, 0)

    for t0, amp, dur in ((T_SNAP, 0.38, 0.14), (T_YANK + 0.12, 0.16, 0.16)):
        if 0 <= t - t0 < dur:
            cv.drawRect(skia.Rect.MakeWH(W, H), paint_fill(skia.Color4f(1, 1, 1, amp * (1 - (t - t0) / dur))))
    vp = skia.Paint()
    vp.setShader(skia.GradientShader.MakeRadial((W/2, H*0.55), H*0.75, [0x00000000, 0x00000000, 0xC0000000], [0, 0.55, 1.0]))
    cv.drawRect(skia.Rect.MakeWH(W, H), vp)
    fade_in = sstep(t / 0.25)
    if fade_in < 1: cv.drawRect(skia.Rect.MakeWH(W, H), paint_fill(skia.Color4f(0, 0, 0, 1 - fade_in)))
    return main.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)

def samples(t):
    if T_GRAB - 0.03 < t < T_PULL + 0.08: return 3
    if T_SNAP - 0.03 < t < T_SNAP + 0.5: return 3
    if 2.9 < t < T_S3END: return 2
    if T_SHOVE - 0.1 < t < T_UP + 0.1: return 3
    if T_Q - 0.02 < t < T_Q + 0.3: return 2
    return 1

def frame(t):
    n = samples(t)
    if n == 1: return render(t).astype(np.float32)
    acc = None; shutter = 0.5 / FPS
    for k in range(n):
        a = render(max(0, t + (k / (n - 1) - 0.5) * shutter)).astype(np.float32)
        acc = a if acc is None else acc + a
    return acc / n

if __name__ == '__main__':
    from PIL import Image
    mode = sys.argv[1]
    if mode == 'stills':
        for t in [float(x) for x in sys.argv[2:]]:
            Image.fromarray(render(t)).save(os.path.join(HERE, f'still_{t:.2f}.png'))
    elif mode == 'chunk':
        os.makedirs(os.path.join(HERE, 'frames'), exist_ok=True)
        a0, a1 = int(sys.argv[2]), int(sys.argv[3])
        for i in range(a0, min(a1, int(DUR * FPS))):
            if os.path.exists(os.path.join(HERE, 'frames', f'f{i:04d}.png')): continue
            a = frame(i / FPS) + np.random.default_rng(i % 6).normal(0, 3.2, (H, W, 1)).astype(np.float32)
            Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(os.path.join(HERE, 'frames', f'f{i:04d}.png'), compress_level=1)
        print('chunk done', a0, a1)
