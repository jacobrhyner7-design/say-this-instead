"""Say This Instead video renderer (built from the Toddler Translator engine). 1080x1920, calm illustrated cards, voiceover, soft music.

Two formats:
  translator: "When your toddler says..." -> "What it really means" -> "Say this instead" -> outro
  swap:       "Stop saying these 3 things" -> 3 x (Instead of / Try) -> outro

Usage: python3 make_video.py post.json out.mp4 [--seed N]
"""
import argparse, json, math, os, random, re, subprocess, tempfile
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from character import draw_toddler, pick_look
from feel_hooks import feel_hook
from hooks import hook as cold_hook
from voice import speak

W, H = 1080, 1920
FPS = 30
HERE = os.path.dirname(os.path.abspath(__file__))
F = lambda n: os.path.join(HERE, "fonts", n)
CREAM = (251, 246, 236)
NAVY = (43, 47, 69)
SOFT = (107, 111, 134)
PURPLE = (220, 96, 78)    # coral: 'what they really mean'
GREEN = (190, 134, 28)    # deep mustard: 'say this instead'
RED = (214, 92, 84)
GOLD = (233, 185, 73)
BRAND = "Say This Instead"  # shown on every video; no handle, so the same video works on TikTok and Instagram
X0, X1 = 80, 940          # keep text clear of TikTok's right-side buttons
SAFE_BOTTOM = 1520        # caption and username cover the bottom of the screen


def font(name, size, weight=None):
    f = ImageFont.truetype(F(name), size)
    if weight:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


def bold(s): return font("Poppins-Bold.ttf", s)
def medium(s): return font("Poppins-Medium.ttf", s)
def serif(s): return font("Lora-Variable.ttf", s, 500)
def serif_i(s): return font("Lora-Italic-Variable.ttf", s, 500)


def wrap(text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.getlength(t) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit(text, maker, max_w, max_h, start, lead=1.25, lo=34):
    s = start
    while s > lo:
        f = maker(s)
        rows = wrap(text, f, max_w)
        if len(rows) * s * lead <= max_h:
            return f, rows, int(s * lead)
        s -= 3
    f = maker(lo)
    return f, wrap(text, f, max_w), int(lo * lead)


_WORDS = None   # when a list, draw_rows records each word's box (for words popping in as they are spoken)
_HIDE = False   # when True, draw_rows draws nothing (the card without its words)


HALO = (251, 244, 230)  # soft paper-colour glow around words, instead of a box behind them


def halo_text(img, xy, text, font_, fill, anchor="la", glow=HALO):
    """Text with a soft glow hugging the letters, so it reads on any picture without a rectangle behind it."""
    if glow is not None and getattr(img, "mode", "") == "RGBA":
        m = Image.new("L", img.size, 0)
        ImageDraw.Draw(m).text(xy, text, font=font_, fill=255, anchor=anchor, stroke_width=7, stroke_fill=255)
        m = m.filter(ImageFilter.GaussianBlur(9)).point(lambda v: min(255, int(v * 1.5)))
        g = Image.new("RGBA", img.size, glow + (0,)); g.putalpha(m)
        img.alpha_composite(g)
    ImageDraw.Draw(img).text(xy, text, font=font_, fill=fill, anchor=anchor)


def draw_rows(d, rows, f, lh, x, y, fill, center=False, width=None):
    for r in rows:
        tx = x + (width - f.getlength(r)) / 2 if center else x
        if _WORDS is not None:
            sp = f.getlength(" ")
            wx = tx
            for wd in r.split():
                wl = f.getlength(wd)
                _WORDS.append((wd, (int(wx - 6), int(y - 8), int(wx + wl + 8), int(y + lh * 0.95))))
                wx += wl + sp
        if not _HIDE:
            img = getattr(d, "_image", None)
            if img is not None and getattr(img, "mode", "") == "RGBA":
                halo_text(img, (tx, y), r, f, fill)
            else:
                d.text((tx, y), r, font=f, fill=fill)
        y += lh
    return y


def background(seed):
    r = random.Random(seed)
    img = Image.new("RGB", (W, H), CREAM)
    tints = [(244, 214, 200), (214, 222, 242), (226, 236, 214), (240, 226, 196)]
    for _ in range(4):
        cx, cy, rr = r.randint(-100, W + 100), r.randint(200, H - 200), r.randint(260, 420)
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=150)
        img.paste(Image.new("RGB", (W, H), r.choice(tints)), (0, 0), m.filter(ImageFilter.GaussianBlur(90)))
    d = ImageDraw.Draw(img)
    # brand mark: tiny moon and handle at the top
    mx, my = W / 2 - bold(32).getlength(BRAND) / 2 - 34, 118
    d.rounded_rectangle([mx - 18, my - 16, mx + 18, my + 12], radius=9, fill=(220, 96, 78))
    d.polygon([(mx - 8, my + 10), (mx - 14, my + 22), (mx + 2, my + 11)], fill=(220, 96, 78))
    d.text((mx + 30, my - 22), BRAND, font=bold(32), fill=NAVY)
    for _ in range(10):
        sx, sy, s = r.randint(60, W - 60), r.randint(170, 1500), r.choice([6, 8, 11])
        d.polygon([(sx, sy - s), (sx + s * .25, sy - s * .25), (sx + s, sy), (sx + s * .25, sy + s * .25),
                   (sx, sy + s), (sx - s * .25, sy + s * .25), (sx - s, sy), (sx - s * .25, sy - s * .25)],
                  fill=(233, 185, 73, 255))
    return img


def pill(d, text, x, y, fill, color=(255, 255, 255), size=34, center=False):
    f = bold(size)
    w = f.getlength(text) + 56
    if center:
        x = (W - w) / 2
    d.rounded_rectangle([x, y, x + w, y + size + 34], radius=(size + 34) / 2, fill=fill)
    d.text((x + 28, y + 12), text, font=f, fill=color)
    return y + size + 34


def card(img, box, fill=(255, 255, 255), radius=36, shadow=True):
    x0, y0, x1, y1 = box
    if shadow:
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([x0, y0 + 10, x1, y1 + 10], radius=radius, fill=(60, 50, 80, 40))
        sh = sh.filter(ImageFilter.GaussianBlur(16))
        img.paste(sh, (0, 0), sh)
    ImageDraw.Draw(img).rounded_rectangle(box, radius=radius, fill=fill)


def place(img, toddler, cx, top):
    img.paste(toddler, (int(cx - toddler.width / 2), int(top)), toddler)


SPRITES = None  # when a list, toddlers are recorded here (for animation) instead of painted


def toddler_in(img, mood, look, top, want, bottom=SAFE_BOTTOM):
    """Draw the toddler as big as `want` but never past `bottom`. Returns its bottom edge."""
    size = int(max(260, min(want, (bottom - top) / 1.25)))
    if SPRITES is not None:
        SPRITES.append({"mood": mood, "look": look, "size": size, "top": int(top)})
        return top + int(size * 1.25)
    t = draw_toddler(mood, look, size)
    place(img, t, W / 2, top)
    return top + t.height


# ---------- translator ----------
def tr_hook(p, look, seed):
    img = background(seed); d = ImageDraw.Draw(img)
    y = pill(d, p["topic"].upper(), 0, 190, NAVY, center=True)
    action = p["says"].startswith("*")
    d.text((W / 2, y + 70), "When your toddler..." if action else "When your toddler says...",
           font=bold(64), fill=NAVY, anchor="mm")
    quote = p["says"].strip("* ") if action else f"“{p['says']}”"
    f, rows, lh = fit(quote, bold, X1 - X0 - 120, 300, 100)
    bh = len(rows) * lh + 90
    by = y + 140
    card(img, [X0, by, X1, by + bh], radius=48)
    d = ImageDraw.Draw(img)
    d.polygon([(W / 2 - 40, by + bh - 2), (W / 2 + 40, by + bh - 2), (W / 2, by + bh + 50)], fill=(255, 255, 255))
    draw_rows(d, rows, f, lh, X0 + 60, by + 45, NAVY, center=True, width=X1 - X0 - 120)
    toddler_in(img, "mad", look, by + bh + 100, 600)
    return img


def tr_means(p, look, seed):
    img = background(seed); d = ImageDraw.Draw(img)
    y = pill(d, "WHAT THEY REALLY MEAN", 0, 260, PURPLE, center=True)
    text = " ".join(p["means"])
    f, rows, lh = fit(text, serif, X1 - X0 - 120, 520, 70, lead=1.35)
    bh = len(rows) * lh + 100
    card(img, [X0, y + 60, X1, y + 60 + bh])
    d = ImageDraw.Draw(img)
    draw_rows(d, rows, f, lh, X0 + 60, y + 110, NAVY, center=True, width=X1 - X0 - 120)
    toddler_in(img, "sad", look, y + 130 + bh, 580)
    return img


def tr_say(p, look, seed):
    img = background(seed); d = ImageDraw.Draw(img)
    y = pill(d, "SAY THIS INSTEAD", 0, 230, GREEN, center=True) + 50
    lines = p["say"]
    avail = 760
    per = avail / len(lines) - 28
    for ln in lines:
        f, rows, lh = fit(f"“{ln}”", serif_i, X1 - X0 - 130, per - 60, 60, lead=1.3, lo=40)
        bh = len(rows) * lh + 60
        card(img, [X0, y, X1, y + bh], radius=30)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([X0, y, X0 + 16, y + bh], radius=8, fill=GREEN)
        draw_rows(d, rows, f, lh, X0 + 60, y + 28, NAVY)
        y += bh + 28
    toddler_in(img, "calm", look, y + 30, 480)
    return img


def outro(p, look, seed):
    img = background(seed); d = ImageDraw.Draw(img)
    d.text((W / 2, 300), "Save this for tonight", font=bold(68), fill=NAVY, anchor="mm")
    f, rows, lh = fit(p["cta"], bold, X1 - X0 - 120, 300, 66)
    bh = len(rows) * lh + 130
    card(img, [X0, 390, X1, 390 + bh], fill=(255, 244, 214), radius=44)
    d = ImageDraw.Draw(img)
    d.text((W / 2, 435), "TELL ME IN THE COMMENTS", font=bold(28), fill=(176, 128, 30), anchor="mm")
    draw_rows(d, rows, f, lh, X0 + 60, 480, NAVY, center=True, width=X1 - X0 - 120)
    end = toddler_in(img, "happy", look, 390 + bh + 60, 600, bottom=SAFE_BOTTOM - 70)
    d = ImageDraw.Draw(img)
    foot = p.get("footer") or "Follow for a new script every day"
    d.text((W / 2, end + 40), foot, font=bold(36) if p.get("footer") else medium(36),
           fill=GREEN if p.get("footer") else SOFT, anchor="mm")
    return img


# ---------- swap ----------
def sw_hook(p, look, seed):
    img = background(seed); d = ImageDraw.Draw(img)
    y = pill(d, p["topic"].upper(), 0, 190, NAVY, center=True)
    f, rows, lh = fit(p["title"], bold, X1 - X0, 360, 92)
    y = draw_rows(d, rows, f, lh, X0, y + 60, NAVY, center=True, width=X1 - X0)
    d.text((W / 2, y + 40), "and what to say instead", font=serif_i(52), fill=GREEN, anchor="mm")
    toddler_in(img, "sad", look, y + 130, 620)
    return img


def sw_pair(p, i, look, seed):
    a, b = p["pairs"][i]
    img = background(seed); d = ImageDraw.Draw(img)
    d.text((W / 2, 260), f"{i + 1} of {len(p['pairs'])}", font=bold(34), fill=SOFT, anchor="mm")
    y = 320
    for label, text, col, good in (("INSTEAD OF", a, RED, False), ("TRY", b, GREEN, True)):
        y = pill(d, label, X0, y, col) + 22
        f, rows, lh = fit(f"“{text}”", serif_i if good else serif, X1 - X0 - 170, 300, 64, lead=1.3, lo=40)
        bh = len(rows) * lh + 70
        card(img, [X0, y, X1, y + bh], fill=(255, 255, 255) if good else (250, 236, 232), radius=32)
        d = ImageDraw.Draw(img)
        draw_rows(d, rows, f, lh, X0 + 50, y + 34, NAVY if good else (150, 110, 106))
        ix, iy = X1 - 60, y + bh / 2
        d.ellipse([ix - 34, iy - 34, ix + 34, iy + 34], fill=col)
        if good:
            d.line([ix - 16, iy, ix - 4, iy + 13, ix + 18, iy - 14], fill="white", width=9, joint="curve")
        else:
            d.line([ix - 14, iy - 14, ix + 14, iy + 14], fill="white", width=9)
            d.line([ix - 14, iy + 14, ix + 14, iy - 14], fill="white", width=9)
        y += bh + 50
    toddler_in(img, "happy" if i == len(p["pairs"]) - 1 else "calm", look, y, 500)
    return img


# ---------- illustrated scenes: a new storybook picture for every card ----------
SCENE_DIR = os.path.join(HERE, "scenes")
TOPIC_TAG = {"tired parent": "tired", "mom guilt": "guilt", "big feelings": "bigfeelings", "dad": "dads",
             "bedtime": "bedtime", "sleep": "bedtime", "nap time": "bedtime", "daycare": "daycare", "meals": "meals",
             "mornings": "morning", "morning": "morning", "leaving the park": "park", "park": "park", "bath": "bath",
             "bath time": "bath", "siblings": "siblings", "sharing": "siblings", "patience": "patience",
             "tantrums": "bigfeelings", "car seat": "bigfeelings", "listening": "patience", "screens": "guilt"}
# words in a card's text that point at a better picture than the post's topic
KEYWORDS = [
    ("bath", "bath"), ("bubble", "bath"), ("towel", "bath"),
    ("dad", "dads"), ("father", "dads"), ("daddy", "dads"),
    ("park", "park"), ("slide", "park"), ("swing", "park"), ("outside", "park"),
    ("eat", "meals"), ("food", "meals"), ("snack", "meals"), ("dinner", "meals"), ("plate", "meals"), ("yucky", "meals"),
    ("shoes", "morning"), ("shirt", "morning"), ("wear", "morning"), ("morning", "morning"), ("dressed", "morning"),
    ("daycare", "daycare"), ("school", "daycare"), ("pick up", "daycare"), ("pickup", "daycare"),
    ("sibling", "siblings"), ("brother", "siblings"), ("sister", "siblings"), ("baby", "siblings"), ("share", "siblings"),
    ("bed", "bedtime"), ("sleep", "bedtime"), ("night", "bedtime"), ("story", "bedtime"), ("book", "bedtime"),
    ("lights out", "bedtime"), ("tuck", "bedtime"), ("tired", "tired"), ("rest", "tired"), ("break", "tired"),
    ("sorry", "repair"), ("yell", "repair"), ("repair", "repair"),
    ("tantrum", "bigfeelings"), ("meltdown", "bigfeelings"), ("mad", "bigfeelings"), ("scream", "bigfeelings"),
    ("hit", "bigfeelings"), ("stomp", "bigfeelings"), ("cry", "bigfeelings"), ("hate", "bigfeelings"),
    ("guilt", "guilt"), ("screen", "guilt"), ("show", "guilt"),
    ("breath", "patience"), ("calm", "patience"), ("eye level", "patience"),
    ("hug", "reassurance"), ("safe", "reassurance"), ("here", "reassurance"), ("love", "reassurance"),
    ("play", "connection"), ("floor", "connection"), ("tower", "connection"), ("together", "connection"),
    ("one day", "time"), ("grow", "time"), ("blink", "time"), ("remember", "time"), ("little", "time"),
]
WARM = ["reassurance", "connection", "time", "repair", "patience", "dads", "tired"]  # good with any message
TEXT_TOP, TEXT_BOTTOM = 210, 800   # the open paper area at the top of every scene


def _library():
    if not os.path.isdir(SCENE_DIR):
        return {}
    lib = {}
    for f in sorted(os.listdir(SCENE_DIR)):
        if f.endswith(".jpg"):
            lib.setdefault(f.split("_")[0], []).append(os.path.join(SCENE_DIR, f))
    return lib


def _tags_for(text):
    t = " " + text.lower() + " "
    out = []
    for word, tag in KEYWORDS:
        if word in t and tag not in out:
            out.append(tag)
    return out


def choose_scenes(p, hints, seed):
    """One different picture per card. Card text keywords first, then the post topic, then warm scenes.
    The seed rotates through each tag's pictures so back-to-back posts don't repeat the same art."""
    lib = _library()
    if not lib:
        return None
    rnd = random.Random(seed * 7919 + 17)
    order = {tag: rnd.sample(files, len(files)) for tag, files in lib.items()}
    topic_tag = TOPIC_TAG.get(p.get("topic", "").lower().strip(), p.get("topic", "").lower().replace(" ", ""))
    used, picks = set(), []
    for hint in hints:
        wanted = _tags_for(hint) + [topic_tag] + rnd.sample(WARM, len(WARM)) + sorted(lib)
        pick = None
        for tag in wanted:
            for f in order.get(tag, []):
                if f not in used:
                    pick = f
                    break
            if pick:
                break
        pick = pick or rnd.choice([f for fs in lib.values() for f in fs])
        used.add(pick)
        picks.append(pick)
    return picks


def overlay():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def brand_mark(d, color=NAVY):
    mx, my = W / 2 - bold(32).getlength(BRAND) / 2 - 34, 118
    d.rounded_rectangle([mx - 34, my - 34, mx + 52 + bold(32).getlength(BRAND), my + 30], radius=32,
                        fill=(251, 244, 230, 200))
    # speech-bubble mark
    d.rounded_rectangle([mx - 18, my - 16, mx + 18, my + 12], radius=9, fill=(220, 96, 78, 255))
    d.polygon([(mx - 8, my + 10), (mx - 14, my + 22), (mx + 2, my + 11)], fill=(220, 96, 78, 255))
    d.text((mx + 30, my - 22), BRAND, font=bold(32), fill=color)


def soft_panel(img, box, alpha=205):
    """Was a blurred cream wash behind text. Turned off (no shapes behind words); text carries its own halo."""
    return
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).rounded_rectangle(box, radius=60, fill=alpha)
    m = m.filter(ImageFilter.GaussianBlur(26))
    wash = Image.new("RGBA", (W, H), (251, 244, 230, 0))
    wash.putalpha(m)
    img.alpha_composite(wash)


def _box(img, text, maker, size, y, fill=(255, 255, 255), color=NAVY, max_h=380, lead=1.25, pad=46, lo=40):
    f, rows, lh = fit(text, maker, X1 - X0 - 120, max_h, size, lead=lead, lo=lo)
    bh = len(rows) * lh + pad * 2
    d = ImageDraw.Draw(img)  # no box behind the words: the halo keeps them readable
    draw_rows(d, rows, f, lh, X0 + 60, y + pad, color, center=True, width=X1 - X0 - 120)
    return y + bh


def _center_pill(img, text, y, fill):
    d = ImageDraw.Draw(img)
    return pill(d, text, 0, y, fill, center=True)


def _block(build):
    """Lay a card out once to measure it, then again vertically centred in the open top area."""
    probe = overlay()
    end = build(probe, 0)
    top = max(TEXT_TOP + 20, (TEXT_TOP + TEXT_BOTTOM) / 2 - end / 2)
    global _WORDS, _HIDE
    img = overlay()
    _WORDS = []
    try:
        build(img, top)
        words = _WORDS
    finally:
        _WORDS = None
    brand_mark(ImageDraw.Draw(img))
    base = overlay()
    _HIDE = True
    try:
        build(base, top)
    finally:
        _HIDE = False
    brand_mark(ImageDraw.Draw(base))
    img.words, img.base = words, base
    img.text_bottom = top + end
    return img


def push_scene(sc, o):
    """When a card's words run low, slide the picture down so the words never sit on a face.
    The space opened at the top is filled with the picture's own wall colour."""
    tb = getattr(o, "text_bottom", 0)
    s = int(max(0, min(340, tb + 40 - H * 0.40)))
    if not s:
        return sc
    wall = sc.crop((0, 0, W, 12)).resize((1, 1), Image.BOX).getpixel((0, 0))
    out = Image.new("RGB", sc.size, wall)
    out.paste(sc, (0, s))
    m = Image.new("L", (W, 120), 0)  # soften the seam
    for y in range(120):
        m.paste(int(255 * (1 - y / 119)), (0, y, W, y + 1))
    out.paste(Image.new("RGB", (W, 120), wall), (0, s), m)
    return out


def il_text(text, size=78):
    """Big serif line on a soft wash (feel lines, 'what it means')."""
    def build(img, top):
        f, rows, lh = fit(text, serif, X1 - X0 - 80, 430, size, lead=1.32)
        th = len(rows) * lh
        if img is not None and top:
            soft_panel(img, [X0 - 20, top - 46, X1 + 20, top + th + 76])
        d = ImageDraw.Draw(img)
        draw_rows(d, rows, f, lh, X0 + 40, top, NAVY, center=True, width=X1 - X0 - 80)
        d.line([W / 2 - 50, top + th + 30, W / 2 + 50, top + th + 30], fill=GOLD, width=6)
        return th + 36
    return _block(build)


def serif_b(s): return font("Lora-Variable.ttf", s, 700)


def il_cold(hook_text, sub=None, voiced_sub=False):
    """First card, the cold open (first 3 seconds): no box, no logo. A dark cinematic shade over a close-up of
    the faces, then big white words that appear phrase by phrase as the voice says them.
    Returns the full overlay (for covers and stills) with .words (word boxes) and .base (shade only) for the video."""
    shade = overlay()
    g = Image.new("L", (1, H))
    for y in range(H):
        t = y / H
        a = 225 * max(0.0, 1 - t / 0.58) ** 1.1 + 70 * max(0.0, (t - 0.80) / 0.20)  # dark top for words, soft bottom
        g.putpixel((0, y), int(min(255, a)))
    shade.putalpha(g.resize((W, H)))
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse([-260, -200, W + 260, H + 300], fill=255)
    vig = Image.eval(vig.filter(ImageFilter.GaussianBlur(160)), lambda v: int((255 - v) * 0.55))
    dark = Image.new("RGBA", (W, H), (12, 10, 18, 0)); dark.putalpha(vig)
    shade.alpha_composite(dark)

    phrases = [x.strip() for x in re.split(r"(?<=[.?!])\s+", hook_text) if x.strip()]
    f, rows, lh = fit(hook_text, serif_b, X1 - X0 - 10, 470, 112, lead=1.16, lo=66)
    # wrap phrase by phrase so each phrase starts on its own line and can appear on its own
    lines = []
    for k, ph in enumerate(phrases):
        for r in wrap(ph, f, X1 - X0 - 10):
            lines.append((k, r))
    th = len(lines) * lh
    sub_h = 0
    if sub:
        fs, srows, slh = fit(sub, serif_i, X1 - X0 - 40, 200, 60, lead=1.22, lo=42)
        sub_h = len(srows) * slh + 40
    top = int(max(200, 500 - (th + sub_h) / 2))
    words = []
    txt, sh = overlay(), overlay()
    d, ds = ImageDraw.Draw(txt), ImageDraw.Draw(sh)
    sp = f.getlength(" ")
    for j, (_, r) in enumerate(lines):
        x, y = W / 2 - f.getlength(r) / 2, top + j * lh
        ds.text((x + 3, y + 5), r, font=f, fill=(0, 0, 0, 190))
        d.text((x, y), r, font=f, fill=(255, 252, 245))
        for wd in r.split():
            wl = f.getlength(wd)
            words.append((wd, (int(x - 9), int(y - 14), int(x + wl + 13), int(y + lh + 4))))
            x += wl + sp
    if sub:
        y = top + th + 40
        for j, r in enumerate(srows):
            x = W / 2 - fs.getlength(r) / 2
            d.text((x, y + j * slh), r, font=fs, fill=(250, 214, 140))
            for wd in r.split():
                wl = fs.getlength(wd)
                words.append((wd, (int(x - 10), int(y + j * slh - 8), int(x + wl + 12), int(y + (j + 1) * slh))))
                x += wl + fs.getlength(" ")
    sh = sh.filter(ImageFilter.GaussianBlur(9))
    sh.alpha_composite(txt)
    full = shade.copy()
    full.alpha_composite(sh)
    full.words, full.base, full.is_cold = words, shade, True
    full.voiced_sub = voiced_sub
    return full


def il_titled(label, color, text, maker=bold, size=84, fill=(255, 255, 255), sub=None, opener=None):
    """Pill label + white box (hooks, 'say this instead', swap pairs).
    opener: an emotional line shown first, in serif italics, above everything (blueprint: emotion first)."""
    def build(img, top):
        y = top
        if opener:
            f, rows, lh = fit(opener, serif_i, X1 - X0 - 60, 150, 62, lead=1.25, lo=44)
            th = len(rows) * lh
            if top:
                soft_panel(img, [X0 - 20, y - 30, X1 + 20, y + th + 30], alpha=225)
            draw_rows(ImageDraw.Draw(img), rows, f, lh, X0 + 30, y, NAVY, center=True, width=X1 - X0 - 60)
            y += th + 34
        if label:
            y = _center_pill(img, label, y, color) + 26
        y = _box(img, text, maker, size, y, fill=fill)
        if sub:
            y += 24
            if not _HIDE:
                halo_text(img, (W / 2, y + 37), sub, serif_i(46), GREEN, anchor="mm")
            y += 74
        return y - top
    return _block(build)


def il_pair(a, b, i, n):
    def build(img, top):
        y = _center_pill(img, f"{i + 1} OF {n}", top, NAVY) + 24
        for label, text, col, good in (("INSTEAD OF", a, RED, False), ("TRY", b, GREEN, True)):
            d = ImageDraw.Draw(img)
            y = pill(d, label, X0, y, col, size=30) + 14
            y = _box(img, f"“{text}”", serif_i if good else serif, 58, y, max_h=170, lead=1.28, pad=30,
                     fill=None, color=NAVY if good else (168, 84, 76)) + 30
        return y - top
    return _block(build)


def il_outro(p, ask, label, foot):
    def build(img, top):
        y = _box(img, ask, bold, 64, top + 46, fill=(255, 244, 214), max_h=260, pad=40)
        d = ImageDraw.Draw(img)
        if label:
            halo_text(img, (W / 2, top + 22), label, bold(28), (176, 128, 30), anchor="mm")
        y += 36
        halo_text(img, (W / 2, y + 32), foot, bold(36) if p.get("footer") else medium(36),
                  GREEN if p.get("footer") else SOFT, anchor="mm")
        return y + 64 - top
    return _block(build)


def plan_illustrated(p, full=False):
    """The video's cards. Videos are kept to about 15 to 18 seconds (completion is the strongest signal after
    the first 2 seconds): translator keeps hook, what it means, the first 'say this' line and the comment card;
    feel keeps the hook, the first 3 lines and the end card. full=True keeps every card (carousels).
    Sets p['_src'] (which full-plan cards were kept) so each kept card keeps its own picture and clip."""
    cards = _plan_full(p)
    n = len(cards)
    if full or p["format"] == "swap":
        keep = list(range(n))
    elif p["format"] == "translator":
        keep = [0, 1, 2, n - 1] if n >= 5 else list(range(n))
    else:
        keep = list(range(min(4, n - 1))) + [n - 1]
    p["_src"], p["_nfull"] = keep, n
    return [cards[k] for k in keep]


def _plan_full(p):
    """[(overlay, voice text, picture hint)] with one card (and one picture) per piece of copy."""
    fv = (" " + p["footer_voice"]) if p.get("footer_voice") else ""
    if p["format"] == "feel":
        hk = cold_hook(p)
        cards = ([(il_cold(hk), hk, p["title"])] if hk else
                 [(il_titled(None, None, p["title"], size=88), p["title"].rstrip(".…") + ".", p["title"])])
        cards += [(il_text(line), line, line) for line in p["lines"]]
        end = p.get("end") or "Send this to someone who needs it today."
        q = p.get("cta") or "Which line did you need today?"
        cards.append((il_outro(p, q, "TELL ME IN THE COMMENTS", p.get("footer") or "Follow for the words you need at work"),
                      f"{end} And tell me in the comments: {q}" + fv, end))
        return cards
    if p["format"] == "translator":
        action = p["says"].startswith("*")
        quote = p["says"].strip("* ") if action else f"“{p['says']}”"
        who = p.get("who") or "they"
        lead = f"WHEN {who.upper()}..." if action else f"WHEN {who.upper()} SAYS..."
        op = feel_hook(p)
        hk = cold_hook(p)
        if hk:
            means = " ".join(p["means"])
            said = (f"When {who} {p['says'].strip('* ')}." if action else f"When {who} says: {p['says']}")
            cards = [(il_cold(hk, quote), hk, p["says"]),
                     (il_titled("WHAT THEY REALLY MEAN", PURPLE, means, maker=serif, size=70),
                      said + " What they really mean: " + means, means)]
            for k, ln in enumerate(p["say"]):
                cards.append((il_titled("SAY THIS INSTEAD", GREEN, f"“{ln}”", maker=serif_i, size=72),
                              ("Say this instead. " if k == 0 else "") + ln, ln))
            cards.append((il_outro(p, p["cta"], "TELL ME IN THE COMMENTS", p.get("footer") or "Follow for a new script every day"),
                          f"Tell me in the comments: {p['cta']}" + fv, p["cta"]))
            return cards
        cards = [(il_titled(lead, NAVY, quote, size=84 if op else 92, opener=op),
                  (op.rstrip(".…") + ". " if op else "") + (f"When {who} {p['says'].strip('* ')}." if action
                  else f"When {who} says: {p['says']}"), p["says"])]
        means = " ".join(p["means"])
        cards.append((il_titled("WHAT THEY REALLY MEAN", PURPLE, means, maker=serif, size=70), "What they really mean: " + means, means))
        for k, ln in enumerate(p["say"]):
            cards.append((il_titled("SAY THIS INSTEAD", GREEN, f"“{ln}”", maker=serif_i, size=72),
                          ("Say this instead. " if k == 0 else "") + ln, ln))
        cards.append((il_outro(p, p["cta"], "TELL ME IN THE COMMENTS", p.get("footer") or "Follow for a new script every day"),
                      f"Tell me in the comments: {p['cta']}" + fv, p["cta"]))
        return cards
    op = feel_hook(p)
    hk = cold_hook(p)
    if hk:
        cards = [(il_cold(hk, p["title"], voiced_sub=True), f"{hk} {p['title']}.", p["title"])]
    else:
        cards = [(il_titled(None if op else p["topic"].upper(), NAVY, p["title"], size=78 if op else 84,
                            sub="and what to say instead", opener=op),
                  (op.rstrip(".…") + ". " if op else "") + f"{p['title']}. And what to say instead.", p["title"])]
    for i, (a, b) in enumerate(p["pairs"]):
        cards.append((il_pair(a, b, i, len(p["pairs"])), f"Instead of: {a} Try: {b}", a + " " + b))
    cards.append((il_outro(p, p["cta"], "TELL ME IN THE COMMENTS", p.get("footer") or "Follow for a new script every day"),
                  f"Save this for later. And tell me in the comments: {p['cta']}" + fv, p["cta"]))
    return cards


def post_slug(p):
    """Folder name for a post's own pictures: engine/scenes/posts/<slug>/01.jpg ..."""
    key = p.get("says") or p.get("title", "")
    return re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")[:60]


def illustrated(p):
    """Every Toddler Translator post is illustrated unless a post sets "style": "cards"."""
    return p.get("style", "illustrated") == "illustrated" and (bool(p.get("scene_files")) or bool(_library()))


# ---------- feel (emotional, share-first) ----------
FEEL_MOODS = ["calm", "sad", "calm", "happy", "calm", "happy"]


def fe_hook(p, look, seed):
    img = background(seed); d = ImageDraw.Draw(img)
    f, rows, lh = fit(p["title"], bold, X1 - X0 - 120, 420, 92)
    bh = len(rows) * lh + 100
    by = 250
    card(img, [X0, by, X1, by + bh], radius=48)
    d = ImageDraw.Draw(img)
    draw_rows(d, rows, f, lh, X0 + 60, by + 50, NAVY, center=True, width=X1 - X0 - 120)
    toddler_in(img, "calm", look, by + bh + 90, 620)
    return img


def fe_line(p, i, look, seed):
    img = background(seed); d = ImageDraw.Draw(img)
    text = p["lines"][i]
    f, rows, lh = fit(text, serif, X1 - X0 - 80, 460, 82, lead=1.32)
    y = 300
    draw_rows(d, rows, f, lh, X0 + 40, y, NAVY, center=True, width=X1 - X0 - 80)
    y += len(rows) * lh
    d.line([W / 2 - 50, y + 40, W / 2 + 50, y + 40], fill=GOLD, width=6)
    toddler_in(img, FEEL_MOODS[i % len(FEEL_MOODS)], look, y + 100, 560)
    return img


def fe_end(p, look, seed):
    img = background(seed); d = ImageDraw.Draw(img)
    ask = p.get("end") or "Send this to someone who needs it today."
    f, rows, lh = fit(ask, bold, X1 - X0 - 120, 300, 70)
    bh = len(rows) * lh + 110
    card(img, [X0, 300, X1, 300 + bh], fill=(255, 244, 214), radius=44)
    d = ImageDraw.Draw(img)
    draw_rows(d, rows, f, lh, X0 + 60, 355, NAVY, center=True, width=X1 - X0 - 120)
    end = toddler_in(img, "happy", look, 300 + bh + 70, 600, bottom=SAFE_BOTTOM - 70)
    d = ImageDraw.Draw(img)
    foot = p.get("footer") or "Follow for the words you need at work"
    d.text((W / 2, end + 40), foot, font=bold(36) if p.get("footer") else medium(36),
           fill=GREEN if p.get("footer") else SOFT, anchor="mm")
    return img


def plan(p, look, seed):
    """[(image, voice text)] for a post."""
    if p["format"] == "feel":
        cards = [(fe_hook(p, look, seed), p["title"].rstrip(".…") + ".")]
        for i, line in enumerate(p["lines"]):
            cards.append((fe_line(p, i, look, seed + 1 + i), line))
        end = p.get("end") or "Send this to someone who needs it today."
        cards.append((fe_end(p, look, seed + 9), end + (" " + p["footer_voice"] if p.get("footer_voice") else "")))
        return cards
    if p["format"] == "translator":
        return [
            (tr_hook(p, look, seed), f"When your toddler {p['says'].strip('* ')}." if p["says"].startswith("*")
             else f"When your toddler says: {p['says']}"),
            (tr_means(p, look, seed + 1), "What they really mean: " + " ".join(p["means"])),
            (tr_say(p, look, seed + 2), "Say this instead. " + " ".join(p["say"])),
            (outro(p, look, seed + 3), f"Save this for tonight. And tell me in the comments: {p['cta']}" + (" " + p["footer_voice"] if p.get("footer_voice") else "")),
        ]
    cards = [(sw_hook(p, look, seed), f"{p['title']}. And what to say instead.")]
    for i, (a, b) in enumerate(p["pairs"]):
        cards.append((sw_pair(p, i, look, seed + 1 + i), f"Instead of: {a} Try: {b}"))
    cards.append((outro(p, look, seed + 9), f"Save this for later. And tell me in the comments: {p['cta']}" + (" " + p["footer_voice"] if p.get("footer_voice") else "")))
    return cards


def dur_of(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    return float(out)


def _ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def _pose(mood, t, k):
    """Offset (dx, dy), scale and tilt for the toddler at time t (seconds into its card)."""
    pop = 0.82 + 0.18 * _ease(t / 0.35) + (0.04 * math.sin(min(t / 0.35, 1) * math.pi))  # pop in with a tiny overshoot
    breathe = 1 + 0.012 * math.sin(t * 2 * math.pi / 2.4)
    dx = dy = ang = 0.0
    if mood == "mad":        # stomp: short shakes every second, plus a little hop
        ph = t % 1.1
        dx = 9 * math.sin(ph * 38) * max(0, 1 - ph / 0.45)
        dy = -7 * abs(math.sin(t * math.pi / 1.1))
    elif mood == "happy":    # bouncy
        dy = -26 * abs(math.sin(t * math.pi / 0.55))
        ang = 2.5 * math.sin(t * 2 * math.pi / 1.1)
    elif mood == "sad":      # slow sway
        ang = 3.5 * math.sin(t * 2 * math.pi / 2.6)
        dy = 4 * math.sin(t * 2 * math.pi / 2.6)
    else:                    # calm: gentle float
        dy = -8 * math.sin(t * 2 * math.pi / 2.2)
    return dx, dy, pop * breathe, ang


EMO_DIR = os.path.join(HERE, "music", "emotional")
# each mood has its own tracks: piano from the first second, a swell around 15 to 20 seconds
MOODS = {
    "nostalgia": ["one day", "remember", "last", "fast", "years", "quiet", "age", "grow", "blink", "story", "book",
                  "time", "favorite", "no one tells"],
    "comfort": ["yell", "guilt", "hard", "midnight", "tantrum", "cry", "hit", "hate", "snap", "scared", "fall apart",
                "daycare", "drop off", "don't go", "break", "tired", "two under", "mad", "baby", "repair", "big feelings",
                "floor", "mom guilt", "tired parent", "siblings", "yourself"],
    "uplift": ["dad", "great job", "doing", "proud", "reassurance", "love you", "connection", "need to hear",
               "ten minutes", "phrase"],
    "lullaby": ["bed", "sleep", "dark", "night", "lie with me", "tonight", "brain is busy"],
    "playful": ["wear", "shoes", "socks", "eat", "dinner", "yucky", "brush", "bath", "car seat", "potty", "park",
                "show", "buy", "mine", "myself", "playing", "leaving", "listen", "school", "stop it", "big deal"],
}


def mood_of(p):
    """Pick the feeling the music should carry, from the hook and the post's own words (first match by priority)."""
    from hooks import music_mood
    if music_mood(p):
        return music_mood(p)
    text = " ".join(str(p.get(k, "")) for k in ("hook", "title", "says", "topic")).lower()
    try:
        text += " " + (cold_hook(p) or "").lower()
    except Exception:
        pass
    for mood in ("comfort", "nostalgia", "lullaby", "uplift", "playful"):
        if any(w in text for w in MOODS[mood]):
            return mood
    return "comfort" if p.get("format") == "feel" else "playful"


def emotional_track(p, seed):
    """An emotional track for this post's mood, or None if the emotional library is missing."""
    if not os.path.isdir(EMO_DIR):
        return None
    if p.get("music") and os.path.exists(os.path.join(EMO_DIR, p["music"])):
        return os.path.join(EMO_DIR, p["music"])  # assigned in the queue so neighbouring posts never share a track
    mood = mood_of(p)
    pool = sorted(f for f in os.listdir(EMO_DIR) if f.startswith(mood) and f.endswith(".m4a"))
    pool = pool or sorted(f for f in os.listdir(EMO_DIR) if f.endswith(".m4a"))
    import zlib  # spread posts across the mood's tracks by the post's own words, so neighbours rarely repeat
    k = zlib.crc32((p.get("says") or p.get("title") or "").encode()) + seed
    return os.path.join(EMO_DIR, pool[k % len(pool)]) if pool else None


NO_MUSIC = False  # True for the TikTok draft version: voice only, so a trending sound can be added in the app


def make_carousel(p, outdir, seed=1):
    """Swipeable slides for a carousel post: every card of the full plan (no trimming) over its own picture.
    Writes outdir/slide_NN.jpg (1080x1920, TikTok photo mode) and outdir/slide_NN_34.jpg (1080x1440, Instagram and
    Facebook, cropped from the top so the words stay in). Returns (tall, crops)."""
    os.makedirs(outdir, exist_ok=True)
    cards = plan_illustrated(p, full=True)
    own = [os.path.join(SCENE_DIR, f) for f in p.get("scene_files", [])]
    picks = own if own and len(own) == len(cards) and all(os.path.exists(f) for f in own) else \
        choose_scenes(p, [h for _, _, h in cards], seed)
    tall, crops = [], []
    for i, ((o, _, _), pic) in enumerate(zip(cards, picks)):
        sc = Image.open(pic).convert("RGB").resize((W, int(W * 1930 / 1080)))
        if not getattr(o, "is_cold", False):
            sc = push_scene(sc, o)
        base = sc.crop((0, 0, W, H))
        if getattr(o, "is_cold", False):  # same close-up on the faces as the video's first frame
            z = 1.42; cw, ch = W / z, H / z
            x0 = (W - cw) / 2; y0 = max(0, min(H - ch, H * 0.47 - ch / 2))
            base = base.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
        img = base.convert("RGBA"); img.alpha_composite(o); img = img.convert("RGB")
        a = os.path.join(outdir, f"slide_{i + 1:02d}.jpg"); img.save(a, quality=90); tall.append(a)
        b = os.path.join(outdir, f"slide_{i + 1:02d}_34.jpg"); img.crop((0, 60, W, 60 + 1440)).save(b, quality=90)
        crops.append(b)
    return tall, crops


def render(p, out, music, seed=1, no_music=False):
    global SPRITES, NO_MUSIC
    NO_MUSIC = no_music
    tmp = tempfile.mkdtemp()
    emo = emotional_track(p, seed)
    if emo:
        music = emo  # every post gets music that carries its feeling
    p["music_used"] = os.path.basename(music)
    look = pick_look(seed)
    scenes = None
    if illustrated(p):
        cards3 = plan_illustrated(p)
        own = [os.path.join(SCENE_DIR, f) for f in p.get("scene_files", [])]
        if own and len(own) == p.get("_nfull") and len(p.get("_src", [])) == len(cards3):
            own = [own[k] for k in p["_src"]]
        if own and len(own) == len(cards3) and all(os.path.exists(f) for f in own):
            picks = own  # pictures drawn for this exact post, one per line
        else:
            picks = choose_scenes(p, [h for _, _, h in cards3], seed)
        scenes = [push_scene(Image.open(f).convert("RGB").resize((W, int(W * 1930 / 1080))), o)
                  for f, (o, _, _) in zip(picks, cards3)]
        p["scenes_used"] = [os.path.basename(f) for f in picks]
        overlays = [o for o, _, _ in cards3]
        # flattened stills (cover image, previews)
        cards = [(Image.alpha_composite(sc.crop((0, 0, W, H)).convert("RGBA"), o).convert("RGB"), v)
                 for sc, (o, v, _) in zip(scenes, cards3)]
        sprites = None
    else:
        SPRITES = []
        try:
            cards = plan(p, look, seed)
            sprites = SPRITES
        finally:
            SPRITES = None
        assert len(sprites) == len(cards), "one toddler per card"
    imgs, auds, durs = [], [], []
    for i, (im, text) in enumerate(cards):
        ip = os.path.join(tmp, f"c{i}.png"); im.save(ip); imgs.append(ip)
        ap = speak(text, os.path.join(tmp, f"v{i}.mp3"), hook=(i == 0 and scenes is not None and getattr(overlays[0], "is_cold", False)))
        d = dur_of(ap) + 0.55 if ap else max(2.6, len(text.split()) * 0.36)
        auds.append(ap); durs.append(round(d, 2))
    durs[0] = max(durs[0], 2.2)
    total = sum(durs)

    starts_t = [sum(durs[:i]) for i in range(len(cards))]

    cold = scenes is not None and getattr(overlays[0], "is_cold", False)
    spoken0 = max(0.6, durs[0] - 0.55)

    # when each on-screen word appears: matched to the moment the voice says it (ElevenLabs word timing),
    # otherwise spread evenly over the spoken line
    def _norm(w):
        return re.sub(r"[^a-z0-9']", "", w.lower().replace("’", "'"))

    def reveal_times(i):
        o = overlays[i] if scenes is not None else None
        words = getattr(o, "words", None) if o is not None else None
        if not words:
            return None
        delay = 0.04 if i == 0 else 0.15
        spoken_len = max(0.5, durs[i] - 0.55)
        timed = []
        ap = auds[i]
        if ap and os.path.exists(ap + ".words.json"):
            try:
                timed = [(_norm(w), float(t)) for w, t in json.load(open(ap + ".words.json")) if t is not None]
            except Exception:
                timed = []
        n = len(words)

        def walk(start):
            times, j, last, hits = [], start, 0.0, 0
            for k, (wd, _) in enumerate(words):
                w = _norm(wd)
                hit = next((m for m in range(j, min(len(timed), j + 8)) if timed[m][0] == w), None) if timed else None
                if hit is not None:
                    t = timed[hit][1]; j = hit + 1; hits += 1
                elif timed:
                    t = last + 0.12
                else:
                    t = spoken_len * k / max(1, n)
                t = max(t, last)
                times.append(t); last = t
            return hits, times

        if timed:  # the card's words are usually the end of the spoken line ("What it really means: ...")
            best = max(((walk(st), st) for st in range(len(timed))), key=lambda x: (x[0][0], x[1]))
            times = best[0][1]
        else:
            times = walk(0)[1]
        return [delay + t for t in times]

    reveal = {}
    states = {}

    def over(i, t):
        """Overlay for card i at time t: the card is there at once, its words pop in as they are spoken."""
        o = overlays[i]
        if scenes is None or not getattr(o, "words", None):
            return o
        if getattr(o, "is_cold", False):
            return o  # the hook is fully on screen from frame one: people decide in the first 2 seconds
        if i not in reveal:
            reveal[i] = reveal_times(i)
        k = sum(1 for rt in reveal[i] if t >= rt)
        if k >= len(o.words):
            return o
        key = (i, k)
        if key not in states:
            if len(states) > 40:
                states.clear()
            st = o.base.copy()
            for _, box in o.words[:k]:
                box = (max(0, box[0]), max(0, box[1]), min(W, box[2]), min(H, box[3]))
                st.paste(o.crop(box), box[:2])
            states[key] = st
        return states[key]

    def faces(img, i, t):
        """Cold open: start close on the faces and ease back a little, so the feeling lands first."""
        if not (i == 0 and cold):
            return img
        g = min(1.0, t / max(durs[0], 0.1)); g = g * g * (3 - 2 * g)
        z = 1.42 - 0.20 * g
        cw, ch = img.width / z, img.height / z
        cx, cy = img.width / 2, img.height * 0.47
        x0 = max(0, min(img.width - cw, cx - cw / 2)); y0 = max(0, min(img.height - ch, cy - ch / 2))
        return img.resize(img.size, Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))

    if cold:  # the cover (first frame people see in the grid) gets the close-up and the full hook too
        c0 = faces(scenes[0].crop((0, 0, W, H)), 0, 0).convert("RGBA")
        c0.alpha_composite(overlays[0])
        c0.convert("RGB").save(imgs[0])

    clips = [os.path.join(SCENE_DIR, c) if c else None for c in p.get("scene_clips", [])] if scenes is not None else []
    if clips and len(clips) == p.get("_nfull") and len(p.get("_src", [])) == len(scenes):
        clips = [clips[k] for k in p["_src"]]
    if scenes is not None and len(clips) == len(scenes) and all(c and os.path.exists(c) for c in clips):
        # movie mode: each card plays its own animated clip (made from that card's picture)
        cache = {}

        def clip_frames(i):
            if i not in cache:
                for k in list(cache):
                    if k < i - 1:
                        del cache[k]
                raw = subprocess.run(["ffmpeg", "-v", "error", "-i", clips[i], "-vf",
                                      "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280",
                                      "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
                n = len(raw) // (720 * 1280 * 3)
                cache[i] = [raw[k * 720 * 1280 * 3:(k + 1) * 720 * 1280 * 3] for k in range(n)]
            return cache[i]

        def frame(i, t):
            fr = clip_frames(i)
            n, d = len(fr), max(durs[i], 0.1)
            clip_len = n / 24.0
            if d <= clip_len * 1.35:        # stretch gently to fill the card
                k = int(min(n - 1, (t / d) * n))
            else:                            # longer card: play forward, then drift back slowly
                cyc = (t / clip_len) % 2
                k = int((cyc if cyc < 1 else 2 - cyc) * (n - 1))
            img = faces(Image.frombytes("RGB", (720, 1280), fr[k]), i, t).resize((W, H), Image.BILINEAR).convert("RGBA")
            img.alpha_composite(over(i, t))
            return img.convert("RGB")
        return _encode(frame, durs, total, auds, cards, music, seed, out, imgs)

    if scenes is not None:
        def frame(i, t):
            sc = scenes[i]
            g = min(1.0, t / max(durs[i], 0.1))
            z = 1.0 + 0.06 * (g * g * (3 - 2 * g))      # gentle push-in on each picture
            cw, ch = W / z, H / z
            x0 = (W - cw) / 2 + (18 if i % 2 else -18) * g  # tiny drift, alternating sides
            x0 = max(0, min(W - cw, x0))
            y0 = (sc.height - ch) * 0.7
            if i == 0 and cold:
                f = faces(sc.crop((0, 0, W, H)), i, t).convert("RGBA")
            else:
                f = sc.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch)).convert("RGBA")
            f.alpha_composite(over(i, t))
            return f.convert("RGB")
        return _encode(frame, durs, total, auds, cards, music, seed, out, imgs)

    # pre-draw each card's toddler (open eyes and a blink frame) once
    art = []
    for s in sprites:
        o = draw_toddler(s["mood"], s["look"], s["size"])
        b = draw_toddler(s["mood"], s["look"], s["size"], blink=True)
        art.append((o, b))
    bgs = [im.convert("RGB") for im, _ in cards]
    rnd = random.Random(seed)
    blinks = [sorted(rnd.uniform(0.8, max(1.0, d - 0.3)) for _ in range(max(1, int(d / 2.6)))) for d in durs]

    def frame(i, t):
        f = bgs[i].copy()
        s, (o, b) = sprites[i], art[i]
        spr = b if any(0 <= t - bt < 0.12 for bt in blinks[i]) else o
        dx, dy, sc, ang = _pose(s["mood"], t, i)
        if abs(sc - 1) > 0.002:
            spr = spr.resize((max(1, int(spr.width * sc)), max(1, int(spr.height * sc))), Image.BILINEAR)
        if abs(ang) > 0.05:
            spr = spr.rotate(ang, resample=Image.BICUBIC, expand=True)
        # anchor at the feet so the toddler grows and sways from the ground
        x = int(W / 2 - spr.width / 2 + dx)
        y = int(s["top"] + o.height - spr.height + dy)
        f.paste(spr, (x, y), spr)
        return f

    return _encode(frame, durs, total, auds, cards, music, seed, out, imgs)


def _encode(frame, durs, total, auds, cards, music, seed, out, imgs):
    fade = int(0.25 * FPS)
    vid_cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
               "-r", str(FPS), "-i", "-"]
    n_in = 1
    inputs, fc = [], ""
    # emotional tracks start on their melody at second zero and swell mid-video, so play them from the top
    start = 0.0 if os.path.dirname(music) == EMO_DIR else random.Random(seed).uniform(2, 40)
    inputs += ["-ss", f"{start:.2f}", "-stream_loop", "-1", "-i", music]
    mv = 0.34 if os.path.dirname(music) == EMO_DIR else 0.24  # emotional music sits forward, under the voice
    if NO_MUSIC:
        mv = 0.0
    fc += f"[{n_in}:a]atrim=0:{total:.2f},asetpts=N/SR/TB,volume={mv},afade=t=in:d=0.05,afade=t=out:st={total - 1.2:.2f}:d=1.2[mus]"
    voiced = [(i, a) for i, a in enumerate(auds) if a]
    starts = [sum(durs[:i]) for i in range(len(cards))]
    mixes = []
    for k, (i, a) in enumerate(voiced):
        inputs += ["-i", a]
        ms = int((starts[i] + (0.04 if i == 0 else 0.15)) * 1000)
        fc += f";[{n_in + 1 + k}:a]adelay={ms}|{ms},volume=1.0[a{k}]"
        mixes.append(f"[a{k}]")
    fc += (f";[mus]{''.join(mixes)}amix=inputs={len(mixes) + 1}:normalize=0,atrim=0:{total:.2f}[aout]"
           if mixes else ";[mus]anull[aout]")
    cmd = vid_cmd + inputs + ["-filter_complex", fc, "-map", "0:v", "-map", "[aout]",
                              "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                              "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}", "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i, d in enumerate(durs):
        nf = int(round(d * FPS))
        for fi in range(nf):
            f = frame(i, fi / FPS)
            if i + 1 < len(durs) and fi >= nf - fade:  # crossfade into the next card
                a = (fi - (nf - fade) + 1) / (fade + 1)
                f = Image.blend(f, frame(i + 1, 0), a)
            proc.stdin.write(f.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    return out, imgs, total

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("post"); ap.add_argument("out")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--music", default=os.path.join(HERE, "music", "soft-sunrise.m4a"))
    a = ap.parse_args()
    o, imgs, t = render(json.load(open(a.post)), a.out, a.music, a.seed)
    print("wrote", o, f"{t:.1f}s", imgs[0].rsplit('/', 1)[0])
