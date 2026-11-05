import sys, subprocess, numpy as np, cairo
k, nparts = int(sys.argv[1]), int(sys.argv[2])
sys.argv = ['x']
import street_stylist as S, pixel_emoji as PX
S.EMO = PX.build_all(10)
n = int(round(S.DUR * S.FPS)); cams = S.camera_track(n)
a, b = n * k // nparts, n * (k + 1) // nparts
surfs = [cairo.ImageSurface(cairo.FORMAT_ARGB32, S.W, S.HT) for _ in range(5)]
pr = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{S.W}x{S.HT}', '-r', str(S.FPS),
                       '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p', f'part{k}.mp4'], stdin=subprocess.PIPE)
for f in range(a, b):
    pr.stdin.write(np.ascontiguousarray(S.render_frame(f / S.FPS, cams[f], surfs)).tobytes())
    if (f - a) % 15 == 0: print(k, f - a, b - a, flush=True)
pr.stdin.close(); pr.wait(); print('done', k, flush=True)
