"""Builds the free Say This Instead Starter Playbook PDF and a cover PNG for the Kit page."""
import os, sys
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scripts import SECTIONS  # noqa

FD = os.path.join(HERE, "..", "engine", "fonts")
pdfmetrics.registerFont(TTFont("PopB", os.path.join(FD, "Poppins-Bold.ttf")))
pdfmetrics.registerFont(TTFont("Pop", os.path.join(FD, "Poppins-Medium.ttf")))
pdfmetrics.registerFont(TTFont("Lora", os.path.join(FD, "Lora-Variable.ttf")))
pdfmetrics.registerFont(TTFont("LoraI", os.path.join(FD, "Lora-Italic-Variable.ttf")))

W, H = letter
CREAM, NAVY, SOFT = HexColor("#FBF6EC"), HexColor("#2B2F45"), HexColor("#6B6F86")
MUSTARD, CORAL, WHITE = HexColor("#BE861C"), HexColor("#DC604E"), HexColor("#FFFFFF")
M = 54
TITLE = "The Starter Playbook"


def bg(c, col=CREAM):
    c.setFillColor(col); c.rect(0, 0, W, H, stroke=0, fill=1)


def para(c, text, x, y_top, w, size=11, font="Lora", color=NAVY, lead=1.42, draw=True):
    st = ParagraphStyle("p", fontName=font, fontSize=size, leading=size * lead, textColor=color)
    p = Paragraph(text, st)
    _, h = p.wrap(w, 1000)
    if draw:
        p.drawOn(c, x, y_top - h)
    return h


def footer(c, n):
    c.setFillColor(SOFT); c.setFont("Pop", 8)
    c.drawCentredString(W / 2, 26, f"Say This Instead  ·  {TITLE}  ·  {n}")


def cover(c):
    bg(c, NAVY)
    c.setFillColor(MUSTARD); c.roundRect(M, H - 150, 150, 26, 13, stroke=0, fill=1)
    c.setFillColor(NAVY); c.setFont("PopB", 10); c.drawCentredString(M + 75, H - 141, "FREE PLAYBOOK")
    c.setFillColor(CREAM); c.setFont("PopB", 50)
    for i, line in enumerate(["Say This", "Instead"]):
        c.drawString(M, H - 240 - i * 58, line)
    c.setFillColor(MUSTARD); c.setFont("LoraI", 24)
    c.drawString(M, H - 350, "25 word-for-word scripts")
    para(c, "for raises, salary, bosses, boundaries, clients, pricing and sales. "
            "Built for the office and for remote work.", M, H - 372, 360, 14, "Lora", CREAM)
    # two cards: don't say / say this instead
    y = 250
    for label, col, txt in [("DON'T SAY", CORAL, "\"I was wondering if maybe there's room for a raise?\""),
                            ("SAY THIS INSTEAD", MUSTARD, "\"Based on my results this year, I'm asking for $X. What would it take to get there?\"")]:
        c.setFillColor(WHITE); c.roundRect(M, y - 84, W - 2 * M, 96, 16, stroke=0, fill=1)
        c.setFillColor(col); c.setFont("PopB", 10); c.drawString(M + 22, y - 10, label)
        para(c, txt, M + 22, y - 18, W - 2 * M - 44, 13.5, "Lora", NAVY)
        y -= 116
    c.setFillColor(SOFT); c.setFont("Pop", 9)
    c.drawString(M, 30, "@saythis.instead")


def intro(c):
    bg(c)
    c.setFillColor(NAVY); c.setFont("PopB", 28); c.drawString(M, H - 100, "How to use this")
    y = H - 130
    for t in [
        "Most hard conversations go wrong in the first sentence. You apologize, you hedge, "
        "you ask permission. This playbook gives you the first sentence, so the rest gets easier.",
        "<b>Every script has three parts.</b> What people usually say, what to say instead, and why it works. "
        "Read the why. Once you get the idea, you can make any script your own.",
        "<b>Swap in your real details.</b> Your numbers, your dates, your results. Specific always beats polite.",
        "<b>Say it out loud once before you use it.</b> Words feel different in your mouth than on a page. "
        "Thirty seconds of practice is the difference between reading a script and sounding sure.",
        "<b>Pause after you ask.</b> The hardest part of every script is the silence after the question. Let them answer.",
    ]:
        y -= para(c, t, M, y, W - 2 * M, 12.5) + 16
    c.setFillColor(WHITE); c.roundRect(M, 90, W - 2 * M, 120, 16, stroke=0, fill=1)
    c.setFillColor(MUSTARD); c.setFont("PopB", 10); c.drawString(M + 22, 186, "INSIDE")
    yy = 166
    for i, (name, col, items) in enumerate(SECTIONS):
        c.setFillColor(HexColor(col)); c.circle(M + 28, yy + 3, 4, stroke=0, fill=1)
        c.setFillColor(NAVY); c.setFont("Pop", 11); c.drawString(M + 40, yy, f"{name}  ({len(items)} scripts)")
        yy -= 16
    footer(c, 2)


def script_block(c, n, s, col, y, draw=True):
    x, w = M, W - 2 * M
    inner = w - 44
    h_when = para(c, s["when"], x + 22, 0, inner, 15, "PopB", NAVY, 1.25, draw=False)
    h_dont = para(c, s["dont"], x + 22, 0, inner, 11, "LoraI", SOFT, draw=False)
    h_say = para(c, s["say"], x + 22, 0, inner, 12.5, "Lora", NAVY, draw=False)
    h_why = para(c, "<b>Why it works:</b> " + s["why"], x + 22, 0, inner, 10, "Lora", SOFT, draw=False)
    total = 18 + h_when + 12 + 12 + h_dont + 12 + 12 + h_say + 12 + h_why + 18
    if not draw:
        return total
    c.setFillColor(WHITE); c.roundRect(x, y - total, w, total, 16, stroke=0, fill=1)
    c.setFillColor(HexColor(col)); c.roundRect(x, y - total, 6, total, 3, stroke=0, fill=1)
    yy = y - 18
    c.setFillColor(HexColor(col)); c.setFont("PopB", 9); c.drawRightString(x + w - 20, yy - 10, f"#{n:02d}")
    yy -= para(c, s["when"], x + 22, yy, inner - 30, 15, "PopB", NAVY, 1.25) + 12
    c.setFillColor(CORAL); c.setFont("PopB", 8.5); c.drawString(x + 22, yy - 8, "DON'T SAY"); yy -= 12
    yy -= para(c, s["dont"], x + 22, yy, inner, 11, "LoraI", SOFT) + 12
    c.setFillColor(MUSTARD); c.setFont("PopB", 8.5); c.drawString(x + 22, yy - 8, "SAY THIS INSTEAD"); yy -= 12
    yy -= para(c, s["say"], x + 22, yy, inner, 12.5, "Lora", NAVY) + 12
    para(c, "<b>Why it works:</b> " + s["why"], x + 22, yy, inner, 10, "Lora", SOFT)
    return total


def sections(c, page):
    n = 0
    for name, col, items in SECTIONS:
        c.showPage(); page += 1; bg(c)
        c.setFillColor(HexColor(col)); c.setFont("PopB", 10)
        c.drawString(M, H - 70, f"PART {SECTIONS.index((name, col, items)) + 1}")
        c.setFillColor(NAVY); c.setFont("PopB", 26); c.drawString(M, H - 102, name)
        y = H - 128
        for s in items:
            n += 1
            need = script_block(c, n, s, col, y, draw=False)
            if y - need < 50:
                footer(c, page); c.showPage(); page += 1; bg(c); y = H - 60
            y -= script_block(c, n, s, col, y) + 14
        footer(c, page)
    return page


def closing(c, page):
    c.showPage(); page += 1; bg(c, NAVY)
    c.setFillColor(CREAM); c.setFont("PopB", 30); c.drawString(M, H - 150, "One script a day.")
    c.setFillColor(MUSTARD); c.setFont("LoraI", 20); c.drawString(M, H - 185, "That's how the words become yours.")
    para(c, "We post new scripts every day for raises, pricing, bosses, clients and the conversations "
            "nobody teaches you. Follow along so you always have the words ready.", M, H - 215, W - 2 * M, 14, "Lora", CREAM)
    c.setFillColor(WHITE); c.roundRect(M, H - 400, W - 2 * M, 110, 16, stroke=0, fill=1)
    c.setFillColor(NAVY); c.setFont("PopB", 16); c.drawString(M + 24, H - 330, "@saythis.instead")
    c.setFont("Pop", 11); c.setFillColor(SOFT)
    c.drawString(M + 24, H - 352, "on TikTok and Instagram")
    c.drawString(M + 24, H - 372, "Send it to a friend who has a hard conversation coming up.")
    para(c, "These scripts are communication examples, not legal, financial or career advice. "
            "Adapt them to your situation.", M, 90, W - 2 * M, 8.5, "Lora", SOFT)
    footer(c, page)


def build(out):
    c = canvas.Canvas(out, pagesize=letter)
    c.setTitle("Say This Instead: The Starter Playbook"); c.setAuthor("Say This Instead")
    cover(c); c.showPage(); intro(c)
    page = sections(c, 2)
    closing(c, page)
    c.save()


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "Say-This-Instead-Starter-Playbook.pdf")
    build(out); print(out)
