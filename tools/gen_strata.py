import numpy as np, os, sys
from PIL import Image
from multiprocessing import Pool

OUT = "STRATA"
FORMATS = {
    "Desktop 4K": (3840, 2160),
    "Ultrawide": (5120, 2160),
    "Mobile": (1290, 2796),
}

PALETTES = {
    "Sunset":   ["#FF5E3A", "#FFB347", "#E8336D", "#7A1FA2"],
    "Ocean":    ["#023E8A", "#0096C7", "#48CAE4", "#ADE8F4"],
    "Aurora":   ["#5A189A", "#2EC4B6", "#9EF01A", "#3A86FF"],
    "Berry":    ["#590D22", "#C9184A", "#FF758F", "#FFCCD5"],
    "Forest":   ["#1B4332", "#2D6A4F", "#52B788", "#D8F3DC"],
    "Citrus":   ["#FF7B00", "#FFB700", "#FFEA00", "#2EC4B6"],
    "Lavender": ["#3C096C", "#7B2CBF", "#C77DFF", "#E0AAFF"],
    "Mono":     ["#1C1C1E", "#5A5A5E", "#A1A1A6", "#EDEDED"],
}

BGS = {
    "Dark":  dict(bg=(14, 14, 16), shadow=0.55, vign=(0, 0, 0)),
    "Light": dict(bg=(240, 239, 235), shadow=0.20, vign=(205, 203, 198)),
}

def hx(c):
    c = c.lstrip("#"); return np.array([int(c[i:i+2], 16) for i in (0, 2, 4)], np.float32) / 255

def rot(px, py, a):
    c, s = np.cos(a), np.sin(a)
    return c * px + s * py, -s * px + c * py

def sd_circle(px, py, r):
    return np.sqrt(px * px + py * py) - r

def sd_capsule(px, py, half_len, r, a):
    x, y = rot(px, py, a)
    x = np.abs(x) - half_len
    x = np.maximum(x, 0)
    return np.sqrt(x * x + y * y) - r

def sd_tri(px, py, r, a, round_r):
    x, y = rot(px, py, a)
    y = -y  # y-up
    k = np.sqrt(3.0)
    r2 = r - round_r
    x = np.abs(x) - r2
    y = y + r2 / k
    m = x + k * y > 0
    nx = np.where(m, (x - k * y) / 2, x)
    ny = np.where(m, (-k * x - y) / 2, y)
    nx = nx - np.clip(nx, -2 * r2, 0)
    return -np.sqrt(nx * nx + ny * ny) * np.sign(ny) - round_r

# Motifs: list of (kind, cx, cy, params..., color_a, color_b) in u-units
MOTIFS = {
    "Orbit": [
        ("circle", 0.42, 0.30, 0.62, 0, 1),
        ("circle", 0.12, 0.06, 0.46, 1, 2),
        ("circle", -0.14, -0.14, 0.32, 2, 3),
        ("circle", -0.34, -0.30, 0.19, 3, 0),
    ],
    "Pills": [
        ("capsule", 0.38, 0.34, 0.62, 0.17, 0, 1),
        ("capsule", 0.14, 0.10, 0.52, 0.17, 1, 2),
        ("capsule", -0.10, -0.14, 0.42, 0.17, 2, 3),
        ("capsule", -0.34, -0.38, 0.30, 0.17, 3, 0),
    ],
    "Prism": [
        ("tri", 0.30, 0.22, 0.78, 0.10, 0, 1),
        ("tri", 0.06, 0.02, 0.56, 0.14, 1, 2),
        ("tri", -0.16, -0.16, 0.36, 0.18, 2, 3),
    ],
    "Blend": [
        ("circle", 0.40, 0.18, 0.58, 0, 1),
        ("capsule", -0.05, 0.24, 0.48, 0.16, 1, 2),
        ("tri", -0.10, -0.22, 0.34, 0.25, 2, 3),
        ("circle", -0.42, -0.02, 0.14, 3, 0),
    ],
}
CAP_ANGLE = np.deg2rad(-35)

def render(job):
    motif, pal, bgname, fmt = job
    W, H = FORMATS[fmt]
    B = BGS[bgname]
    cols = [hx(c) for c in PALETTES[pal]]
    if pal == "Mono" and bgname == "Dark":
        cols = [hx(c) for c in ["#3A3A3C", "#6E6E73", "#AEAEB2", "#F2F2F7"]]
    portrait = H > W
    u = W * 0.80 if portrait else H * 0.62
    acx = W * 0.47 if portrait else W * 0.62
    acy = H * 0.62 if portrait else H * 0.52

    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    # background with soft vignette
    bg = np.array(B["bg"], np.float32) / 255
    vg = np.array(B["vign"], np.float32) / 255
    d = np.sqrt(((xs - W / 2) / W) ** 2 + ((ys - H / 2) / H) ** 2) / 0.7
    v = np.clip(d, 0, 1) ** 2 * (0.6 if bgname == "Dark" else 0.5)
    img = bg[None, None, :] * (1 - v[..., None]) + vg[None, None, :] * v[..., None]

    shapes = MOTIFS[motif]
    gdir = np.array([np.cos(np.deg2rad(55)), np.sin(np.deg2rad(55))], np.float32)
    for sh in shapes:
        kind = sh[0]
        cx = acx + sh[1] * u
        cy = acy + sh[2] * u
        px, py = xs - cx, ys - cy
        if kind == "circle":
            r = sh[3] * u
            dist = sd_circle(px, py, r); size = r; ca, cb = sh[4], sh[5]
        elif kind == "capsule":
            hl, r = sh[3] * u, sh[4] * u
            dist = sd_capsule(px, py, hl, r, CAP_ANGLE); size = hl + r; ca, cb = sh[5], sh[6]
        else:
            r, rr = sh[3] * u, sh[4] * sh[3] * u
            dist = sd_tri(px, py, r, np.deg2rad(-12), rr); size = r; ca, cb = sh[5], sh[6]
        # soft shadow
        sw = 0.07 * u
        sdist = None
        off = 0.025 * u
        if kind == "circle":
            sdist = sd_circle(px - off, py - off * 1.4, sh[3] * u)
        elif kind == "capsule":
            sdist = sd_capsule(px - off, py - off * 1.4, sh[3] * u, sh[4] * u, CAP_ANGLE)
        else:
            sdist = sd_tri(px - off, py - off * 1.4, sh[3] * u, np.deg2rad(-12), sh[4] * sh[3] * u)
        sa = (1 - np.clip((sdist + sw * 0.3) / sw, 0, 1)) ** 2 * B["shadow"]
        img = img * (1 - sa[..., None])
        # gradient fill
        t = (px * gdir[0] + py * gdir[1]) / (2 * size) + 0.5
        t = np.clip(t, 0, 1)
        t = t * t * (3 - 2 * t)
        col = cols[ca][None, None, :] * (1 - t[..., None]) + cols[cb][None, None, :] * t[..., None]
        # subtle rim light
        rim = np.clip(1 - np.abs(dist + 0.006 * u) / (0.006 * u), 0, 1) * 0.10
        col = np.clip(col + rim[..., None], 0, 1)
        a = np.clip(0.5 - dist, 0, 1)
        img = img * (1 - a[..., None]) + col * a[..., None]

    # fine grain to kill banding
    rng = np.random.default_rng(hash(job) & 0xFFFF)
    img = img + rng.normal(0, 1.2 / 255, img.shape).astype(np.float32)
    out = (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
    folder = os.path.join(OUT, fmt, bgname)
    os.makedirs(folder, exist_ok=True)
    fn = os.path.join(folder, f"STRATA_{motif}_{pal}_{bgname}.jpg")
    Image.fromarray(out).save(fn, quality=95, subsampling=0)
    return fn

if __name__ == "__main__":
    jobs = [(m, p, b, f) for f in FORMATS for b in BGS for m in MOTIFS for p in PALETTES]
    if len(sys.argv) > 1:
        jobs = [j for j in jobs if j[1] == sys.argv[1] and j[3] == "Desktop 4K"]
    with Pool(os.cpu_count()) as pool:
        for i, fn in enumerate(pool.imap_unordered(render, jobs)):
            pass
    print("done", len(jobs))
