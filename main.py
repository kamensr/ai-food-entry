#!/usr/bin/env python3
"""make.fun food-picture-01 entry: a gourmet burger, rendered procedurally.

Python 3.13, stdlib only. Fully deterministic, no network.
Output: $MAKEFUN_OUTPUT/entry.png (default /output/entry.png), <=1024x1024, <=1MiB.
"""
import math
import os
import struct
import zlib

W = H = 840
CX = W / 2.0

# ---------------------------------------------------------------- utilities

def n2(x, y):
    """Deterministic per-pixel hash noise in [0,1)."""
    n = (int(x) * 374761393 + int(y) * 668265263) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFFFFFF) / 4294967295.0


def vnoise(x, y):
    """Smooth value noise (bilinear) in [0,1)."""
    xi, yi = math.floor(x), math.floor(y)
    fx, fy = x - xi, y - yi
    fx = fx * fx * (3 - 2 * fx)
    fy = fy * fy * (3 - 2 * fy)
    a = n2(xi, yi)
    b = n2(xi + 1, yi)
    c = n2(xi, yi + 1)
    d = n2(xi + 1, yi + 1)
    return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy


def smooth(t):
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    return t * t * (3 - 2 * t)


def ellipse_cov(dx, dy, rx, ry, soft=2.0):
    """Coverage in [0,1] for a point in a soft ellipse."""
    if rx <= 0 or ry <= 0:
        return 0.0
    d = math.sqrt((dx / rx) ** 2 + (dy / ry) ** 2)
    return smooth((1.0 - d) * min(rx, ry) / soft)


def blend(base, col, a):
    if a <= 0:
        return base
    return (
        base[0] + (col[0] - base[0]) * a,
        base[1] + (col[1] - base[1]) * a,
        base[2] + (col[2] - base[2]) * a,
    )


# ---------------------------------------------------------------- scene data

# Sesame seeds on the dome: (x, y, angle_deg, scale)
SEEDS = [
    (316, 262, 18, 1.00), (368, 226, -12, 1.05), (432, 214, 8, 1.00),
    (498, 232, -20, 1.05), (552, 270, 14, 0.95), (292, 306, -8, 0.95),
    (352, 292, 24, 1.00), (418, 276, -6, 1.05), (486, 286, 16, 1.00),
    (546, 314, -16, 0.95), (330, 334, 10, 0.90), (400, 326, -22, 0.95),
    (466, 330, 6, 0.95), (528, 344, -10, 0.85),
]

# Cheese drip positions: (dx from center, half-width, length)
DRIPS = [(-118, 9, 34), (-72, 8, 26), (-46, 11, 52), (30, 10, 40), (78, 8, 30), (104, 9, 58)]


def dome_cov(x, y):
    """Top-bun dome coverage (upper half ellipse)."""
    dx, dy = x - CX, y - 350.0
    if dy > 2:
        return 0.0
    dy = min(dy, 0.0)
    return ellipse_cov(dx, dy, 252, 168, soft=2.5)


def dome_shade(x, y):
    """Golden bun color with vertical gradient, rim bake and gloss."""
    dx, dy = x - CX, y - 350.0
    t = smooth(min(1.0, max(0.0, (-dy) / 168.0)))  # 0 at bottom, 1 at top
    r = 198 + 34 * t
    g = 130 + 42 * t
    b = 62 + 34 * t
    # rim darkening toward silhouette edge
    d = math.sqrt((dx / 252) ** 2 + (dy / 168) ** 2)
    edge = smooth((d - 0.78) / 0.22)
    r -= 46 * edge
    g -= 40 * edge
    b -= 26 * edge
    # glossy highlight upper-left
    hl = math.exp(-(((x - 340) / 95.0) ** 2 + ((y - 252) / 62.0) ** 2))
    r += 46 * hl
    g += 36 * hl
    b += 22 * hl
    # crisp secondary specular
    hl2 = math.exp(-(((x - 300) / 38.0) ** 2 + ((y - 232) / 26.0) ** 2))
    r += 40 * hl2
    g += 34 * hl2
    b += 24 * hl2
    # baked speckle
    sp = (vnoise(x * 0.09, y * 0.09) - 0.5) * 14
    return (r + sp, g + sp * 0.8, b + sp * 0.5)


def seed_cov(x, y):
    """Best coverage over all seeds; returns (cov, glint) or None."""
    for (sx, sy, ang, sc) in SEEDS:
        if abs(x - sx) > 9 * sc or abs(y - sy) > 7 * sc:
            continue
        a = math.radians(ang)
        dx, dy = x - sx, y - sy
        rx = dx * math.cos(a) + dy * math.sin(a)
        ry = -dx * math.sin(a) + dy * math.cos(a)
        c = ellipse_cov(rx, ry, 7 * sc, 4.4 * sc, soft=1.4)
        if c > 0:
            g = math.exp(-(((rx + 2.2 * sc) / (2.2 * sc)) ** 2
                           + ((ry + 1.4 * sc) / (1.6 * sc)) ** 2))
            return (c, g)
    return None


def lettuce_bottom(x):
    yb = 390 + 15 * math.sin(x * 0.05 + 0.8) + 6 * math.sin(x * 0.13 + 2.0)
    yb += 5 * math.sin(x * 0.021) * math.sin(x * 0.047 + 1.3)
    return yb


def cheese_cov(x, y):
    """Cheese band + drips."""
    band = ellipse_cov(x - CX, y - 408.0, 236, 20.0, soft=2.0)
    if band > 0.5:
        return 1.0
    dx = x - CX
    for (ddx, w, ln) in DRIPS:
        px = dx - ddx
        if abs(px) > w + 1:
            continue
        dy = y - 408.0
        if dy < -2 or dy > ln:
            continue
        if dy <= ln - w:
            cov = smooth((w - abs(px)) / 1.5)
        else:
            rr = math.sqrt(px ** 2 + (dy - (ln - w)) ** 2)
            cov = smooth((w - rr) / 1.5)
        if cov > 0:
            return cov
    return 0.0


def shade(x, y):
    """Full scene color for one pixel."""
    # -- background: warm radial gradient
    rdx, rdy = x - CX, y - 470.0
    rd = math.sqrt(rdx * rdx + rdy * rdy) / 560.0
    rd = min(rd, 1.0)
    col = (
        66 - 46 * rd,
        40 - 28 * rd,
        27 - 18 * rd,
    )
    # warm glow behind the burger
    gl = math.exp(-(((x - CX) / 330.0) ** 2 + ((y - 390) / 300.0) ** 2))
    col = blend(col, (150, 96, 52), 0.22 * gl)

    # -- drop shadow under plate
    sh = ellipse_cov(x - CX, y - 585.0, 335, 42, soft=8.0)
    col = blend(col, (12, 8, 6), 0.55 * sh)

    # -- plate
    pc = ellipse_cov(x - CX, y - 552.0, 322, 50, soft=2.5)
    if pc > 0:
        d = math.sqrt(((x - CX) / 322) ** 2 + ((y - 552.0) / 50) ** 2)
        pr = 234 - 34 * smooth((d - 0.7) / 0.3)
        pg = 228 - 36 * smooth((d - 0.7) / 0.3)
        pb = 216 - 40 * smooth((d - 0.7) / 0.3)
        sp = (vnoise(x * 0.15 + 40, y * 0.15) - 0.5) * 8
        col = blend(col, (pr + sp, pg + sp, pb + sp), pc)
        # front rim light arc
        if y > 552:
            rim = smooth((d - 0.86) / 0.06) * smooth((0.99 - d) / 0.05)
            col = blend(col, (255, 250, 240), 0.5 * rim)
        # inner shadow under the burger
        ins = ellipse_cov(x - CX, y - 548.0, 205, 16, soft=6.0)
        col = blend(col, (120, 96, 78), 0.4 * ins)

    # -- bottom bun
    bb = ellipse_cov(x - CX, y - 508.0, 226, 42, soft=2.0)
    if y > 508:
        bb = min(bb, smooth((552 - y) / 2.5))
    if bb > 0:
        t = smooth(min(1.0, max(0.0, (508 - y) / 42.0)))
        br = 208 + 22 * t
        bg2 = 150 + 26 * t
        bbv = 88 + 24 * t
        e = smooth((max(abs(x - CX) / 226.0, abs(y - 508.0) / 42.0) - 0.8) / 0.2)
        br -= 34 * e
        bg2 -= 28 * e
        bbv -= 20 * e
        sp = (vnoise(x * 0.11 + 7, y * 0.11 + 3) - 0.5) * 10
        col = blend(col, (br + sp, bg2 + sp, bbv + sp * 0.6), bb)

    # -- patty
    pt = ellipse_cov(x - CX, y - 462.0, 240, 38, soft=2.0)
    if pt > 0:
        v = vnoise(x * 0.16, y * 0.3)
        pr = 96 + 34 * v
        pg = 54 + 20 * v
        pb = 32 + 14 * v
        d = math.sqrt(((x - CX) / 240) ** 2 + ((y - 462.0) / 38) ** 2)
        e = smooth((d - 0.8) / 0.2)
        pr -= 30 * e
        pg -= 18 * e
        pb -= 12 * e
        if n2(x * 3 + 11, y * 3 + 5) > 0.94:  # char specks
            pr -= 34
            pg -= 24
            pb -= 16
        # grill marks: diagonal sear bands
        gm = math.sin((x + y) * 0.085 + 0.4)
        if gm > 0.35:
            k = smooth((gm - 0.35) / 0.4)
            pr -= 30 * k
            pg -= 20 * k
            pb -= 14 * k
        # juicy specular dots (rendered fat sizzling)
        jd = vnoise(x * 0.5 + 31, y * 0.9 + 17)
        if jd > 0.8:
            jk = smooth((jd - 0.8) / 0.2)
            pr += 60 * jk
            pg += 34 * jk
            pb += 20 * jk
        # juicy highlight sheen
        hl = math.exp(-(((x - 380) / 90.0) ** 2 + ((y - 452) / 14.0) ** 2))
        pr += 26 * hl
        pg += 12 * hl
        col = blend(col, (pr, pg, pb), pt)

    # -- cheese (band + drips), drawn over patty
    cc = cheese_cov(x, y)
    if cc > 0:
        v = vnoise(x * 0.12 + 21, y * 0.2 + 9)
        cr = 250 + 5 * v
        cg = 198 + 16 * v
        cb = 58 + 18 * v
        hl = math.exp(-(((x - 400) / 110.0) ** 2 + ((y - 402) / 8.0) ** 2))
        cr += 5 * hl
        cg += 22 * hl
        cb += 30 * hl
        # molten gloss streak along the band
        gloss = math.exp(-(((y - 400) / 5.0) ** 2))
        cr += 4 * gloss
        cg += 14 * gloss
        cb += 24 * gloss
        col = blend(col, (cr, cg, cb), cc)

    # -- tomato slice
    tc = ellipse_cov(x - CX, y - 384.0, 228, 27, soft=2.0)
    if tc > 0:
        d = math.sqrt(((x - CX) / 228) ** 2 + ((y - 384.0) / 27) ** 2)
        inner = smooth((d - 0.55) / 0.25)  # 0 center -> 1 rim
        tr = 234 - 52 * inner
        tg = 108 - 62 * inner
        tb = 84 - 46 * inner
        # seed pockets: faint lighter blobs
        angp = math.atan2((y - 384.0) / 27.0, (x - CX) / 228.0)
        seeds = math.sin(angp * 5.0 + 0.6)
        if 0.35 < d < 0.8:
            tr += 16 * max(0.0, seeds)
            tg += 6 * max(0.0, seeds)
        # moist rim highlight
        rimh = smooth((d - 0.8) / 0.18) * (1.0 - smooth((d - 0.97) / 0.03))
        tr += 26 * rimh
        tg += 10 * rimh
        col = blend(col, (tr, tg, tb), tc)

    # -- lettuce ruffle
    yb = lettuce_bottom(x)
    if 344 <= y <= yb + 2:
        lc = smooth((y - 344) / 2.0) * smooth((yb - y) / 2.0)
        v = vnoise(x * 0.2 + 55, y * 0.25)
        lr = 96 + 44 * v
        lg = 168 + 44 * v
        lb = 62 + 26 * v
        # rib highlights
        rib = math.exp(-((math.sin(x * 0.11 + 1.0)) ** 2) * 3.0)
        lr += 24 * rib
        lg += 26 * rib
        # pale frill tips at the ruffled edge
        tip = smooth((y - (yb - 7.0)) / 7.0)
        lr += 60 * tip
        lg += 58 * tip
        lb += 30 * tip
        col = blend(col, (lr, lg, lb), lc * 0.96)

    # -- top bun dome
    dc = dome_cov(x, y)
    if dc > 0:
        col = blend(col, dome_shade(x, y), dc)

    # -- sesame seeds (soft drop shadow on bun + specular glint)
    if y < 360:
        s = seed_cov(x, y)
        if s:
            c, gl = s
            shc = seed_cov(x + 2, y + 3)
            if shc is None:
                col = blend(col, (146, 94, 46), 0.5 * c)
            col = blend(col, (246, 228, 182), c)
            col = blend(col, (255, 252, 240), 0.85 * gl * c)

    # -- steam wisps (turbulent plume, widening and fading upward)
    for (wx, ph, amp) in ((352, 0.0, 18.0), (414, 2.1, 22.0), (470, 4.2, 15.0), (502, 5.6, 11.0)):
        ty = 196.0 - y  # 0 at y=196, grows upward
        if 30 <= ty <= 185:
            wob = (wx + amp * math.sin(y * 0.042 + ph)
                   + 6.0 * math.sin(y * 0.09 + ph * 2.3))
            fall = 1.0 - (ty - 30.0) / 155.0
            turb = 0.7 + 0.5 * vnoise(x * 0.03 + ph, y * 0.02)
            a = 0.26 * fall * turb * math.exp(-(((x - wob) / (10.0 + ty * 0.05)) ** 2))
            if a > 0.003:
                col = blend(col, (255, 246, 230), a)

    # -- vignette + film grain
    vd = math.sqrt((x - CX) ** 2 + (y - H / 2.0) ** 2) / (0.62 * W)
    vg = 1.0 - 0.34 * smooth((vd - 0.55) / 0.45)
    gr = (n2(x * 7 + 101, y * 7 + 59) - 0.5) * 6.0
    col = (
        col[0] * vg + gr,
        col[1] * vg + gr,
        col[2] * vg + gr,
    )
    return col


def render():
    buf = bytearray(W * H * 3)
    i = 0
    for y in range(H):
        for x in range(W):
            c = shade(x, y)
            r = int(min(255.0, max(0.0, c[0] + 0.5)))
            g = int(min(255.0, max(0.0, c[1] + 0.5)))
            b = int(min(255.0, max(0.0, c[2] + 0.5)))
            buf[i] = r
            buf[i + 1] = g
            buf[i + 2] = b
            i += 3
    return buf


def write_png(path, buf, w, h):
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)  # filter: none
        raw += buf[y * stride:(y + 1) * stride]

    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        c += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        return c

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT", "/output")
    buf = render()
    path = os.path.join(out_dir, "entry.png")
    size = write_png(path, buf, W, H)
    print(f"wrote {path} ({W}x{H}, {size} bytes)")


if __name__ == "__main__":
    main()
