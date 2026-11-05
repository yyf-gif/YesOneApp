import numpy as np, wave, os
HERE = os.path.dirname(os.path.abspath(__file__))
SR = 48000; DUR = 14.5
N = int(SR * DUR)
out = np.zeros(N)
rng = np.random.default_rng(3)

L_TIMES = [4.20, 5.10, 6.00, 6.90, 7.80, 8.70]; R_OFF = 0.08
T_SNAP = 2.50; T_GROW = 2.97; T_SHOVE = 9.16; T_CGRAB = 9.62; T_YANK = 9.74; T_UP = 10.10
T_POOF = 10.22; T_POSE = 10.30; T_Q = 10.15
OUTL = np.zeros(N); OUTR = np.zeros(N)

def add(sig, t, gain=1.0):
    i = int(t * SR); j = min(N, i + len(sig))
    if i < N: out[i:j] += sig[:j - i] * gain

def env(n, a, d):  # attack/decay exponential env
    t = np.arange(n) / SR
    e = np.exp(-t / d)
    na = int(a * SR)
    if na > 0: e[:na] *= np.linspace(0, 1, na)
    return e

def noise(n): return rng.standard_normal(n)
def lp(x, k):  # one-pole lowpass, k in (0,1)
    y = np.zeros_like(x); acc = 0.0
    for i in range(len(x)):
        acc += k * (x[i] - acc); y[i] = acc
    return y
def hp(x, k): return x - lp(x, k)
def tone(freqs, dur):
    n = int(dur * SR)
    f = np.interp(np.arange(n), np.linspace(0, n, len(freqs)), freqs)
    return np.sin(2 * np.pi * np.cumsum(f) / SR)

def boom(f0=55, f1=35, dur=0.9, a=0.003):
    n = int(dur * SR); return tone([f0, f1], dur) * env(n, a, dur / 3.5)
def click(dur=0.012, bright=0.6):
    n = int(dur * SR); return hp(noise(n), bright) * env(n, 0, dur / 4)
def whoosh(dur=0.18, up=True):
    n = int(dur * SR); x = noise(n)
    k = np.linspace(0.02, 0.25, n) if up else np.linspace(0.25, 0.02, n)
    y = np.zeros(n); acc = 0
    for i in range(n): acc += k[i] * (x[i] - acc); y[i] = acc
    w = np.sin(np.linspace(0, np.pi, n)) ** 2
    return y * w * 3
def fabric_snap():
    n = int(0.08 * SR); x = hp(noise(n), 0.3) * env(n, 0.001, 0.015)
    return x + 0.6 * tone([180, 90], 0.08) * env(n, 0, 0.02)
def metal(dur=0.35, base=520):
    n = int(dur * SR); s = np.zeros(n)
    for m, g in ((1, 1), (2.76, 0.6), (5.4, 0.4), (8.9, 0.25)):
        s += g * np.sin(2 * np.pi * base * m * np.arange(n) / SR)
    return s * env(n, 0, dur / 5) * 0.4
def ding(f=1320, dur=0.6):
    n = int(dur * SR); tt = np.arange(n) / SR
    s = np.sin(2*np.pi*f*tt) + 0.4*np.sin(2*np.pi*f*2.01*tt) + 0.2*np.sin(2*np.pi*f*3.02*tt)
    return s * env(n, 0.002, dur / 4) * 0.5
def scratch():
    dur = 0.32; n = int(dur * SR)
    f = np.concatenate([np.linspace(900, 200, n // 2), np.linspace(200, 1100, n - n // 2)])
    saw = 2 * ((np.cumsum(f) / SR) % 1) - 1
    nz = lp(noise(n), 0.2)
    return (0.5 * saw + nz) * env(n, 0.005, 0.12) * np.sin(np.linspace(0, np.pi, n)) ** 0.5

# ---- scene 1 ----
add(scratch(), 0.56, 0.5)
add(fabric_snap(), 0.60, 0.8); add(boom(90, 60, 0.25), 0.60, 0.5)
# rubber stretch: rising wobbly tone 0.8 -> 2.5
dur = T_SNAP - 0.8; n = int(dur * SR); tt = np.linspace(0, 1, n)
freq = 90 + 520 * tt ** 1.8 + 12 * np.sin(2 * np.pi * 9 * tt * dur)
st = np.sin(2 * np.pi * np.cumsum(freq) / SR) + 0.35 * np.sign(np.sin(2 * np.pi * np.cumsum(freq * 0.5) / SR))
creak = lp(noise(n), 0.05) * (0.3 + 0.7 * tt)
add((st * 0.35 + creak * 0.8) * (0.15 + 0.85 * tt ** 1.5), 0.8, 0.55)
# snap
add(click(0.02, 0.8), T_SNAP, 1.2); add(fabric_snap(), T_SNAP, 1.0); add(boom(60, 32, 1.2), T_SNAP, 1.3)
add(whoosh(0.25, False), T_SNAP + 0.02, 0.6)

# regrow: each half pops into a full person
def bloop(f0=220, f1=660, dur=0.16):
    n = int(dur * SR); return tone([f0, f1], dur) * env(n, 0.002, dur / 3)
add(bloop(200, 700), T_GROW, 0.55); add(bloop(260, 820), T_GROW + 0.03, 0.45); add(click(0.01, 0.6), T_GROW, 0.5)

# ---- racks + styling ----
add(whoosh(0.12), 2.98, 0.35)
add(metal(0.4, 430), 3.13, 0.7); add(lp(noise(int(0.28*SR)), 0.04) * env(int(0.28*SR), 0.01, 0.1) * 3, 3.14, 0.5)
add(metal(0.5, 380), 3.42, 0.9); add(boom(110, 70, 0.2), 3.42, 0.5)
for off in (0.0, R_OFF):
    for i, tk in enumerate(L_TIMES):
        tk += off
        add(metal(0.12, 900 + 60 * i), tk - 0.52, 0.18)
        add(whoosh(0.10), tk - 0.43, 0.30)
        add(whoosh(0.14, True), tk - 0.16, 0.45)
        add(fabric_snap(), tk, 0.9); add(click(0.01, 0.7), tk, 0.6)
        add(boom(140, 90, 0.12), tk, 0.45)
        if i < 5: add(whoosh(0.10), tk + 0.10, 0.25)

# ---- shove racks off ----
add(boom(120, 70, 0.15), T_SHOVE, 0.5); add(metal(0.3, 400), T_SHOVE, 0.5)
n = int(0.35 * SR); add(lp(noise(n), 0.03) * np.sin(np.linspace(0, np.pi, n)) * 5, T_SHOVE, 0.5)
add(whoosh(0.25, False), T_SHOVE + 0.05, 0.5)

# ---- curtain: grab, yank, roll up ----
add(fabric_snap(), T_CGRAB, 0.6); add(click(0.012, 0.5), T_CGRAB, 0.4)
n = int(0.40 * SR); tt = np.arange(n) / SR
ratchet = (np.sin(2 * np.pi * 38 * tt) > 0.6).astype(float) * hp(noise(n), 0.4) * env(n, 0.003, 0.3)
add(ratchet, T_YANK, 0.7)
add(whoosh(0.38, True), T_YANK, 1.0); add(fabric_snap(), T_YANK, 0.9)
add(click(0.02, 0.8), T_UP - 0.02, 0.9); add(boom(70, 40, 0.5), T_UP, 0.7)
# worlds revealed: rain (left) and warm courtyard air + chime (right)
n = N - int(T_YANK * SR)
fade = np.clip(np.arange(n) / (0.5 * SR), 0, 1)
OUTL[int(T_YANK * SR):] += lp(noise(n), 0.35) * 0.10 * fade + hp(noise(n), 0.6) * 0.04 * fade
OUTR[int(T_YANK * SR):] += lp(noise(n), 0.02) * 0.6 * fade
add(ding(1568, 1.2), T_UP + 0.02, 0.35)
# ---- stylists vanish ----
n = int(0.3 * SR); add(lp(noise(n), 0.15) * env(n, 0.005, 0.08) * 2, T_POOF, 0.6); add(bloop(700, 300, 0.12), T_POOF, 0.3)

# ---- question ----
add(whoosh(0.2, True), T_Q - 0.12, 0.6); add(boom(80, 50, 0.35), T_Q, 0.6)
add(ding(1320), T_Q + 0.42, 0.9); add(ding(1760), T_Q + 0.62, 0.9)
add(boom(48, 28, 2.0, 0.003), T_Q + 0.9, 1.2)

# simple room reverb
rev = out.copy()
for d, g in ((0.031, 0.25), (0.047, 0.2), (0.071, 0.15), (0.113, 0.1)):
    k = int(d * SR); rev[k:] += out[:-k] * g
out = rev
# soft clip + normalize
out = np.tanh(out * 0.9)
out /= np.max(np.abs(out)) * 1.08
st = np.stack([out + OUTL, out + OUTR], 1)
st /= np.max(np.abs(st)) * 1.05
with wave.open(os.path.join(HERE, 'sfx.wav'), 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st * 32767).astype(np.int16).tobytes())
print('ok')
