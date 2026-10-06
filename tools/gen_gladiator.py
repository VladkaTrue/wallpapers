import numpy as np, os, sys
from PIL import Image
from multiprocessing import Pool

OUT = "/home/claude/GLADIATOR"
PRE = "GLADIATOR"
FORMATS = {"Desktop 4K": (3840, 2160), "Ultrawide": (5120, 2160), "Mobile": (1290, 2796)}

RED, DEEP, BONE, INK = "#D3122B", "#7A0915", "#F2EFE9", "#151517"
# A — основной, B — тень основного, C — контраст, D — второй акцент
PALETTES = {
    "Crimson": [RED, DEEP, BONE, INK],
    "Iron":    ["#38383D", "#18181A", RED, BONE],
    "Bone":    [BONE, "#CBC6BE", RED, INK],
    "Ember":   [RED, INK, "#4A0610", BONE],
}
BGS = {
    "Dark":  dict(bg=(17, 17, 19), vign=(0, 0, 0), shadow=0.6),
    "Light": dict(bg=(238, 236, 232), vign=(206, 203, 198), shadow=0.22),
}

def hx(c):
    c = c.lstrip("#"); return np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255

def mix(a, b, t):
    return a[None, None, :] * (1 - t[..., None]) + b[None, None, :] * t[..., None]

def sstep(t):
    t = np.clip(t, 0, 1); return t * t * (3 - 2 * t)

def hash2(i, j, seed=0):
    h = (i * 374761393 + j * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0

class Canvas:
    def __init__(s, W, H, bgname):
        s.W, s.H = W, H
        s.B = BGS[bgname]
        s.ys, s.xs = np.mgrid[0:H, 0:W].astype(np.float32)
        bg = np.array(s.B["bg"], np.float32) / 255; vg = np.array(s.B["vign"], np.float32) / 255
        d = np.sqrt(((s.xs - W / 2) / W) ** 2 + ((s.ys - H / 2) / H) ** 2) / 0.7
        v = np.clip(d, 0, 1) ** 2 * (0.6 if bgname == "Dark" else 0.5)
        s.img = mix(bg, vg, v)

    def layer(s, sdf_fn, col, u, shadow=True):
        """sdf_fn(px, py) -> signed distance (px); col — HxWx3."""
        if shadow:
            off = 0.022 * u; sw = 0.07 * u
            sd = sdf_fn(s.xs - off, s.ys - off * 1.4)
            sa = (1 - np.clip((sd + sw * 0.3) / sw, 0, 1)) ** 2 * s.B["shadow"]
            s.img *= (1 - sa[..., None])
        d = sdf_fn(s.xs, s.ys)
        rim = np.clip(1 - np.abs(d + 0.005 * u) / (0.005 * u), 0, 1) * 0.08
        col = np.clip(col + rim[..., None], 0, 1)
        a = np.clip(0.5 - d, 0, 1)
        s.img = s.img * (1 - a[..., None]) + col * a[..., None]

    def lin_grad(s, c1, c2, ang, cx, cy, size):
        g = np.array([np.cos(np.deg2rad(ang)), np.sin(np.deg2rad(ang))], np.float32)
        t = ((s.xs - cx) * g[0] + (s.ys - cy) * g[1]) / (2 * size) + 0.5
        return mix(c1, c2, sstep(t))

# ---------------- мотивы ----------------

def m_scales(cv, P, u, ax, ay, portrait):
    """Чешуйчатый доспех: ромбы-заклёпки с гранями, полоса контрастных чешуек."""
    A, B, C, D = P
    s = u * 0.115                                  # размер чешуйки
    r2 = 1 / np.sqrt(2)
    X = (cv.xs - ax) / s; Y = (cv.ys - ay) / s
    xr, yr = (X + Y) * r2, (Y - X) * r2            # повёрнутая сетка
    i, j = np.floor(xr), np.floor(yr)
    fx, fy = xr - i, yr - j
    ii, jj = i.astype(np.int64), j.astype(np.int64)
    rnd = hash2(ii, jj)
    # центр ячейки в экранных координатах
    ccx = ((i + .5) - (j + .5)) * r2 * s + ax
    ccy = ((i + .5) + (j + .5)) * r2 * s + ay
    # видимость: диагональное поле, край рассыпается
    if portrait:
        f = (ccy - cv.H * 0.30) / (cv.H * 0.45)
    else:
        f = ((ccx - cv.W * 0.42) * 0.8 + (ccy - cv.H * 0.1) * 0.35) / (cv.W * 0.32)
    vis = (f + (rnd - 0.5) * 0.55) > 0
    # цвет: основной с вариацией, полоса контрастных чешуек вдоль ряда
    # ряд вдоль диагонали (константа xr): берём ряд, проходящий через видимую часть
    k = int(np.floor(((cv.W * (0.50 if portrait else 0.80)) + (cv.H * (0.62 if portrait else 0.55)) - ax - ay) / s * r2))
    band = ii == k
    band2 = ii == k + 2
    base_t = np.clip(0.25 + (rnd - 0.5) * 0.5 + f.clip(0, 2) * 0.2, 0, 1)
    col = mix(A, B, base_t)
    col = np.where(band[..., None], mix(C, C * 0.86, rnd * 0.4), col)
    col = np.where((band2 & (rnd > 0.55))[..., None], mix(D, D * 0.8, rnd * 0.3), col)
    # грани: светлая верхняя-левая, тёмная правая-нижняя
    facet = np.where(fx > fy, 1.07, 0.93) * np.where(fx + fy < 1, 1.05, 0.9)
    edge = np.minimum(np.minimum(fx, 1 - fx), np.minimum(fy, 1 - fy)) * s   # px до края
    ao = 0.78 + 0.22 * np.clip(edge / (0.12 * s), 0, 1)
    col = np.clip(col * (facet * ao)[..., None], 0, 1)
    # блик по центральной грани
    ridge = np.clip(1 - np.abs(fx - fy) * s / (0.02 * s + 1.5), 0, 1) * 0.06
    col = np.clip(col + ridge[..., None], 0, 1)
    gap = 0.045 * s
    a = np.clip(edge - gap, 0, 1) * vis
    # тень под чешуйками
    sa = np.clip(edge / (gap * 2.5), 0, 1) * vis * cv.B["shadow"] * 0.6
    cv.img *= (1 - sa[..., None] * (1 - a[..., None]))
    cv.img = cv.img * (1 - a[..., None]) + col * a[..., None]

def m_stripes(cv, P, u, ax, ay, portrait):
    """Диагональные полосы-перевязь со слоями и тенями."""
    A, B, C, D = P
    ang = np.deg2rad(-62 if portrait else -28)
    n = np.array([np.sin(ang), -np.cos(ang)], np.float32)   # нормаль к полосе
    bands = [  # (смещение центра, ширина, c1, c2)
        (0.30, 0.50, B, A),
        (-0.02, 0.10, C, C * 0.9),
        (-0.21, 0.24, A, B),
        (-0.39, 0.05, D, D),
        (0.62, 0.07, C, C * 0.9),
    ]
    for off, w, c1, c2 in bands:
        o, hw = off * u, w * u / 2
        def sdf(px, py, o=o, hw=hw):
            p = (px - ax) * n[0] + (py - ay) * n[1]
            return np.abs(p - o) - hw
        col = cv.lin_grad(c1, c2, np.rad2deg(ang), ax, ay, u * 0.9)
        cv.layer(sdf, col, u)

def m_arena(cv, P, u, ax, ay, portrait):
    """Арена: концентрические кольца, вид сверху."""
    A, B, C, D = P
    rings = [(1.00, B, A), (0.82, A, B), (0.66, C, C * 0.88), (0.60, A, B), (0.44, D, D * 0.8), (0.38, B, A), (0.20, C, C * 0.88)]
    for r, c1, c2 in rings:
        R = r * u
        sdf = lambda px, py, R=R: np.sqrt((px - ax) ** 2 + (py - ay) ** 2) - R
        cv.layer(sdf, cv.lin_grad(c1, c2, 230, ax, ay, R), u)

def sd_seg(px, py, ax, ay, bx, by):
    pax, pay = px - ax, py - ay; bax, bay = bx - ax, by - ay
    h = np.clip((pax * bax + pay * bay) / (bax * bax + bay * bay), 0, 1)
    dx, dy = pax - bax * h, pay - bay * h
    return np.sqrt(dx * dx + dy * dy)

def m_chevron(cv, P, u, ax, ay, portrait):
    """Клинки: вложенные шевроны остриём вверх."""
    A, B, C, D = P
    half_w, depth, th = 0.62 * u, 0.42 * u, 0.085 * u
    stack = [(0.52, B, A), (0.30, C, C * 0.88), (0.08, A, B), (-0.14, D, D * 0.8), (-0.36, A, B)]
    for dy, c1, c2 in reversed(stack):
        tx, ty = ax, ay + dy * u
        def sdf(px, py, tx=tx, ty=ty):
            l = sd_seg(px, py, tx, ty, tx - half_w, ty + depth)
            r = sd_seg(px, py, tx, ty, tx + half_w, ty + depth)
            return np.minimum(l, r) - th
        cv.layer(sdf, cv.lin_grad(c1, c2, 90, tx, ty + depth / 2, depth), u)

MOTIFS = {"Scales": m_scales, "Stripes": m_stripes, "Arena": m_arena, "Chevron": m_chevron}

# якоря композиции: (u, ax, ay) как доли
LAYOUT = {
    "Scales":  dict(land=(1.0, 0.00, 0.00), port=(1.0, 0.0, 0.0)),
    "Stripes": dict(land=(0.95, 0.78, 0.60), port=(1.25, 0.55, 0.66)),
    "Arena":   dict(land=(0.95, 0.80, 0.86), port=(1.25, 0.70, 0.88)),
    "Chevron": dict(land=(0.62, 0.68, 0.36), port=(0.80, 0.50, 0.50)),
}

def render(job):
    motif, pal, bgname, fmt = job
    W, H = FORMATS[fmt]
    portrait = H > W
    P = [hx(c) for c in PALETTES[pal]]
    cv = Canvas(W, H, bgname)
    ku, kx, ky = LAYOUT[motif]["port" if portrait else "land"]
    u = (W if portrait else H) * ku
    if motif == "Scales":
        ax, ay = 0.0, 0.0
        u = (W * 1.15) if portrait else H
    else:
        ax, ay = W * kx, H * ky
    MOTIFS[motif](cv, P, u, ax, ay, portrait)
    rng = np.random.default_rng(abs(hash(job)) & 0xFFFF)
    img = cv.img + rng.normal(0, 1.2 / 255, cv.img.shape).astype(np.float32)
    out = (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
    folder = os.path.join(OUT, fmt, bgname); os.makedirs(folder, exist_ok=True)
    fn = os.path.join(folder, f"{PRE}_{motif}_{pal}_{bgname}.jpg")
    Image.fromarray(out).save(fn, quality=95, subsampling=0)
    return fn

if __name__ == "__main__":
    jobs = [(m, p, b, f) for f in FORMATS for b in BGS for m in MOTIFS for p in PALETTES]
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        jobs = [j for j in jobs if j[1] in ("Crimson",) and j[3] != "Ultrawide"]
    with Pool(os.cpu_count()) as pool:
        for _ in pool.imap_unordered(render, jobs): pass
    print("done", len(jobs))
