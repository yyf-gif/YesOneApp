"""Paint the stick-figure neck into each top's collar opening, like the original art: the inside of the
collar becomes a light grey gradient (212 -> 190), so the head sits on a visible neck."""
import sys, os, numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage
A = os.path.join(sys.argv[1], 'art')
TOP, BOT = np.array([212, 212, 218.]), np.array([190, 190, 196.])
def paint(n, m):
    im = np.array(Image.open(os.path.join(A, n + '.png'))).astype(float)
    m = np.array(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))) / 255.0
    ys = np.where(m.max(1) > 0.5)[0]; y0, y1 = ys.min(), ys.max()
    u = np.clip((np.arange(im.shape[0]) - y0) / max(1, y1 - y0), 0, 1)[:, None, None]
    col = TOP * (1 - u) + BOT * u
    im[..., :3] = im[..., :3] * (1 - m[..., None]) + col * m[..., None]
    im[..., 3] = np.maximum(im[..., 3], m * 255)
    Image.fromarray(im.clip(0, 255).astype(np.uint8)).save(os.path.join(A, n + '.png')); print(n, 'neck rows', y0, y1)
def poly(n, pts):
    im = Image.open(os.path.join(A, n + '.png')); mk = Image.new('L', im.size, 0)
    ImageDraw.Draw(mk).polygon(pts, fill=255); paint(n, np.array(mk) / 255.0)
def flood(n, seed, box):
    im = np.array(Image.open(os.path.join(A, n + '.png'))).astype(float)
    lum = im[..., :3] @ [0.299, 0.587, 0.114]; x0, y0, x1, y1 = box
    dark = np.zeros(lum.shape, bool); dark[y0:y1, x0:x1] = (lum[y0:y1, x0:x1] < 75) & (im[y0:y1, x0:x1, 3] > 60)
    lab, _ = ndimage.label(dark); m = lab == lab[seed[1], seed[0]]
    assert lab[seed[1], seed[0]] > 0, n
    m = ndimage.binary_closing(m, iterations=2) & (im[..., 3] > 60)
    paint(n, m.astype(float))
flood('sk_top', (318, 28), (256, 0, 381, 46))
flood('sk_top_pose', (322, 28), (263, 0, 385, 46))
poly('vt_shirt', [(129, 8), (196, 8), (196, 30), (191, 42), (187, 52), (186, 58), (140, 58), (138, 52), (134, 42), (130, 30)])
poly('vt_top', [(176, 17), (248, 17), (247, 30), (244, 40), (238, 50), (233, 60), (227, 70), (217, 82), (207, 70), (193, 60), (183, 50), (180, 40), (178, 30)])
poly('vt_top_pose', [(176, 16), (245, 16), (242, 30), (240, 40), (236, 50), (231, 60), (221, 70), (207, 81), (197, 70), (192, 60), (186, 50), (182, 40), (178, 30)])
