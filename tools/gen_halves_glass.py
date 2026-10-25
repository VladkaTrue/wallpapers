"""HALVES GLASS — те же сетки HALVES, но каждая половинка из цветного стекла.

python3 tools/gen_halves_glass.py          — весь пак
python3 tools/gen_halves_glass.py test     — быстрый тест в уменьшенном размере
"""
import os, sys, random
import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_halves as H0          # палитры, раскладки, типы клеток — ровно как в HALVES
from gen_glass import blur

OUT = "/home/claude/HALVES_GLASS"
PRE = "HALVES-GLASS"
TEST = len(sys.argv) > 1 and sys.argv[1] == "test"

class Recorder:
    """вместо рисования запоминает полукруги и круги, чтобы потом построить из них стекло."""
    def __init__(self): self.items = []
    def pieslice(self, box, a, b, fill):
        cx, cy, r = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2, (box[2] - box[0]) / 2
        m = np.deg2rad((a + b) / 2)
        self.items.append(("half", cx, cy, r, np.cos(m), np.sin(m), fill))
    def ellipse(self, box, fill):
        cx, cy, r = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2, (box[2] - box[0]) / 2
        self.items.append(("circ", cx, cy, r, 0, 0, fill))

def layout(lay, pal, bgname, fmt, W, H):
    """та же логика раскладки, что в gen_halves.render — одинаковые сиды дают одинаковые сетки."""
    bg, fg, grey, acc, acc2 = (H0.hx(c) for c in H0.PALETTES[pal][bgname])
    rnd = random.Random(H0.LAYOUTS[lay] * 1000 + {"Mac": 1, "Ultrawide": 2, "iPhone": 3}[fmt])
    dr = Recorder()
    if H > W:
        cols = 4; mx = W * 0.07; top = H * 0.30; bottom = H * 0.06
        s = (W - 2 * mx) / cols; rows = int((H - top - bottom) // s)
        oy = top + ((H - top - bottom) - rows * s) / 2
    else:
        cols = 8 if W / H < 2 else 12; mx = W * 0.04
        s = (W - 2 * mx) / cols; top, bottom = H * 0.06, H * 0.07
        rows = int((H - top - bottom) // s); oy = top + ((H - top - bottom) - rows * s) / 2
    ox = (W - cols * s) / 2; gap = s * 0.10; n = cols * rows
    picked = []; order = list(range(n)); rnd.shuffle(order)
    for k in order:
        i, j = k % cols, k // cols
        if all(abs(i - q % cols) + abs(j - q // cols) >= max(3, cols // 3) for q in picked):
            picked.append(k)
        if len(picked) == 4: break
    full_acc = set(picked[:2]); pair_acc = set(picked[2:4])
    rest = [k for k in order if k not in picked]; greys = set(rest[:max(3, n // 12)])
    def op(): return rnd.choices([0.92, 0.70, 0.45, 0.25], weights=[5, 3, 2, 1])[0]
    for k in range(n):
        i, j = k % cols, k // cols
        x, y = ox + i * s, oy + j * s
        kind = rnd.choice(H0.KINDS)
        ca, cb = (fg, op()), (fg, op())
        if k in full_acc:
            kind = "circle"; ca = (acc2 if (k == min(full_acc)) else acc, 0.92)
        elif k in pair_acc:
            kind = rnd.choice(["bow_h", "bow_v", "dd_r", "dd_l"]); ca, cb = (acc, 0.92), (acc, 0.6)
        elif k in greys:
            if rnd.random() < .5: ca = (grey, 0.8)
            else: cb = (grey, 0.8)
        H0.cell(dr, x, y, s, gap, kind, ca, cb)
    return dr.items, s, (bg, fg, grey, acc, acc2)

def render(job):
    lay, pal, bgname, fmt = job
    W, H = H0.FORMATS[fmt]
    if TEST: W, H = W // 3, H // 3
    items, s, (bg, fg, grey, acc, acc2) = layout(lay, pal, bgname, fmt, W, H)
    f = lambda c: np.array(c, np.float32) / 255
    dark = bgname == "Dark"
    # фон: цвет палитры + мягкие пятна её же цветов — стеклу есть что преломлять
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    img = np.empty((H, W, 3), np.float32); img[:] = f(bg)
    M = max(W, H)
    for col, bx, by, br in [(acc, .22, .30, .38), (acc2, .82, .72, .40), (grey, .62, .18, .34), (fg, .18, .86, .30)]:
        d2 = ((xs - bx * W) ** 2 + (ys - by * H) ** 2) / (br * M) ** 2
        a = (np.exp(-d2 * 2.4) * (0.26 if dark else 0.22))[..., None]
        img = img * (1 - a) + f(col) * a
    # поле расстояний до ближайшей фигуры + её цвет и плотность
    D = np.full((H, W), 1e4, np.float32)
    TC = np.zeros((H, W, 3), np.float32); TA = np.zeros((H, W), np.float32)
    GY = np.zeros((H, W), np.float32)       # положение по вертикали внутри фигуры: -1 верх, +1 низ
    pad = 0.12 * s
    for kind, cx, cy, r, vx, vy, (col, alpha) in items:
        x0, x1 = int(max(0, cx - r - pad)), int(min(W, cx + r + pad + 1))
        y0, y1 = int(max(0, cy - r - pad)), int(min(H, cy + r + pad + 1))
        px, py = xs[y0:y1, x0:x1] - cx, ys[y0:y1, x0:x1] - cy
        d = np.sqrt(px * px + py * py) - r
        if kind == "half":
            d = np.maximum(d, -(px * vx + py * vy))
        sub = D[y0:y1, x0:x1]; m = d < sub
        sub[m] = d[m]
        TC[y0:y1, x0:x1][m] = f(col); TA[y0:y1, x0:x1][m] = alpha
        GY[y0:y1, x0:x1][m] = (py / r)[m]
    inside = np.clip(0.5 - D, 0, 1)
    # цветной отсвет: стекло отбрасывает на фон мягкое пятно своего цвета, чуть ниже фигуры
    A = TA * inside
    Cb = blur(TC * A[..., None], 0.10 * s); Ab = blur(np.repeat(A[..., None], 3, 2), 0.10 * s)[..., 0]
    sh_y = int(0.06 * s)
    Cb = np.roll(Cb, sh_y, axis=0); Ab = np.roll(Ab, sh_y, axis=0)
    if dark:
        img = img + Cb * 0.45
    else:
        img = img * (1 - 0.35 * Ab[..., None]) + Cb * 0.35
    # тень под стеклом
    sh = np.clip(1 - (D - 0.012 * s) / (0.08 * s), 0, 1) ** 2 * (1 - inside)
    img = img * (1 - (sh * (0.35 if dark else 0.14))[..., None])
    # стекло: матовость + преломление у кромок с лёгкой аберрацией
    gy, gx = np.gradient(D); gm = np.sqrt(gx * gx + gy * gy) + 1e-6
    nx, ny = gx / gm, gy / gm
    depth = np.clip(-D, 0, None)
    frost = blur(img, 0.035 * s)
    lens = (1 - np.clip(depth / (0.18 * s), 0, 1)) ** 2 * 0.16 * s
    iy, ix = np.nonzero(inside > 0)
    refr = img.copy()
    for c, k in enumerate((1.0, 1.06, 1.12)):
        sx = ix + nx[iy, ix] * lens[iy, ix] * k; sy = iy + ny[iy, ix] * lens[iy, ix] * k
        refr[iy, ix, c] = map_coordinates(frost[..., c], [sy, sx], order=1, mode="nearest")
    # окраска стекла в цвет фигуры: плотные фигуры — насыщенное стекло, лёгкие — почти прозрачное
    tint = (TA * 0.42)[..., None]
    refr = refr * (1 - tint) + TC * tint
    haze = 0.05 if dark else 0.12
    refr = refr * (1 - haze) + haze
    refr = refr * (1 - 0.10 * GY)[..., None]          # верх фигуры светлее, низ темнее
    # блики: свет сверху слева, кромка и внутренний отсвет
    rim = np.clip(1 - depth / (0.02 * s), 0, 1)
    light = np.clip(-(nx * 0.6 + ny * 0.8), 0, 1)
    shade = np.clip(nx * 0.6 + ny * 0.8, 0, 1)
    refr = refr + (rim * light * 0.75)[..., None]
    refr = refr * (1 - (rim * shade * 0.20)[..., None])
    glow = np.clip(1 - depth / (0.14 * s), 0, 1) ** 3 * light * 0.18
    refr = refr + glow[..., None]
    spec = np.exp(-((depth - 0.045 * s) / (0.010 * s)) ** 2) * light * 0.30   # тонкий внутренний блик
    refr = refr + spec[..., None]
    line = np.clip(1 - np.abs(D + 0.6) / 1.2, 0, 1) * 0.22
    refr = refr + line[..., None]
    a = inside[..., None]
    img = img * (1 - a) + np.clip(refr, 0, 1) * a
    rng = np.random.default_rng(abs(hash(job)) & 0xFFFF)
    img = img + rng.normal(0, 1.0 / 255, img.shape).astype(np.float32)
    folder = os.path.join(OUT, fmt, bgname); os.makedirs(folder, exist_ok=True)
    Image.fromarray((np.clip(img, 0, 1) * 255 + .5).astype(np.uint8)).save(
        os.path.join(folder, f"{PRE}_{lay}_{pal}_{bgname}.jpg"), quality=94, subsampling=0, optimize=True)
    return job

if __name__ == "__main__":
    jobs = [(l, p, b, f) for f in H0.FORMATS for b in ("Dark", "Light") for l in H0.LAYOUTS for p in H0.PALETTES]
    if TEST:
        jobs = [j for j in jobs if j[0] == "Rhythm"]
    for j in jobs:
        if os.path.exists(os.path.join(OUT, j[3], j[2], f"{PRE}_{j[0]}_{j[1]}_{j[2]}.jpg")): continue
        render(j); print("ok", j, flush=True)
    print("done", len(jobs))
