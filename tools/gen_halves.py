"""HALVES — сетка из полукругов в духе Баухауса, как на присланном фото.

python3 tools/gen_halves.py          — весь пак
python3 tools/gen_halves.py test     — быстрый тест в уменьшенном размере
"""
import os, sys, random
import numpy as np
from PIL import Image, ImageDraw
from multiprocessing import Pool

OUT = "/home/claude/HALVES"
PRE = "HALVES"
TEST = len(sys.argv) > 1 and sys.argv[1] == "test"
FORMATS = {"Mac": (4480, 3088), "Ultrawide": (5120, 2160), "iPhone": (1320, 2868)}
SS = 2  # суперсэмплинг для гладких краёв

# фон, фигуры, серый, акцент, второй акцент (светлее)
PALETTES = {
    "Classic": {"Dark":  ("#0E0E0E", "#ECE8E3", "#9E9EA0", "#F0582A", "#F4876C"),
                "Light": ("#ECE8E3", "#161616", "#9E9EA0", "#F0582A", "#F4876C")},
    "Harbor":  {"Dark":  ("#092634", "#F4F4F2", "#5F7B8D", "#FF6E42", "#FF9A79"),
                "Light": ("#F4F4F2", "#092634", "#93A9B7", "#FF6E42", "#FF9A79")},
    "Emerald": {"Dark":  ("#0D4C3C", "#F4F1EB", "#6F8E80", "#9CC27A", "#7AA05A"),
                "Light": ("#F4F1EB", "#0D4C3C", "#AFC0B4", "#7AA05A", "#9CC27A")},
    "Juniper": {"Dark":  ("#2B2E1C", "#EFE9D7", "#898861", "#C2483F", "#D97A6C"),
                "Light": ("#EFE9D7", "#343723", "#B4B392", "#7D2826", "#A8453F")},
}
LAYOUTS = {"Rhythm": 7, "Pulse": 19, "Echo": 42}

def hx(c):
    c = c.lstrip("#"); return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))

class Layers:
    def __init__(self, size):
        self.size, self.masks = size, {}
    def _d(self, key):
        if key not in self.masks:
            m = Image.new("L", self.size, 0); self.masks[key] = (m, ImageDraw.Draw(m))
        return self.masks[key][1]
    def pieslice(self, box, a, b, fill):
        self._d(fill).pieslice(box, a, b, fill=255)
    def ellipse(self, box, fill):
        self._d(fill).ellipse(box, fill=255)

def half(dr, cx, cy, r, start, end, col):
    dr.pieslice((cx - r, cy - r, cx + r, cy + r), start, end, fill=col)

def cell(dr, x, y, s, gap, kind, ca, cb):
    x0, y0, x1, y1 = x + gap, y + gap, x + s - gap, y + s - gap
    t = x1 - x0; r = t / 2; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if kind == "bow_v":      # полукруги от верхнего и нижнего края навстречу друг другу
        half(dr, cx, y0, r, 0, 180, ca); half(dr, cx, y1, r, 180, 360, cb)
    elif kind == "bow_h":
        half(dr, x0, cy, r, -90, 90, ca); half(dr, x1, cy, r, 90, 270, cb)
    elif kind == "split_v":  # круг из двух половинок, разрез вертикальный
        half(dr, cx, cy, r, 90, 270, ca); half(dr, cx, cy, r, -90, 90, cb)
    elif kind == "split_h":
        half(dr, cx, cy, r, 180, 360, ca); half(dr, cx, cy, r, 0, 180, cb)
    elif kind == "dd_r":     # две «D», выпуклостью вправо
        half(dr, x0, cy, r, -90, 90, ca); half(dr, cx, cy, r, -90, 90, cb)
    elif kind == "dd_l":
        half(dr, x1, cy, r, 90, 270, ca); half(dr, cx, cy, r, 90, 270, cb)
    elif kind == "dd_d":
        half(dr, cx, y0, r, 0, 180, ca); half(dr, cx, cy, r, 0, 180, cb)
    elif kind == "dd_u":
        half(dr, cx, y1, r, 180, 360, ca); half(dr, cx, cy, r, 180, 360, cb)
    elif kind == "out_v":    # полукруги спиной друг к другу: «)(» по вертикали
        half(dr, cx, cy, r, 180, 360, ca); half(dr, cx, cy + 0.0001, r, 0, 180, cb)
    elif kind == "circle":
        dr.ellipse((x0, y0, x1, y1), fill=ca)

KINDS = ["bow_v"] * 4 + ["bow_h"] * 4 + ["dd_r", "dd_l", "dd_d", "dd_u"] * 2 + ["split_v", "split_h"]

def render(job):
    layout, pal, bgname, fmt = job
    W, H = FORMATS[fmt]
    if TEST: W, H = W // 3, H // 3
    bg, fg, grey, acc, acc2 = (hx(c) for c in PALETTES[pal][bgname])
    rnd = random.Random(LAYOUTS[layout] * 1000 + {"Mac": 1, "Ultrawide": 2, "iPhone": 3}[fmt])
    S = SS
    dr = Layers((W * S, H * S))
    portrait = H > W
    if portrait:
        cols = 4
        mx = W * 0.07; top = H * 0.30; bottom = H * 0.06     # верх свободен под часы iOS
        s = (W - 2 * mx) / cols
        rows = int((H - top - bottom) // s)
        oy = top + ((H - top - bottom) - rows * s) / 2
    else:
        # сетка во всю ширину, как на фото; сверху поле под строку меню, снизу под Dock
        cols = 8 if W / H < 2 else 12
        mx = W * 0.04
        s = (W - 2 * mx) / cols
        top, bottom = H * 0.06, H * 0.07
        rows = int((H - top - bottom) // s)
        oy = top + ((H - top - bottom) - rows * s) / 2
    ox = (W - cols * s) / 2
    gap = s * 0.10                     # больше воздуха между фигурами
    n = cols * rows
    # акценты: пара оранжевых кругов, пара оранжевых «D», несколько серых половинок
    # акценты разносим подальше друг от друга
    picked = []
    order = list(range(n)); rnd.shuffle(order)
    for k in order:
        i, j = k % cols, k // cols
        if all(abs(i - q % cols) + abs(j - q // cols) >= max(3, cols // 3) for q in picked):
            picked.append(k)
        if len(picked) == 4: break
    full_acc = set(picked[:2]); pair_acc = set(picked[2:4])
    rest = [k for k in order if k not in picked]
    greys = set(rest[:max(3, n // 12)])
    # прозрачность: большинство фигур плотные, часть — полупрозрачные и совсем лёгкие
    def op():
        return rnd.choices([0.92, 0.70, 0.45, 0.25], weights=[5, 3, 2, 1])[0]
    for k in range(n):
        i, j = k % cols, k // cols
        x, y = ox + i * s, oy + j * s
        kind = rnd.choice(KINDS)
        ca, cb = (fg, op()), (fg, op())
        if k in full_acc:
            kind = "circle"; ca = (acc2 if (k == min(full_acc)) else acc, 0.92)
        elif k in pair_acc:
            kind = rnd.choice(["bow_h", "bow_v", "dd_r", "dd_l"]); ca, cb = (acc, 0.92), (acc, 0.6)
        elif k in greys:
            if rnd.random() < .5: ca = (grey, 0.8)
            else: cb = (grey, 0.8)
        cell(dr, x * S, y * S, s * S, gap * S, kind, ca, cb)
    out = np.empty((H * S, W * S, 3), np.float32); out[:] = np.array(bg, np.float32)
    for (col, alpha), (m, _) in dr.masks.items():
        a = (np.asarray(m, np.float32) / 255 * alpha)[..., None]
        out = out * (1 - a) + np.array(col, np.float32) * a
    img = Image.fromarray(np.clip(out + .5, 0, 255).astype(np.uint8))
    img = img.resize((W, H), Image.LANCZOS)
    folder = os.path.join(OUT, fmt, bgname); os.makedirs(folder, exist_ok=True)
    img.save(os.path.join(folder, f"{PRE}_{layout}_{pal}_{bgname}.jpg"), quality=94, subsampling=0, optimize=True)
    return job

if __name__ == "__main__":
    jobs = [(l, p, b, f) for f in FORMATS for b in ("Dark", "Light") for l in LAYOUTS for p in PALETTES]
    if TEST:
        jobs = [j for j in jobs if j[0] == "Rhythm"]
    with Pool(os.cpu_count()) as pool:
        for _ in pool.imap_unordered(render, jobs): pass
    print("done", len(jobs))
