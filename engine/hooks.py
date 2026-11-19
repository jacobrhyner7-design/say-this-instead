"""Cold-open hooks: the first 3 seconds of every Toddler Translator video.

Rules (people decide in about 3 seconds whether to keep watching):
- Name a moment the viewer lived this week, in their words, so they feel seen before they think.
- Concrete beats abstract: crossed arms, tears at the door, a blanket at midnight.
- Second person or the toddler's own words. Present tense. 12 words max, two short lines.
- Leave a loop open (a hurt, a fear, a question) that the rest of the video answers.
- It must match the first picture, since that picture is what they see behind it.
- Pull one of the emotional triggers that make persons stop, feel and share:
  guilt ("you yelled today"), time slipping away ("the last bedtime story"), being seen in the hard part
  ("it's midnight and you're here"), their child's pain ("she held it together all day"), fear of failing them,
  and the ache of loving someone this small.
- Never use em dashes.
A post can set its own "hook"; otherwise this table is used, keyed by "says" or "title"."""

HOOKS = {}  # every Say This Instead post carries its own "hook"


def hook(p):
    """Every post opens cold. Order: the post's own hook, this table, then its emotional opener or title."""
    got = p.get("hook") or HOOKS.get(p.get("says") or p.get("title", ""))
    if got:
        return got
    from feel_hooks import feel_hook
    fallback = feel_hook(p) or p.get("title") or ""
    if fallback:
        return fallback.rstrip(".…").strip() + "."
    if p.get("says"):
        said = p["says"].strip("* ")
        return (f"'{said}' You've been here before." if not p["says"].startswith("*")
                else f"They {said}. And you freeze.")
    return None


# The feeling the music carries on each post (engine/music/emotional/<mood>_N.m4a):
# nostalgia = time slipping away; comfort = a hard moment that turns to relief; uplift = pride, being seen;
# lullaby = bedtime tenderness; playful = everyday battles met with love.
MUSIC_MOOD = {}  # every post carries its own "mood"
MOOD_NAMES = ("nostalgia", "comfort", "uplift", "lullaby", "playful")


def music_mood(p):
    m = p.get("mood") or MUSIC_MOOD.get(p.get("says") or p.get("title", ""))
    return m if m in MOOD_NAMES else None
