"""CONTOUR v2 — монохромная топографическая карта под macOS 27 и iOS 27.

python3 tools/gen_contour.py          — весь пак
python3 tools/gen_contour.py test     — быстрый тест в уменьшенном размере
"""
import numpy as np, os, sys
from PIL import Image
from scipy.ndimage import map_coordinates, gaussian_filter
from multiprocessing import Pool

OUT = "/home/claude/CONTOUR"
PRE = "CONTOUR"
TEST = len(sys.argv) > 1 and sys.argv[1] == "test"

FORMATS = {"Mac": (4480, 3088), "Ultrawide": (5120, 2160), "iPhone": (1320, 2868)}

# фон, тонкие линии, толстые (индексные) линии
PALETTES = {
    "Graphite": {"Dark": ("#0B0B0C", "#6C6C70", "#A4A4A9"), "Light": ("#F2F2F0", "#C2C2C4", "#8E8E93")},
    "Navy":     {"Dark": ("#0A1222", "#3E4F6E", "#8396BA"), "Light": ("#EEF1F6", "#BAC4D6", "#7385A8")},
    "Olive":    {"Dark": ("#0E120D", "#4C5946", "#929F87"), "Light": ("#F0F2EC", "#C1C8B8", "#84927A")},
    "Clay":     {"Dark": ("#150E0B", "#664537", "#B98068"), "Light": ("#F5EFEB", "#D9C3B7", "#AD7D67")},
}
# рельефы — разные «участки карты»
TERRAINS = {"Highland": 3, "Valley": 17, "Plateau": 29, "Coast": 41}

def hx(c):
    c = c.lstrip("#"); return np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255

def octave(seed, x, y, cell, n=40):
    rng = np.random.default_rng(seed)
    g = gaussian_filter(rng.normal(size=(n, n)).astype(np.float32), 0.7, mode="wrap")
    gx = x / cell + n / 2; gy = y / cell + n / 2
    return map_coordinates(g, [gy.ravel(), gx.ravel()], order=3, mode="wrap").reshape(x.shape)

def height(seed, x, y):
    # лёгкое искривление пространства делает холмы «органичнее»
    wx = x + 0.05 * octave(seed + 101, x, y, 0.30)
    wy = y + 0.05 * octave(seed + 202, x, y, 0.30)
    return (octave(seed, wx, wy, 0.26) + 0.42 * octave(seed + 1, wx, wy, 0.13)
            + 0.16 * octave(seed + 2, wx, wy, 0.065))

def render(job):
    terrain, pal, bgname, fmt = job
    W, H = FORMATS[fmt]
    if TEST: W, H = W // 3, H // 3
    portrait = H > W
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    if portrait:
        vw = 0.50                      # телефон видит более крупный фрагмент той же карты
        x = 0.15 + (xs / W - 0.5) * vw; y = (ys / H - 0.5) * vw * H / W
        thin_w, thick_w = 0.0030 * W, 0.0068 * W
    else:
        x = (xs - W / 2) / H; y = (ys - H / 2) / H
        thin_w, thick_w = 0.0017 * H, 0.0042 * H
    h = height(TERRAINS[terrain], x, y)
    h = (h - h.mean()) / h.std()
    v = h * 3.4 + 0.5                  # плотность изолиний
    gy, gx = np.gradient(v)
    gm = np.sqrt(gx * gx + gy * gy) + 1e-6
    f = v - np.round(v)
    dist = np.abs(f) / gm
    major = (np.round(v).astype(np.int32) % 4) == 0
    lw = np.where(major, thick_w, thin_w)
    a = np.clip(lw / 2 + 0.5 - dist, 0, 1)
    # где линии сходятся слишком плотно — слегка гасим, чтобы не было «каши»
    a *= 1 - np.clip(gm * 1.6 / thin_w - 1.0, 0, 1) * 0.6

    bgc, thin_c, thick_c = (hx(c) for c in PALETTES[pal][bgname])
    col = np.where(major[..., None], thick_c, thin_c)
    img = np.broadcast_to(bgc, (H, W, 3)).astype(np.float32)
    # едва заметная виньетка, как на фото экрана
    d = np.sqrt(((xs - W / 2) / W) ** 2 + ((ys - H / 2) / H) ** 2) / 0.72
    vig = (np.clip(d, 0, 1) ** 2 * (0.25 if bgname == "Dark" else 0.05))[..., None]
    img = img * (1 - vig)
    img = img * (1 - a[..., None]) + col * a[..., None]
    rng = np.random.default_rng(abs(hash(job)) & 0xFFFF)
    img = img + rng.normal(0, 0.8 / 255, img.shape).astype(np.float32)
    out = Image.fromarray((np.clip(img, 0, 1) * 255 + .5).astype(np.uint8))
    folder = os.path.join(OUT, fmt, bgname); os.makedirs(folder, exist_ok=True)
    out.save(os.path.join(folder, f"{PRE}_{terrain}_{pal}_{bgname}.jpg"), quality=92, subsampling=0, optimize=True)
    return job

if __name__ == "__main__":
    jobs = [(t, p, b, f) for f in FORMATS for b in ("Dark", "Light") for t in TERRAINS for p in PALETTES]
    if TEST:
        jobs = [j for j in jobs if j[1] == "Graphite"]
    with Pool(os.cpu_count()) as pool:
        for _ in pool.imap_unordered(render, jobs): pass
    print("done", len(jobs))
