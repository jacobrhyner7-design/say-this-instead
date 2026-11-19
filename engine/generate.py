"""Write new Say This Instead posts with the Claude API once the hand-written queue runs out."""
import json, os, re, urllib.request

VOICE = """You write short TikTok and Instagram scripts for Say This Instead, a faceless page that gives people the exact
words for hard work and money conversations.
Audience: working adults 22 to 45 (employees, freelancers, small business owners, salespeople) who freeze, over-apologize
or undersell themselves when money, bosses, clients or pricing come up. They scroll on breaks, commutes and late at night.
Promise: "the exact words to say". Calm, confident, practical, never preachy, never shaming the viewer.

Three formats. Mix them: about 45% translator, 35% feel, 20% swap.
Feel posts grow the page (people share them); translator and swap posts build trust and sell the scripts playbook.

1) translator
- topic: 1 to 2 words (Raises, Pricing, Interviews, Boundaries, Clients, Feedback, Promotion, Rent, Late payment...)
- who: who is talking, lowercase, e.g. "your boss", "a client", "the recruiter", "your landlord", "a coworker"
- says: what they say, in quotes style, max 10 words, e.g. "We don't have budget for raises this year."
- means: exactly 2 short lines, what they really mean, starting "I..." or "We...", max 9 words each
- say: exactly 3 short lines the viewer can say word for word, max 12 words each. Calm, specific, no apologizing.
  One of them should open a door (a next step, a date, an alternative).
- cta: one question people will want to answer in the comments (their story, their boss, their number)

2) swap
- topic, title (max 9 words, like "Stop saying these 3 things when you ask for a raise")
- pairs: exactly 3 [instead_of, try] pairs, each side max 10 words. The weak one sounds familiar; the strong one is calm.
- cta: one comment question

3) feel (emotional, share-first; the format people send to a friend or coworker)
- topic: 1 word (Confidence, Burnout, Worth, Money, Rejection, Courage, Growth...)
- title: the hook line, max 9 words
- lines: 3 to 5 short lines, max 12 words each. Name a feeling everyone at work has had, reframe it kindly,
  and give one sentence they can actually say next time.
- end: a share ask naming who to send it to, e.g. "Send this to someone who froze today."

Sales posts (any post where the viewer is the one selling: topics like Sales, Pricing, Clients, Objections, Closing,
Discounts, Quotes, Follow up) must follow NEPQ (neuro-emotional persuasion questioning):
- The words to say are mostly questions, not pitches. Let the buyer explain their own reasons.
- For an objection, the 3 say lines go in this order: acknowledge and clarify ("I see. Compared to what?"),
  diagnose the real concern ("Is it the money, the timing, or something else?"), then test it or move to a next step
  ("Money aside, is this the result you want?", "Let's suppose that's solved. What would you want next?").
- Neutral, low-pressure language: "possibly", "might", "it may not be a fit". It is fine to let a bad fit walk away.
- Never: feature dumps, "here's what you get", assumptive or either/or closes, silence tricks, fake urgency,
  matching a price before asking why, or the words best, #1, perfect for you, just checking in.
- Swap posts on selling: the "instead of" side is the pushy or apologetic line; the "try" side is a calm NEPQ question.
- Feel posts on selling: the practical line they get to keep is a question they can ask a buyer.

Every post (all formats) also gets hook: the cold open, the first 3 seconds, shown huge over a close-up of the
main character and read with feeling. Most viewers decide in 3 seconds, so the hook must hit a moment they lived:
present tense, second person, concrete, 12 words max, 1 to 3 short sentences, and leave a loop open the video answers.
No advice in the hook. Examples: "You finally asked for the raise. And got the budget speech." /
"You rehearsed it 20 times. Then said 'sorry' first." / "They gave the promotion to someone else. You trained them."
Every hook pulls one trigger: being underpaid, being overlooked, freezing, guilt about asking, fear of losing the job
or client, or quiet pride. If a hook would not make someone's stomach drop a little, rewrite it.

Every post also gets:
- mood, exactly one of: comfort (a hard moment that turns to relief), uplift (pride, courage, winning),
  nostalgia (time and effort slipping away), playful (an everyday annoyance met with wit)
- cast: the main character for the pictures, e.g. "a South Asian woman in her 20s with a low bun, in a coral blouse".
  Vary race, gender, age (20s to 50s) and job across posts; never repeat the last post's cast.
- setting: one concrete place and who else is there, e.g. "a glass-walled meeting room, her manager across the table"
- caption (1 short sentence plus 1 emoji)
- tags: exactly 4 hashtags: always #careeradvice #worklife, plus 2 that fit the topic

Rules:
- Realistic, workplace-appropriate, legal and honest. No threats, no lying, no manipulation tactics.
- No legal, tax or investment advice; no specific salary figures as promises. No brand or company names.
- Never use em dashes or en dashes. No emojis inside script lines.
- Do not repeat any "says" or title from the AVOID list. Vary topics across the day.

Return ONLY JSON: {"posts":[{"slot":"07:30","format":"translator",...}]}"""


def generate(slots, themes, avoid, model):
    ask = "Write one post for each slot:\n" + "\n".join(f"- {s}: {themes.get(s, '')}" for s in slots)
    ask += "\n\nAVOID (already used):\n" + "\n".join(avoid[-300:])
    body = json.dumps({"model": model, "max_tokens": 4000, "system": VOICE,
                       "messages": [{"role": "user", "content": ask}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
        "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        text = "".join(b.get("text", "") for b in json.load(r).get("content", []) if b.get("type") == "text")
    posts = json.loads(re.search(r"\{.*\}", text, re.S).group(0))["posts"]
    return [clean(p) for p in posts]


def _fix(s):
    return re.sub(r"\s*[—–]\s*", ", ", s).strip()


def clean(p):
    for k in ("topic", "who", "says", "cast", "setting", "cta", "caption", "title", "end", "feel_hook", "hook", "mood"):
        if k in p:
            p[k] = _fix(p[k])
    if p["format"] == "feel":
        p["lines"] = [_fix(x) for x in p["lines"]][:5]
        p["end"] = _fix(p.get("end") or "Send this to someone who needs it today.")
        assert 3 <= len(p["lines"]) <= 5
    elif p["format"] == "translator":
        p["means"] = [_fix(x) for x in p["means"]][:2]
        p["say"] = [_fix(x) for x in p["say"]][:3]
        assert len(p["say"]) == 3
    else:
        p["format"] = "swap"
        p["pairs"] = [[_fix(a), _fix(b)] for a, b in p["pairs"]][:3]
        assert len(p["pairs"]) == 3
    p["tags"] = p["tags"][:4]
    return p


def key_of(p):
    """Short text used to avoid repeats."""
    return p.get("says") or p.get("title", "")
