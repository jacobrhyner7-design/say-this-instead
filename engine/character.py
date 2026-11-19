"""The Toddler Translator toddler: one simple, recognizable character in four moods.

draw_toddler(mood, look, size) -> RGBA image
mood: mad | sad | calm | happy
look: dict from pick_look(seed): skin, hair colour, hair style, shirt colour.
Everything is drawn at 2x and scaled down so edges stay smooth.
"""
import math, random
from PIL import Image, ImageDraw

SKINS = [(255, 224, 196), (241, 194, 160), (224, 172, 128), (198, 140, 100), (160, 104, 70), (122, 78, 52)]
HAIRS = [(70, 48, 36), (40, 30, 26), (150, 96, 54), (214, 170, 96), (24, 20, 20), (120, 64, 40)]
SHIRTS = [(246, 196, 92), (138, 184, 222), (240, 160, 170), (152, 204, 160), (190, 168, 230), (244, 150, 110)]
# coily appears most often (about 4 in 10 videos); the rest stay varied
STYLES = ["coily", "coily", "coily", "coily", "tuft", "bob", "puffs", "curly", "tuft", "curly"]
INK = (52, 44, 52)


def pick_look(seed):
    r = random.Random(seed)
    return {"skin": r.choice(SKINS), "hair": r.choice(HAIRS), "style": r.choice(STYLES), "shirt": r.choice(SHIRTS)}


def _e(d, cx, cy, rx, ry, fill):
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=fill)


def _darker(c, f=0.82):
    return tuple(int(v * f) for v in c)


def draw_toddler(mood="calm", look=None, size=520, sparkles=True, blink=False):
    look = look or pick_look(1)
    S = size * 2
    img = Image.new("RGBA", (S, int(S * 1.25)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = S / 2
    R = S * 0.27            # head radius
    hy = R * 1.55           # head centre
    skin, hair, shirt = look["skin"], look["hair"], look["shirt"]

    # body
    by = hy + R * 1.55
    d.rounded_rectangle([cx - R * 0.78, by - R * 0.55, cx + R * 0.78, by + R * 0.95], radius=R * 0.55, fill=shirt)
    # arms: mood sets the pose
    arm = R * 0.22
    if mood == "mad":       # fists up
        for s in (-1, 1):
            d.line([cx + s * R * 0.6, by - R * 0.2, cx + s * R * 1.1, by - R * 0.75], fill=shirt, width=int(arm * 2))
            _e(d, cx + s * R * 1.12, by - R * 0.8, arm * 1.15, arm * 1.15, skin)
    elif mood == "happy":   # arms out wide
        for s in (-1, 1):
            d.line([cx + s * R * 0.6, by - R * 0.15, cx + s * R * 1.2, by - R * 0.55], fill=shirt, width=int(arm * 2))
            _e(d, cx + s * R * 1.24, by - R * 0.6, arm * 1.1, arm * 1.1, skin)
    else:                   # arms down, hugging in a little when sad
        k = 0.85 if mood == "sad" else 1.0
        for s in (-1, 1):
            d.line([cx + s * R * 0.62, by - R * 0.2, cx + s * R * 0.82 * k, by + R * 0.55], fill=shirt, width=int(arm * 2))
            _e(d, cx + s * R * 0.84 * k, by + R * 0.62, arm * 1.1, arm * 1.1, skin)
    # feet
    for s in (-1, 1):
        _e(d, cx + s * R * 0.38, by + R * 1.02, R * 0.3, R * 0.17, _darker(shirt, 0.55))

    # hair behind head
    st = look["style"]
    if st == "bob":
        d.chord([cx - R * 1.12, hy - R * 1.12, cx + R * 1.12, hy + R * 1.2], 180, 360, fill=hair)
        d.rectangle([cx - R * 1.12, hy - R * 0.05, cx - R * 0.78, hy + R * 0.55], fill=hair)
        d.rectangle([cx + R * 0.78, hy - R * 0.05, cx + R * 1.12, hy + R * 0.55], fill=hair)
    if st == "puffs":
        for s in (-1, 1):
            _e(d, cx + s * R * 0.95, hy - R * 0.75, R * 0.42, R * 0.42, hair)

    # ears + head
    for s in (-1, 1):
        _e(d, cx + s * R * 0.98, hy + R * 0.08, R * 0.2, R * 0.24, _darker(skin, 0.93))
    _e(d, cx, hy, R, R * 0.97, skin)

    # hair on top
    if st == "tuft":
        d.chord([cx - R * 0.95, hy - R * 1.02, cx + R * 0.95, hy + R * 0.2], 190, 350, fill=hair)
        d.arc([cx - R * 0.1, hy - R * 1.45, cx + R * 0.45, hy - R * 0.85], 120, 330, fill=hair, width=int(R * 0.12))
    elif st == "bob":
        d.chord([cx - R * 1.0, hy - R * 1.05, cx + R * 1.0, hy + R * 0.15], 180, 360, fill=hair)
    elif st == "puffs":
        d.chord([cx - R * 0.95, hy - R * 1.0, cx + R * 0.95, hy + R * 0.1], 185, 355, fill=hair)
    elif st == "coily":
        # volume sits on top of the head; the face stays clear. Small coils plus darker coil marks.
        dark = _darker(hair, 0.7)
        oy = hy - R * 0.22
        puffs = []
        for rad, n, rr in [(0.96, 11, 0.27), (1.1, 9, 0.23)]:
            for i in range(n):
                a = math.pi * (1.08 + i * 0.84 / (n - 1))
                puffs.append((cx + math.cos(a) * R * rad, oy + math.sin(a) * R * rad * 0.92, R * rr))
        for x, y, r in puffs:
            _e(d, x, y, r, r, hair)
        d.chord([cx - R * 1.0, hy - R * 1.12, cx + R * 1.0, hy + R * 0.02], 180, 360, fill=hair)
        for k, (x, y, r) in enumerate(puffs + [(cx + dx * R, hy + dy * R, R * 0.2) for dx, dy in
                                               [(-0.5, -0.62), (-0.15, -0.8), (0.2, -0.78), (0.52, -0.6), (0.0, -1.05)]]):
            d.arc([x - r * 0.45, y - r * 0.45, x + r * 0.45, y + r * 0.45], 40 + k * 47, 300 + k * 47,
                  fill=dark, width=max(3, int(R * 0.035)))
    elif st == "curly":
        for i in range(9):
            a = math.pi * (1.05 + i * 0.9 / 8)
            _e(d, cx + math.cos(a) * R * 0.85, hy + math.sin(a) * R * 0.85, R * 0.26, R * 0.26, hair)
        d.chord([cx - R * 0.9, hy - R * 0.95, cx + R * 0.9, hy + R * 0.05], 180, 360, fill=hair)

    # face
    ey, ex, er = hy + R * 0.08, R * 0.38, R * 0.1
    w = max(4, int(R * 0.07))
    if blink and mood != "calm":  # eyes shut for one blink frame
        for s in (-1, 1):
            d.line([cx + s * ex - er * 1.1, ey + er * 0.2, cx + s * ex + er * 1.1, ey + er * 0.2], fill=INK, width=w)
    elif mood == "calm":
        for s in (-1, 1):
            d.arc([cx + s * ex - er * 1.4, ey - er * 1.2, cx + s * ex + er * 1.4, ey + er * 1.2], 200, 340, fill=INK, width=w)
    else:
        for s in (-1, 1):
            _e(d, cx + s * ex, ey, er, er * 1.15, INK)
            _e(d, cx + s * ex + er * 0.35, ey - er * 0.4, er * 0.35, er * 0.35, (255, 255, 255))
    # brows
    bw = int(R * 0.06)
    if mood == "mad":
        for s in (-1, 1):
            d.line([cx + s * (ex + er * 1.6), ey - er * 2.6, cx + s * (ex - er * 1.2), ey - er * 1.5], fill=INK, width=bw)
    elif mood == "sad":
        for s in (-1, 1):
            d.line([cx + s * (ex + er * 1.5), ey - er * 1.6, cx + s * (ex - er * 1.1), ey - er * 2.5], fill=INK, width=bw)
    # cheeks
    for s in (-1, 1):
        ch = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(ch).ellipse([cx + s * R * 0.62 - R * 0.17, ey + R * 0.2 - R * 0.1,
                                    cx + s * R * 0.62 + R * 0.17, ey + R * 0.2 + R * 0.1], fill=(240, 120, 130, 110))
        img.alpha_composite(ch)
    d = ImageDraw.Draw(img)
    # mouth
    my = hy + R * 0.48
    if mood == "mad":
        _e(d, cx, my, R * 0.24, R * 0.17, INK)
        _e(d, cx, my + R * 0.08, R * 0.13, R * 0.07, (230, 120, 130))
    elif mood == "sad":
        d.arc([cx - R * 0.18, my - R * 0.02, cx + R * 0.18, my + R * 0.2], 200, 340, fill=INK, width=w)
        for s in (-1, 1):  # tears
            tx, ty = cx + s * ex, ey + er * 2.2
            d.polygon([(tx, ty - R * 0.08), (tx - R * 0.06, ty + R * 0.05), (tx + R * 0.06, ty + R * 0.05)], fill=(140, 190, 240))
            _e(d, tx, ty + R * 0.06, R * 0.065, R * 0.065, (140, 190, 240))
    elif mood == "calm":
        d.arc([cx - R * 0.2, my - R * 0.2, cx + R * 0.2, my + R * 0.06], 20, 160, fill=INK, width=w)
    else:  # happy: open smile
        d.chord([cx - R * 0.26, my - R * 0.2, cx + R * 0.26, my + R * 0.22], 0, 180, fill=INK)
        d.chord([cx - R * 0.14, my + R * 0.02, cx + R * 0.14, my + R * 0.2], 0, 180, fill=(230, 120, 130))

    # mood marks
    if mood == "mad":
        for s in (-1, 1):
            x0, y0 = cx + s * R * 1.25, hy - R * 0.75
            for k in range(3):
                a = math.radians(-90 + s * 35 + (k - 1) * 30)
                d.line([x0, y0, x0 + math.cos(a) * R * 0.28 * s, y0 + math.sin(a) * R * 0.28],
                       fill=(232, 98, 90), width=int(R * 0.06))
    if mood == "happy" and sparkles:
        for (dx, dy, r) in [(-1.35, -0.9, 0.09), (1.4, -0.6, 0.07), (1.2, -1.2, 0.05)]:
            _sparkle(d, cx + dx * R, hy + dy * R, R * r * 2.2, (246, 196, 92))
    return img.resize((size, int(size * 1.25)), Image.LANCZOS)


def _sparkle(d, x, y, s, col):
    d.polygon([(x, y - s), (x + s * 0.25, y - s * 0.25), (x + s, y), (x + s * 0.25, y + s * 0.25),
               (x, y + s), (x - s * 0.25, y + s * 0.25), (x - s, y), (x - s * 0.25, y - s * 0.25)], fill=col)


if __name__ == "__main__":
    sheet = Image.new("RGBA", (4 * 420, 3 * 500), (251, 246, 236, 255))
    for row in range(3):
        look = pick_look(row * 7 + 3)
        for i, m in enumerate(["mad", "sad", "calm", "happy"]):
            t = draw_toddler(m, look, 400)
            sheet.alpha_composite(t, (i * 420 + 10, row * 500 + 10))
    sheet.save("character_sheet.png")
