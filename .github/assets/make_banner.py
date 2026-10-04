"""Render the README banner in both themes and the GitHub social preview (1280x640).

    python .github/assets/make_banner.py
"""
import os

from PIL import Image, ImageDraw

from brand import ORANGE, P, THEMES, Layout, background, drop_shadow, finish, font, life_ring, text

W, H = 1280, 640
HERE = os.path.dirname(os.path.abspath(__file__))
RING_CENTER, RING_DIAMETER = (300, 320), 372
TEXT_X = 586


def render(theme):
    t = THEMES[theme]
    img = background(W, H, theme, glow_at=RING_CENTER, glow_radius=560, waves_from=0.66)
    layout = Layout(W, H, margin=24)

    ring = life_ring(RING_DIAMETER)
    shadow, (ox, oy) = drop_shadow(ring, theme, offset=(10, 18), blur=16)
    x0 = P(RING_CENTER[0]) - ring.width // 2
    y0 = P(RING_CENTER[1]) - ring.height // 2
    img.alpha_composite(shadow, (x0 + ox, y0 + oy))
    img.alpha_composite(ring, (x0, y0))
    r = RING_DIAMETER * 0.5 * 1.16
    layout.add("ring", (RING_CENTER[0] - r, RING_CENTER[1] - r, RING_CENTER[0] + r, RING_CENTER[1] + r))

    d = ImageDraw.Draw(img)
    word = font("bahnschrift.ttf", 148, "Bold")
    box = text(d, layout, "wordmark", (TEXT_X, 292), "lifeboat", word, t["ink"], anchor="ls")
    d.rectangle((P(TEXT_X + 4), P(320), P(TEXT_X + 92), P(327)), fill=ORANGE)
    layout.add("rule", (TEXT_X + 4, 320, TEXT_X + 92, 327))

    sub = font("seguisb.ttf", 36)
    text(d, layout, "subtitle 1", (TEXT_X, 382), "Bitnami's PostgreSQL image,", sub, t["ink"], anchor="ls")
    text(d, layout, "subtitle 2", (TEXT_X, 428), "rebuilt from upstream source.", sub, t["ink"], anchor="ls")

    mono = font("CascadiaMono.ttf", 25)
    text(d, layout, "facts", (TEXT_X, 506), "19 sources · SHA-256 pinned · amd64 + arm64", mono, t["muted"],
         anchor="ls")

    layout.check()
    return img


for theme in ("dark", "light"):
    finish(render(theme), W, H, os.path.join(HERE, f"banner-{theme}.png"))
finish(render("dark"), W, H, os.path.join(HERE, "social-preview.png"))
print("wrote banner-dark.png, banner-light.png, social-preview.png")
