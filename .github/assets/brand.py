"""Shared look for lifeboat's README images: palette, fonts, the life ring, a layout guard.

Two themes, "dark" (navy night sea) and "light" (warm paper), and one accent:
international orange, the colour of a life ring. Windows fonts (Bahnschrift, Segoe UI,
Cascadia Mono); on another OS point FONT_DIR at equivalents.
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 2  # draw at 2x, downsample once at the end
FONT_DIR = os.environ.get("FONT_DIR", "C:/Windows/Fonts/")
MIN_PX = 24  # smallest text a reader must parse, in final pixels

ORANGE = (255, 91, 31)
RING_WHITE = (247, 244, 238)
ROPE = (226, 211, 186)
ROPE_DARK = (168, 147, 116)

THEMES = {
    "dark": dict(bg=(10, 28, 48), glow=(22, 52, 84), ink=(243, 239, 230), muted=(205, 216, 228),
                 wave=(205, 216, 228, 20), card=(16, 40, 66), card_edge=(44, 74, 106),
                 shadow=(0, 0, 0, 150)),
    "light": dict(bg=(245, 241, 232), glow=(253, 251, 246), ink=(14, 42, 71), muted=(58, 84, 112),
                  wave=(14, 42, 71, 18), card=(255, 253, 249), card_edge=(212, 202, 184),
                  shadow=(14, 42, 71, 70)),
}


def P(v):
    return int(round(v * S))


def font(name, px, variation=None):
    assert px >= MIN_PX, f"{name} at {px}px is below the {MIN_PX}px floor"
    f = ImageFont.truetype(FONT_DIR + name, P(px))
    if variation:
        f.set_variation_by_name(variation.encode() if isinstance(variation, str) else variation)
    return f


class Layout:
    """Collects every block's box; refuses to write when one leaves the canvas or two collide."""

    def __init__(self, w, h, margin=0):
        self.w, self.h, self.margin = w, h, margin
        self.boxes, self.problems = [], []

    def add(self, name, box, may_overlap=()):
        x0, y0, x1, y1 = box
        m = self.margin
        if x0 < m or y0 < m or x1 > self.w - m or y1 > self.h - m:
            self.problems.append(f"{name} {tuple(round(v) for v in box)} leaves the {self.w}x{self.h} canvas")
        for other, ob in self.boxes:
            if other in may_overlap:
                continue
            if x0 < ob[2] and ob[0] < x1 and y0 < ob[3] and ob[1] < y1:
                self.problems.append(f"{name} overlaps {other}")
        self.boxes.append((name, box))

    def check(self):
        if self.problems:
            raise SystemExit("refusing to write the image:\n  " + "\n  ".join(self.problems))


def text(draw, layout, name, xy, s, fnt, fill, anchor="la", may_overlap=()):
    """Draw text at final-pixel coordinates and register its box with the layout guard."""
    x, y = xy
    draw.text((P(x), P(y)), s, font=fnt, fill=fill, anchor=anchor)
    b = draw.textbbox((P(x), P(y)), s, font=fnt, anchor=anchor)
    box = tuple(v / S for v in b)
    layout.add(name, box, may_overlap)
    return box


def background(w, h, theme, glow_at=None, glow_radius=520, waves_from=0.62):
    """Flat ground with a soft glow and faint sea lines along the lower part."""
    t = THEMES[theme]
    W, H = P(w), P(h)
    img = np.zeros((H, W, 3), dtype=np.float32)
    img[:] = t["bg"]
    if glow_at:
        yy, xx = np.mgrid[0:H, 0:W]
        d = np.hypot(xx - P(glow_at[0]), yy - P(glow_at[1])) / P(glow_radius)
        k = np.clip(1 - d, 0, 1) ** 2
        img += (np.array(t["glow"], dtype=np.float32) - np.array(t["bg"], dtype=np.float32)) * k[..., None]
    base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")
    lines = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lines)
    rows = 7
    for i in range(rows):
        y0 = h * waves_from + i * (h * (1 - waves_from) / rows)
        amp, period, phase = 5 + i * 1.5, 210 + i * 26, i * 0.9
        pts = [(P(x), P(y0 + amp * math.sin(2 * math.pi * x / period + phase))) for x in range(-10, w + 11, 6)]
        d.line(pts, fill=t["wave"], width=P(2))
    return Image.alpha_composite(base, lines)


def life_ring(diameter, angle_offset=22.5, rope=True):
    """A shaded life ring with four orange bands and, by default, grab lines, as RGBA at 2x.
    Leave the rope off below ~120 px, where it turns into clutter."""
    pad = 0.16
    size = P(diameter * (1 + 2 * pad))
    c = size / 2
    r_out = P(diameter / 2)
    r_in = r_out * 0.56
    r_mid, half = (r_out + r_in) / 2, (r_out - r_in) / 2

    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    dx, dy = xx - c, yy - c
    dist = np.hypot(dx, dy)
    theta = np.degrees(np.arctan2(dy, dx)) % 360
    t = np.clip((dist - r_mid) / half, -1, 1)

    # Torus normal, lit from the upper left.
    nz = np.sqrt(np.clip(1 - t * t, 0, 1))
    nx, ny = t * dx / np.maximum(dist, 1), t * dy / np.maximum(dist, 1)
    light = np.array([-0.45, -0.6, 0.66])
    light /= np.linalg.norm(light)
    diffuse = np.clip(nx * light[0] + ny * light[1] + nz * light[2], 0, 1)
    half_vec = light + np.array([0, 0, 1.0])
    half_vec /= np.linalg.norm(half_vec)
    spec = np.clip(nx * half_vec[0] + ny * half_vec[1] + nz * half_vec[2], 0, 1) ** 28

    orange = ((theta + angle_offset) // 45) % 2 == 0
    base = np.where(orange[..., None], np.array(ORANGE, np.float32), np.array(RING_WHITE, np.float32))
    shade = (0.50 + 0.62 * diffuse)[..., None]
    rgb = base * shade + 255 * 0.32 * spec[..., None]

    edge = np.clip(np.minimum(dist - r_in, r_out - dist) / 1.6 + 0.5, 0, 1)  # antialiased rim
    ring = np.dstack([np.clip(rgb, 0, 255), edge * 255]).astype(np.uint8)
    img = Image.fromarray(ring, "RGBA")
    if not rope:
        return img

    # Grab lines: four rope loops, fixed at the middle of the white bands.
    rope = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(rope)
    starts = [(45 * k + 45 - angle_offset + 22.5) % 360 for k in range(0, 8, 2)]
    for a in starts:
        pts = []
        for i in range(91):
            phi = math.radians(a + i)
            sag = math.sin(math.pi * i / 90)
            r = r_out + P(4) + sag * P(diameter * 0.075)
            pts.append((c + r * math.cos(phi), c + r * math.sin(phi)))
        d.line(pts, fill=ROPE_DARK, width=P(6.5), joint="curve")
        d.line(pts, fill=ROPE, width=P(4.5), joint="curve")
        for i in range(0, 91, 4):  # twist marks
            x, y = pts[i]
            d.ellipse((x - P(1), y - P(1), x + P(1), y + P(1)), fill=ROPE_DARK)
        for edge_angle in (a, a + 90):  # lashings across the ring
            phi = math.radians(edge_angle)
            for off in (-P(3), P(3)):
                ux, uy = math.cos(phi), math.sin(phi)
                vx, vy = -uy, ux
                x0, y0 = c + (r_in + P(2)) * ux + off * vx, c + (r_in + P(2)) * uy + off * vy
                x1, y1 = c + (r_out + P(5)) * ux + off * vx, c + (r_out + P(5)) * uy + off * vy
                d.line([(x0, y0), (x1, y1)], fill=ROPE_DARK, width=P(2.5))
    return Image.alpha_composite(img, rope)


def drop_shadow(rgba, theme, offset=(10, 16), blur=18):
    """A soft shadow from an RGBA sprite's alpha, same size as the sprite plus the offset."""
    t = THEMES[theme]
    alpha = rgba.split()[3]
    sh = Image.new("RGBA", rgba.size, t["shadow"][:3] + (0,))
    sh.putalpha(alpha.point(lambda v: v * t["shadow"][3] // 255))
    return sh.filter(ImageFilter.GaussianBlur(P(blur))), (P(offset[0]), P(offset[1]))


def finish(img, w, h, path):
    img.convert("RGB").resize((w, h), Image.LANCZOS).save(path, optimize=True)
