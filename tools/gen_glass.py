"""GLASS — стеклянные фигуры в духе Liquid Glass (iOS 27 / macOS 27).

python3 tools/gen_glass.py          — весь пак
python3 tools/gen_glass.py test     — быстрый тест в уменьшенном размере
"""
import os, sys
import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import map_coordinates, gaussian_filter

OUT = "/home/claude/GLASS"
PRE = "GLASS"
TEST = len(sys.argv) > 1 and sys.argv[1] == "test"
FORMATS = {"Mac": (4480, 3088), "Ultrawide": (5120, 2160), "iPhone": (1320, 2868)}

# фон: базовый цвет + цветные пятна (x, y в долях экрана, радиус в долях большей стороны)
PALETTES = {
    "Aurora": {
        "Dark":  ("#0B0D1E", [("#3D5AFE", .22, .30, .45), ("#8E2DE2", .70, .25, .40), ("#FF3CAC", .80, .80, .42), ("#2BD2FF", .30, .85, .38)]),
        "Light": ("#EEF0FF", [("#7F8CFF", .22, .30, .45), ("#C59BFF", .70, .25, .40), ("#FF9AD5", .80, .80, .42), ("#8EE7FF", .30, .85, .38)]),
    },
    "Sunset": {
        "Dark":  ("#160A12", [("#FF5E3A", .25, .70, .45), ("#FF2A68", .65, .35, .40), ("#7A1FA2", .85, .80, .42), ("#FFB347", .20, .20, .35)]),
        "Light": ("#FFF3EC", [("#FFA07A", .25, .70, .45), ("#FF8FB1", .65, .35, .40), ("#C59BE8", .85, .80, .42), ("#FFD38A", .20, .20, .35)]),
    },
    "Lagoon": {
        "Dark":  ("#04161A", [("#00B4D8", .30, .30, .45), ("#0077B6", .75, .70, .45), ("#2EC4B6", .70, .20, .35), ("#90E0EF", .20, .85, .35)]),
        "Light": ("#EAF8F7", [("#7FD8E8", .30, .30, .45), ("#7FB3E0", .75, .70, .45), ("#8FE3C8", .70, .20, .35), ("#C8F1F8", .20, .85, .35)]),
    },
    "Graphite": {
        "Dark":  ("#0E0F12", [("#3A3F4B", .25, .30, .45), ("#5B6578", .75, .65, .45), ("#2C3340", .70, .15, .35), ("#8A93A6", .30, .85, .30)]),
        "Light": ("#F2F3F5", [("#C9CED8", .25, .30, .45), ("#AEB6C4", .75, .65, .45), ("#DDE1E8", .70, .15, .35), ("#9CA6B8", .30, .85, .30)]),
    },
}

# фигуры в единицах u = меньшая сторона экрана, относительно центра (x вправо, y вниз)
# ("circle", cx, cy, r) | ("capsule", cx, cy, w, h) | ("rect", cx, cy, w, h, radius)
MOTIFS = {
    "Orbs": {
        "land": [("circle", .34, .02, .36), ("circle", -.16, .20, .17), ("circle", -.52, -.22, .07)],
        "port": [("circle", .10, .30, .40), ("circle", -.24, .66, .18), ("circle", .30, -.08, .08)],
    },
    "Pills": {
        "land": [("capsule", -.26, .06, .27, .82), ("capsule", 0, -.04, .27, .82), ("capsule", .26, .06, .27, .82)],
        "port": [("capsule", -.27, .38, .34, 1.15), ("capsule", 0, .26, .34, 1.15), ("capsule", .27, .38, .34, 1.15)],
    },
    "Panels": {
        "land": [("rect", -.14, -.06, .64, .42, .10), ("rect", .16, .14, .64, .42, .10), ("rect", .50, -.26, .22, .22, .06)],
        "port": [("rect", -.04, .10, .84, .52, .12), ("rect", .06, .50, .84, .52, .12), ("rect", -.24, -.30, .30, .30, .08)],
    },
}

def hx(c):
    c = c.lstrip("#"); return np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255

def blur(img, sigma):
    """быстрое сильное размытие: уменьшить → размыть → увеличить."""
    H, W, _ = img.shape
    k = max(1, int(sigma / 6))
    out = np.empty_like(img)
    for c in range(3):
        ch = Image.fromarray(img[..., c].astype(np.float32), "F")
        sm = np.asarray(ch.resize((max(1, W // k), max(1, H // k)), Image.BILINEAR), np.float32)
        sm = gaussian_filter(sm, sigma / k, mode="nearest")
        out[..., c] = np.asarray(Image.fromarray(sm, "F").resize((W, H), Image.BICUBIC), np.float32)
    return out

def background(pal, bgname, W, H):
    base, blobs = PALETTES[pal][bgname]
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    img = np.empty((H, W, 3), np.float32); img[:] = hx(base)
    M = max(W, H)
    for col, bx, by, br in blobs:
        d2 = ((xs - bx * W) ** 2 + (ys - by * H) ** 2) / (br * M) ** 2
        a = np.exp(-d2 * 2.2)[..., None] * (0.85 if bgname == "Dark" else 0.75)
        img = img * (1 - a) + hx(col) * a
    return img

def sdf(shape, xs, ys, u, cx0, cy0):
    kind = shape[0]
    cx, cy = cx0 + shape[1] * u, cy0 + shape[2] * u
    px, py = xs - cx, ys - cy
    if kind == "circle":
        return np.sqrt(px * px + py * py) - shape[3] * u
    if kind == "capsule":
        w, h = shape[3] * u, shape[4] * u
        r = w / 2; hl = h / 2 - r
        qy = np.maximum(np.abs(py) - hl, 0)
        return np.sqrt(px * px + qy * qy) - r
    if kind == "rect":
        w, h, r = shape[3] * u / 2, shape[4] * u / 2, shape[5] * u
        qx, qy = np.abs(px) - w + r, np.abs(py) - h + r
        return np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2) + np.minimum(np.maximum(qx, qy), 0) - r

def glass(img, d, u, bgname):
    H, W, _ = img.shape
    gy, gx = np.gradient(d)
    gm = np.sqrt(gx * gx + gy * gy) + 1e-6
    nx, ny = gx / gm, gy / gm                              # нормаль наружу
    inside = np.clip(0.5 - d, 0, 1)
    depth = np.clip(-d, 0, None)
    edge = 0.06 * u
    # тень под стеклом
    sh = np.clip(1 - (d - 0.01 * u) / (0.06 * u), 0, 1) ** 2 * (1 - inside)
    img = img * (1 - (sh * (0.30 if bgname == "Dark" else 0.12))[..., None])
    # матовое стекло: размытый фон + преломление у краёв с лёгкой хроматической аберрацией
    frost = blur(img, 0.018 * u)
    lens = (1 - np.clip(depth / edge, 0, 1)) ** 2 * 0.12 * u
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    refr = np.empty_like(img)
    for c, k in enumerate((1.0, 1.06, 1.12)):
        sx = xs + nx * lens * k; sy = ys + ny * lens * k
        refr[..., c] = map_coordinates(frost[..., c], [sy, sx], order=1, mode="nearest")
    # лёгкий белёсый налёт стекла
    tint = 0.07 if bgname == "Dark" else 0.22
    refr = refr * (1 - tint) + tint
    # блик по кромке: свет сверху слева, тень снизу справа
    rim = np.clip(1 - depth / (0.012 * u), 0, 1)
    light = np.clip(-(nx * -0.6 + ny * -0.8), 0, 1)        # нормаль смотрит к свету
    dark_side = np.clip(nx * -0.6 + ny * -0.8, 0, 1)
    refr = refr + (rim * light * 0.65)[..., None]
    refr = refr * (1 - (rim * dark_side * 0.18)[..., None])
    # мягкий внутренний отсвет вдоль верхнего края
    glow = np.clip(1 - depth / (0.06 * u), 0, 1) ** 3 * light * 0.10
    refr = refr + glow[..., None]
    # тонкий светлый контур
    line = np.clip(1 - np.abs(d + 0.6) / 1.2, 0, 1) * 0.25
    refr = refr + line[..., None]
    a = inside[..., None]
    return img * (1 - a) + np.clip(refr, 0, 1) * a

def render(job):
    motif, pal, bgname, fmt = job
    W, H = FORMATS[fmt]
    if TEST: W, H = W // 3, H // 3
    portrait = H > W
    u = min(W, H)
    img = background(pal, bgname, W, H)
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    cx0, cy0 = W / 2, H / 2
    for shape in MOTIFS[motif]["port" if portrait else "land"]:
        d = sdf(shape, xs, ys, u, cx0, cy0)
        img = glass(img, d, u, bgname)
    rng = np.random.default_rng(abs(hash(job)) & 0xFFFF)
    img = img + rng.normal(0, 1.1 / 255, img.shape).astype(np.float32)
    folder = os.path.join(OUT, fmt, bgname); os.makedirs(folder, exist_ok=True)
    Image.fromarray((np.clip(img, 0, 1) * 255 + .5).astype(np.uint8)).save(
        os.path.join(folder, f"{PRE}_{motif}_{pal}_{bgname}.jpg"), quality=94, subsampling=0, optimize=True)
    return job

if __name__ == "__main__":
    jobs = [(m, p, b, f) for f in FORMATS for b in ("Dark", "Light") for m in MOTIFS for p in PALETTES]
    if TEST:
        jobs = [j for j in jobs if j[1] in ("Aurora", "Sunset") and j[3] != "Ultrawide"]
    if len(sys.argv) > 2:
        jobs = [j for j in jobs if j[3] == sys.argv[2]]
    for j in jobs:                       # последовательно: так надёжнее, чем пул процессов
        render(j); print("ok", j, flush=True)
    print("done", len(jobs))
