"""CASCADE — ряд капсул внахлёст с перетеканием цвета. Палитры — от пользователя.

python3 tools/gen_cascade.py          — весь пак
python3 tools/gen_cascade.py test     — быстрый тест в уменьшенном размере
"""
import numpy as np, os, sys
from PIL import Image
from multiprocessing import Pool

OUT = "/home/claude/CASCADE"
PRE = "CASCADE"
TEST = len(sys.argv) > 1 and sys.argv[1] == "test"
FORMATS = {"Mac": (4480, 3088), "Ultrawide": (5120, 2160), "iPhone": (1320, 2868)}
N = 18  # капсул в ряду
ALPHA = 0.55  # непрозрачность одной капсулы

# палитры с присланных карточек: светлый, второй светлый, акцент(ы), тёмный
PALETTES = {
    "Tangerine": dict(light="#FAF3E1", light2="#F5E7C6", accents=["#FF6D1F"], dark="#222222"),
    "Emerald":   dict(light="#F4F1EB", light2="#7AA05A", accents=["#2D5A4A"], dark="#0D4C3C"),
    "Juniper":   dict(light="#EFE9D7", light2="#898861", accents=["#7D2826"], dark="#343723"),
    "Harbor":    dict(light="#F9F9F9", light2="#FF6E42", accents=["#004E72"], dark="#092634"),
}

def hx(c):
    c = c.lstrip("#"); return np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], np.float64) / 255

# --- OKLab, чтобы переходы между цветами были ровными, без грязи ---
def lin(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def unlin(c): return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.clip(c, 0, None) ** (1 / 2.4) - 0.055)
def to_oklab(c):
    r, g, b = lin(c)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = np.cbrt(l), np.cbrt(m), np.cbrt(s)
    return np.array([0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
                     1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
                     0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s])
def from_oklab(o):
    L, a, b = o
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = np.array([4.0767416621 * l - 3.3077085654 * m + 0.2309667819 * s,
                    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
                    -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s])
    return np.clip(unlin(rgb), 0, 1)

def ramp(stops, n):
    """n цветов, равномерно по ломаной из опорных цветов в OKLab."""
    labs = [to_oklab(s) for s in stops]
    out = []
    for i in range(n):
        t = i / (n - 1) * (len(labs) - 1)
        k = min(int(t), len(labs) - 2); f = t - k
        out.append(from_oklab(labs[k] * (1 - f) + labs[k + 1] * f))
    return out

def colors(pal, bgname):
    P = PALETTES[pal]
    light, light2, acc, dark = hx(P["light"]), hx(P["light2"]), [hx(a) for a in P["accents"]], hx(P["dark"])
    if bgname == "Dark":
        bg = dark
        tail = from_oklab(to_oklab(acc[-1]) * 0.25 + to_oklab(dark) * 0.75)   # последняя капсула почти растворяется в фоне
        stops = [light, light2] + acc + [tail]
    else:
        bg = light
        tail = from_oklab(to_oklab(light2) * 0.3 + to_oklab(light) * 0.7)
        stops = [dark] + acc + [light2, tail]
    return bg, ramp(stops, N)

def render(job):
    pal, bgname, fmt = job
    W, H = FORMATS[fmt]
    if TEST: W, H = W // 3, H // 3
    portrait = H > W
    bg, cols = colors(pal, bgname)
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    img = np.empty((H, W, 3), np.float32); img[:] = bg
    if not portrait:
        # вертикальные капсулы в горизонтальный ряд (как на образце)
        ch, cw = 0.72 * H, 0.165 * H
        span = 1.10 * H
        x0 = W / 2 - span / 2; cy = H * 0.47
        step = (span - cw) / (N - 1)
        centers = [(x0 + cw / 2 + i * step, cy) for i in range(N)]
        hl, r = (ch - cw) / 2, cw / 2              # полудлина прямой части и радиус
        vertical = True
    else:
        # на телефоне — тот же ряд, повёрнутый на 90°: горизонтальные капсулы стопкой, ниже часов iOS
        cw, ch = 0.88 * W, 0.20 * W          # длина и толщина капсулы (пропорции как на Mac)
        span = 0.58 * H
        y0 = H * 0.33; cx = W / 2
        step = (span - ch) / (N - 1)
        centers = [(cx, y0 + ch / 2 + i * step) for i in range(N)]
        hl, r = (cw - ch) / 2, ch / 2
        vertical = False
    # «стекло»: идём спереди назад, каждая капсула пропускает часть света от лежащих под ней.
    # Смесь нормируем по самим капсулам, без фона, поэтому края не выцветают,
    # а в перекрытиях видны контуры и цвет соседних капсул.
    num = np.zeros((H, W, 3), np.float32); den = np.zeros((H, W), np.float32)
    trans = np.ones((H, W), np.float32); free = np.ones((H, W), np.float32)
    for i in range(N):
        cx, cy = centers[i]
        dx, dy = xs - cx, ys - cy
        if vertical:
            dy = np.maximum(np.abs(dy) - hl, 0)
        else:
            dx = np.maximum(np.abs(dx) - hl, 0)
        d = np.sqrt(dx * dx + dy * dy) - r
        cov = np.clip(0.5 - d, 0, 1)
        w = ALPHA * cov * trans
        num += w[..., None] * cols[i].astype(np.float32); den += w
        trans *= 1 - ALPHA * cov
        free *= 1 - cov
    mixc = num / np.maximum(den, 1e-6)[..., None]
    union = (1 - free)[..., None]
    img = img * (1 - union) + mixc * union
    rng = np.random.default_rng(abs(hash(job)) & 0xFFFF)
    img = img + rng.normal(0, 0.9 / 255, img.shape).astype(np.float32)
    folder = os.path.join(OUT, fmt, bgname); os.makedirs(folder, exist_ok=True)
    Image.fromarray((np.clip(img, 0, 1) * 255 + .5).astype(np.uint8)).save(
        os.path.join(folder, f"{PRE}_Row_{pal}_{bgname}.jpg"), quality=94, subsampling=0, optimize=True)
    return job

if __name__ == "__main__":
    jobs = [(p, b, f) for f in FORMATS for b in ("Dark", "Light") for p in PALETTES]
    with Pool(os.cpu_count()) as pool:
        for _ in pool.imap_unordered(render, jobs): pass
    print("done", len(jobs))
