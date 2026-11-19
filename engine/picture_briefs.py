"""Picture prompts for Say This Instead: one picture per card, matching that card's words.

Signature look (different from Toddler Translator's storybook): modern editorial illustration, flat graphic
shapes with soft grain, a limited palette of deep navy, coral, warm cream and mustard. Adults at work and at home,
every race and gender rotating. The top 40 percent stays plain for the words.

Each post carries `cast` (the person the post follows) and `setting` (where the first picture happens);
the scene for each card is built from the card's role, so every picture matches its words."""

STYLE = ("Modern editorial illustration, flat graphic shapes, subtle grain, palette of navy, coral, cream and "
         "mustard. Main character: {cast}. Scene: {scene} Top 40 percent is a plain empty cream wall for text; "
         "people in the lower 60 percent, faces visible and expressive. One single scene, no panels, no split frames, no duplicated people. No text, letters, numbers or logos.")


def scenes_for(p):
    """One scene per card of the full plan (make_video.plan_illustrated(p, full=True))."""
    s, who = p["setting"], p.get("who", "the other person").replace("your ", "the ")
    if p["format"] == "translator":
        return [
            f"Close-up, emotional: {s}. The main character's face shows the exact feeling of this moment: "
            f"{p['hook']}",
            f"The main character pauses and thinks, looking at {who}, reading between the lines, calm focus.",
            f"The main character speaks calmly and confidently to {who}, open hands, steady posture.",
            f"The main character offers a clear choice to {who}, who starts to nod.",
            f"{who.capitalize()} and the main character find agreement, relaxed shoulders, a small smile.",
            "The main character walks away lighter, a confident small smile, natural light.",
        ]
    if p["format"] == "swap":
        return [f"Close-up, emotional: {s}. The main character's face shows: {p['hook']}"] + [
            f"The main character speaks up with calm, quiet confidence, "
            f"moment {i + 1} of 3 in the same place." for i in range(len(p["pairs"]))
        ] + ["The main character, proud and relaxed, closing a laptop or leaving the room with a nod."]
    # feel
    out = [f"Close-up, emotional: {s}. The main character's face shows: {p['hook']}"]
    for line in p["lines"]:
        out.append(f"The main character in a quiet, honest moment that shows this thought: {line}")
    out.append("The main character looks up with calm resolve and a small hopeful smile, warm light.")
    return out


def prompts_for(p):
    return [STYLE.format(cast=p["cast"], scene=sc) for sc in scenes_for(p)]


# kept for tools written for the Toddler engine
BRIEFS = {}
RACE = {}
