"""Resample a final-pose top into the pixel frame of its sheet top (same scale + origin), so the code can swap them."""
import sys, os, numpy as np
from PIL import Image
P = sys.argv[1]; ref_n, raw_n, out_n, frac = sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5])
A = os.path.join(P, 'art')
ref = Image.open(os.path.join(A, ref_n + '.png')); raw = Image.open(os.path.join(A, raw_n + '.png'))
ra = np.array(ref)[..., 3] > 40
k = 0.25
def mask(im, s, w, h):
    return np.array(im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR))[..., 3] > 40
R = mask(ref, k, 0, 0); hR = int(R.shape[0] * frac); Rt = R[:hR]
best = None
for s in np.arange(0.50, 1.15, 0.01):
    M = mask(raw, s * k, 0, 0)
    for dy in range(-12, 13):
        for dx in range(-14, 15):
            # place M at (dx, dy) in R's frame, compare top region
            C = np.zeros_like(Rt)
            y0, x0 = dy, dx
            ys = slice(max(0, y0), min(hR, y0 + M.shape[0])); xs = slice(max(0, x0), min(R.shape[1], x0 + M.shape[1]))
            if ys.stop <= ys.start or xs.stop <= xs.start: continue
            C[ys, xs] = M[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0]
            iou = (C & Rt).sum() / max(1, (C | Rt).sum())
            if best is None or iou > best[0]: best = (iou, s, dx / k, dy / k)
iou, s, dx, dy = best; print(out_n, 'iou %.3f scale %.3f dx %.1f dy %.1f' % best)
sc = raw.resize((int(raw.width * s), int(raw.height * s)), Image.LANCZOS)
PAD = int(round(ref.width * 0.12))                       # both get the same side margins (bent sleeves stick out)
H = max(ref.height, int(dy + sc.height) + 4)
out = Image.new('RGBA', (ref.width + 2 * PAD, H), (0, 0, 0, 0)); out.paste(sc, (int(round(dx)) + PAD, int(round(dy))), sc)
out.save(os.path.join(A, out_n + '.png'))
rp = Image.new('RGBA', (ref.width + 2 * PAD, ref.height), (0, 0, 0, 0)); rp.paste(ref, (PAD, 0), ref)
rp.save(os.path.join(A, ref_n + '.png')); print(out.size, rp.size, 'pad', PAD)
