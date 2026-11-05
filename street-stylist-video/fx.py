"""Comic FX in the same art style: pop-up text, sweat drops, anger marks, stars, sparkles, notes, dust, speed lines."""
import math, random, cairo
from rig import BLACK


def ease_out_back(x, k=1.7):
    x = min(max(x, 0), 1); x -= 1
    return 1 + (k + 1) * x ** 3 + k * x ** 2


def pop_scale(dt, dur):
    """0->overshoot->1, then quick shrink at end"""
    if dt < 0 or dt > dur: return 0.0
    s = ease_out_back(dt / 0.16, 2.2)
    if dur - dt < 0.12: s *= max(0.0, (dur - dt) / 0.12) ** 0.7
    return s


def rrect(ctx, x, y, w, h, r):
    ctx.new_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0); ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi); ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()


def outlined_fill(ctx, color, lw, shadow=(5, 5)):
    path = ctx.copy_path()
    ctx.save(); ctx.translate(*shadow); ctx.new_path(); ctx.append_path(path)
    ctx.set_source_rgb(*BLACK); ctx.set_line_width(lw); ctx.fill_preserve(); ctx.stroke(); ctx.restore()
    ctx.new_path(); ctx.append_path(path); ctx.set_source_rgb(*BLACK); ctx.set_line_width(lw)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND); ctx.stroke_preserve(); ctx.set_source_rgb(*color); ctx.fill()


def comic_text(ctx, text, x, y, size, scale=1.0, rot=0.0, fill=(1, 1, 1), stroke_w=None,
               weight=cairo.FONT_WEIGHT_BOLD, alpha=1.0, font="Inter Display Black"):
    if scale <= 0.01: return
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.scale(scale, scale)
    ctx.select_font_face(font, cairo.FONT_SLANT_NORMAL, weight); ctx.set_font_size(size)
    ext = ctx.text_extents(text)
    ox, oy = -ext.width / 2 - ext.x_bearing, -ext.height / 2 - ext.y_bearing
    sw = stroke_w if stroke_w is not None else size * 0.16
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.push_group()
    for (dx, dy, st) in ((size * 0.05, size * 0.06, True), (0, 0, True)):
        ctx.new_path(); ctx.move_to(ox + dx, oy + dy); ctx.text_path(text)
        ctx.set_source_rgb(*BLACK); ctx.set_line_width(sw); ctx.stroke_preserve(); ctx.fill()
    ctx.new_path(); ctx.move_to(ox, oy); ctx.text_path(text); ctx.set_source_rgb(*fill); ctx.fill()
    ctx.pop_group_to_source(); ctx.paint_with_alpha(alpha)
    ctx.restore()


def pop_text(ctx, t, t0, dur, text, x, y, size, rot=0.0, fill=(1, 1, 1), wobble=0.04, rise=0.0, font="Inter Display Black"):
    dt = t - t0; s = pop_scale(dt, dur)
    if s <= 0: return
    r = rot + wobble * math.sin(dt * 18)
    comic_text(ctx, text, x, y - rise * dt, size, s, r, fill, font=font)


def sweat_drop(ctx, x, y, s=1.0, alpha=1.0):
    if s < 0.02: return
    ctx.save(); ctx.translate(x, y); ctx.scale(s, s)
    ctx.new_path(); ctx.move_to(0, -26); ctx.curve_to(10, -6, 16, 4, 16, 12); ctx.arc(0, 12, 16, 0, math.pi)
    ctx.curve_to(-16, 4, -10, -6, 0, -26); ctx.close_path()
    ctx.push_group(); outlined_fill(ctx, (0.62, 0.84, 1.0), 6, (2, 3))
    ctx.new_path(); ctx.arc(-5, 10, 4, 0, 2 * math.pi); ctx.set_source_rgb(1, 1, 1); ctx.fill()
    ctx.pop_group_to_source(); ctx.paint_with_alpha(alpha); ctx.restore()


def sweat_pop(ctx, t, t0, dur, x, y, s=1.0):
    dt = t - t0
    if dt < 0 or dt > dur: return
    sc = pop_scale(dt, dur) * s
    sweat_drop(ctx, x, y + 40 * dt, sc)


def anger_mark(ctx, x, y, s=1.0, rot=0.0):
    if s < 0.02: return
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.scale(s, s)
    for k in range(4):
        ctx.save(); ctx.rotate(k * math.pi / 2)
        ctx.new_path(); ctx.move_to(8, -30); ctx.curve_to(8, -12, 12, -8, 30, -8)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_source_rgb(*BLACK); ctx.set_line_width(17); ctx.stroke_preserve()
        ctx.set_source_rgb(0.95, 0.18, 0.2); ctx.set_line_width(9); ctx.stroke()
        ctx.restore()
    ctx.restore()


def anger_pop(ctx, t, t0, dur, x, y, s=1.0):
    sc = pop_scale(t - t0, dur)
    if sc > 0: anger_mark(ctx, x, y, s * sc * (1 + 0.12 * math.sin((t - t0) * 30)))


def star_shape(ctx, x, y, r, rot=0.0, color=(1.0, 0.86, 0.25)):
    if r < 1: return
    ctx.new_path()
    for i in range(10):
        a = rot + i * math.pi / 5 - math.pi / 2
        rr = r if i % 2 == 0 else r * 0.45
        (ctx.move_to if i == 0 else ctx.line_to)(x + rr * math.cos(a), y + rr * math.sin(a))
    ctx.close_path(); outlined_fill(ctx, color, 6, (2, 3))


def dizzy_stars(ctx, t, t0, dur, cx, cy, rx=70, ry=22):
    dt = t - t0
    if dt < 0 or dt > dur: return
    sc = pop_scale(dt, dur)
    for i in range(3):
        a = dt * 9 + i * 2 * math.pi / 3
        star_shape(ctx, cx + rx * math.cos(a), cy + ry * math.sin(a), 20 * sc, a)


def sparkle(ctx, x, y, r, alpha=1.0):
    if r < 1: return
    ctx.save(); ctx.new_path()
    ctx.move_to(x, y - r); ctx.curve_to(x, y, x, y, x + r, y); ctx.curve_to(x, y, x, y, x, y + r)
    ctx.curve_to(x, y, x, y, x - r, y); ctx.curve_to(x, y, x, y, x, y - r); ctx.close_path()
    ctx.push_group(); outlined_fill(ctx, (1, 1, 1), 5, (1, 2)); ctx.pop_group_to_source(); ctx.paint_with_alpha(alpha)
    ctx.restore()


def music_note(ctx, x, y, s=1.0, alpha=1.0, double=False):
    comic_text(ctx, "♫" if double else "♪", x, y, 70 * s, 1.0, 0.0, (1, 1, 1), font="DejaVu Sans", alpha=alpha)


def dust_puff(ctx, t, t0, dur, x, y, s=1.0, n=6, seed=1):
    dt = t - t0
    if dt < 0 or dt > dur: return
    k = dt / dur; rng = random.Random(seed)
    for i in range(n):
        a = math.pi + (i / (n - 1)) * math.pi + rng.uniform(-0.2, 0.2)
        d = (30 + 90 * k) * s * rng.uniform(0.7, 1.2)
        r = (18 + 26 * k) * s * rng.uniform(0.7, 1.2) * (1 - k * 0.5)
        ctx.new_path(); ctx.arc(x + d * math.cos(a) * 1.4, y + d * math.sin(a) * 0.5, r, 0, 2 * math.pi)
        ctx.set_source_rgba(0.94, 0.94, 0.95, 0.9 * (1 - k)); ctx.fill_preserve()
        ctx.set_source_rgba(0, 0, 0, 0.55 * (1 - k)); ctx.set_line_width(4); ctx.stroke()


def speed_lines(ctx, x, y, direction, alpha=1.0, seed=0, length=150):
    rng = random.Random(seed)
    for i in range(4):
        yy = y + rng.uniform(-150, 120); L = length * rng.uniform(0.6, 1.2); xx = x - direction * rng.uniform(40, 90)
        ctx.new_path(); ctx.move_to(xx, yy); ctx.line_to(xx - direction * L, yy)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_source_rgba(0, 0, 0, alpha * 0.8); ctx.set_line_width(12); ctx.stroke_preserve()
        ctx.set_source_rgba(1, 1, 1, alpha); ctx.set_line_width(6); ctx.stroke()
