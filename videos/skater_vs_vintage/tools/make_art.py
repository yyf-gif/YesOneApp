"""Cut the outfit art for Skater vs Vintage out of the sheets in art_src/ -> art/*.png"""
import sys, os, numpy as np
from PIL import Image
from scipy import ndimage
P = sys.argv[1]; S = os.path.join(P, 'art_src'); O = os.path.join(P, 'art')
def load(n): return np.array(Image.open(os.path.join(S, n)).convert('RGBA'))
def trim(a, pad=4):
    ys, xs = np.where(a[..., 3] > 8)
    return a[max(0, ys.min() - pad):ys.max() + pad + 1, max(0, xs.min() - pad):xs.max() + pad + 1]
def keep_biggest(a, thr=20):
    m = a[..., 3] > thr; lab, n = ndimage.label(ndimage.binary_dilation(m, iterations=2))
    if n <= 1: return a
    sizes = ndimage.sum(m, lab, range(1, n + 1)); k = 1 + int(np.argmax(sizes))
    a = a.copy(); a[..., 3] = np.where(lab == k, a[..., 3], 0); return a

def save(a, n, do_trim=True):
    a = keep_biggest(a)
    Image.fromarray(trim(a) if do_trim else a).save(os.path.join(O, n + '.png')); print(n, a.shape)
def box(a, x0, y0, x1, y1):
    b = a[y0:y1, x0:x1].copy(); return b

s1 = load('1.webp'); s2 = load('2.webp'); f3 = load('3.webp'); f4 = load('4.webp')
# ---- skater (sheet 1)
save(box(s1, 262, 18, 795, 596), 'sk_top')
save(box(s1, 829, 13, 1202, 659), 'sk_jeans')
save(box(s1, 1306, 23, 1529, 220), 'sk_beanie')
save(box(s1, 1598, 56, 1763, 636), 'sk_board')
save(box(s1, 1256, 205, 1563, 424), 'sk_bag_full')
save(box(s1, 1251, 431, 1404, 619), 'sk_shoe_l')
save(box(s1, 1404, 431, 1558, 619), 'sk_shoe_r')
# ---- vintage (sheet 2)
save(box(s2, 40, 55, 369, 444), 'vt_shirt')
save(box(s2, 372, 44, 730, 446), 'vt_jacket')
save(box(s2, 730, 44, 1071, 446), 'vt_top')
save(box(s2, 1071, 52, 1272, 490), 'vt_trousers_plain')
save(box(s2, 1272, 50, 1494, 490), 'vt_trousers')
save(box(s2, 137, 594, 386, 683), 'vt_glasses')
save(box(s2, 436, 453, 670, 770), 'vt_bag')
save(box(s2, 761, 587, 1016, 675), 'vt_belt')
save(box(s2, 1110, 540, 1237, 765), 'vt_boot_l')
save(box(s2, 1247, 538, 1378, 765), 'vt_boot_r')

# ---- final-pose tops from the full fits
yy, xx = np.mgrid[0:f3.shape[0], 0:f3.shape[1]]
# vintage: both hands in pockets. drop trousers (light beige) + belt below the waist
a = f3.copy(); rgb = a[..., :3].astype(float); lum = rgb @ [0.299, 0.587, 0.114]
low = yy >= 508
r_, g_, b_ = rgb[..., 0], rgb[..., 1], rgb[..., 2]
gold = (r_ - b_ > 80) & (r_ > 140) & ((xx < 462) | (xx > 626))  # jacket buttons (not the belt buckle)
beige = low & (lum > 128) & ~gold
# belt + tucked shirt between the jacket fronts: remove everything that is NOT olive jacket, so the jacket fronts
# stay on top and overlap the belt ends (the belted trousers behind show only through the gap)
r_, g_, b_ = rgb[..., 0], rgb[..., 1], rgb[..., 2]
olive = (g_ >= r_ * 0.72) & (lum < 140) & (lum > 32)           # jacket (belt leather is g/r < 0.6)
olive |= gold
beltzone = (yy >= 510) & (xx >= 440) & (xx <= 645) & ~olive
a[..., 3] = np.where(beige | beltzone | (yy > 760), 0, a[..., 3])
zone = (yy >= 510) & (xx >= 440) & (xx <= 645)                  # drop thin leftovers (shadow lines) in the gap
m_ = a[..., 3] > 40; thin = m_ & ~ndimage.binary_opening(m_, iterations=4) & zone
a[..., 3] = np.where(thin, 0, a[..., 3])
a = keep_biggest(a)
save(a, 'vt_top_pose_raw')
# skater: left hand in the jeans pocket, right hand down on the board. cut along the hem line
cut_x = [0, 330, 398, 404, 560, 600, 672, 690, 1024]
cut_y = [655, 660, 652, 634, 642, 668, 672, 732, 732]
cy = np.interp(xx, cut_x, cut_y)
b = f4.copy(); b[..., 3] = np.where(yy < cy, b[..., 3], 0)
rgb = b[..., :3].astype(float); lum = rgb @ [0.299, 0.587, 0.114]
sat = rgb.max(-1) - rgb.min(-1)
zone = (yy >= 618) & (xx >= 395) & (xx <= 690)
jeansy = zone & ~(((lum > 150) & (sat < 45)) | (lum < 55))
b[..., 3] = np.where(jeansy, 0, b[..., 3])
b = keep_biggest(b)
save(b, 'sk_top_pose_raw')

# ---- bag bodies without the long straps (the strap is drawn in code, over the shoulder)
bf = np.array(Image.open(os.path.join(O, 'sk_bag_full.png'))); save(bf[58:, :212], 'sk_bag')
vb = np.array(Image.open(os.path.join(O, 'vt_bag.png'))); save(vb[128:, :178], 'vt_bag')
os.remove(os.path.join(O, 'sk_bag_full.png'))
# ---- background: art_src/5.webp has vintage | skater. Mirror it so skater is on the left (title order SKATER VS VINTAGE),
#      each half keeps its busy side on the outer edge. The glowing divider column is cut out (the code draws its own).
bg = Image.open(os.path.join(S, '5.webp')).convert('RGB'); g = np.array(bg)
Image.fromarray(np.ascontiguousarray(g[:, 477:][:, ::-1])).save(os.path.join(P, 'bg_left.png'))
Image.fromarray(np.ascontiguousarray(g[:, :462][:, ::-1])).save(os.path.join(P, 'bg_right.png'))
print('bg', g.shape)
