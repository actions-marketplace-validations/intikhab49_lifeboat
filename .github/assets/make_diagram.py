"""Render the "how it's built" diagram in both themes (1280x400).

    python .github/assets/make_diagram.py
"""
import os

from PIL import Image, ImageDraw

from brand import ORANGE, P, THEMES, Layout, background, drop_shadow, finish, font, life_ring, text

W, H = 1280, 400
HERE = os.path.dirname(os.path.abspath(__file__))
CARD_W, CARD_H, GAP, TOP = 270, 250, 36, 74
LEFT = (W - (4 * CARD_W + 3 * GAP)) // 2
PAD = 24

STEPS = [
    ("Read the recipe", ["BUILD.txt inside", "Bitnami's package"]),
    ("Fill the gaps", ["from pg_config", "and the binaries"]),
    ("Build from source", ["19 archives,", "SHA-256 pinned"]),
    ("Prove it matches", ["76 of 76 checks", "identical"]),
]


def render(theme):
    t = THEMES[theme]
    img = background(W, H, theme, glow_at=(W / 2, H / 2), glow_radius=760, waves_from=0.9)
    layout = Layout(W, H, margin=16)
    title_font = font("bahnschrift.ttf", 29, "SemiBold SemiCondensed")
    sub_font = font("seguisb.ttf", 24)
    num_font = font("bahnschrift.ttf", 24, "Bold")

    cards = Image.new("RGBA", img.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(cards)
    boxes = []
    for i in range(4):
        x0 = LEFT + i * (CARD_W + GAP)
        box = (x0, TOP, x0 + CARD_W, TOP + CARD_H)
        boxes.append(box)
        edge = ORANGE if i == 3 else t["card_edge"]
        cd.rounded_rectangle(tuple(P(v) for v in box), radius=P(20), fill=t["card"], outline=edge,
                             width=P(3 if i == 3 else 2))
        layout.add(f"card {i + 1}", box)
    shadow, (ox, oy) = drop_shadow(cards, theme, offset=(0, 10), blur=14)
    img.alpha_composite(shadow, (ox, oy))
    img.alpha_composite(cards)

    d = ImageDraw.Draw(img)
    for i, (box, (title, sub)) in enumerate(zip(boxes, STEPS)):
        x0, y0, x1, y1 = box
        inner = (x0 + PAD, y0 + PAD - 4, x1 - PAD, y1 - PAD + 4)
        cx, cy = x0 + PAD + 22, y0 + PAD + 22
        d.ellipse((P(cx - 22), P(cy - 22), P(cx + 22), P(cy + 22)), fill=ORANGE)
        d.text((P(cx), P(cy + 1)), str(i + 1), font=num_font, fill=(255, 250, 244), anchor="mm")
        placed = [text(d, layout, f"title {i + 1}", (x0 + PAD, y0 + 132), title, title_font, t["ink"],
                       anchor="ls", may_overlap=(f"card {i + 1}",))]
        for j, line in enumerate(sub):
            placed.append(text(d, layout, f"sub {i + 1}.{j}", (x0 + PAD, y0 + 178 + j * 34), line, sub_font,
                               t["muted"], anchor="ls", may_overlap=(f"card {i + 1}",)))
        for b in placed:
            if b[0] < inner[0] or b[2] > inner[2] or b[1] < inner[1] or b[3] > inner[3]:
                layout.problems.append(f"text {b} spills out of card {i + 1}")
        if i < 3:  # arrow to the next card
            ax0, ax1, ay = x1 + 8, x1 + GAP - 8, (y0 + y1) / 2
            d.line((P(ax0), P(ay), P(ax1 - 9), P(ay)), fill=ORANGE, width=P(3))
            d.polygon([(P(ax1), P(ay)), (P(ax1 - 11), P(ay - 7)), (P(ax1 - 11), P(ay + 7))], fill=ORANGE)

    ring = life_ring(48, rope=False)
    rx = P(boxes[3][2] - PAD - 30) - ring.width // 2
    ry = P(boxes[3][1] + PAD + 22) - ring.height // 2
    img.alpha_composite(ring, (rx, ry))

    layout.check()
    return img


for theme in ("dark", "light"):
    finish(render(theme), W, H, os.path.join(HERE, f"how-it-is-built-{theme}.png"))
print("wrote how-it-is-built-dark.png, how-it-is-built-light.png")
