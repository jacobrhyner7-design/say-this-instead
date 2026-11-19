"""Render data/preview.json with the real voice (ElevenLabs) and post nothing.
Writes previews/preview.mp4 and previews/preview.json (which voice was used per line)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import voice
from make_video import render, HERE

ROOT = os.path.dirname(HERE)
p = json.load(open(os.path.join(ROOT, "data", "preview.json")))
used = []
_orig_eleven = voice._eleven
def _track(text, out, hook=False):
    got = _orig_eleven(text, out, hook)
    used.append("elevenlabs" if got else "fallback")
    return got
voice._eleven = _track
os.makedirs(os.path.join(ROOT, "previews"), exist_ok=True)
out, imgs, total = render(p, os.path.join(ROOT, "previews", "preview.mp4"),
                          os.path.join(HERE, "music", "soft-sunrise.m4a"), seed=20261111)
rep = {"seconds": round(total, 1), "voice_per_card": used, "pictures": p.get("scenes_used")}
json.dump(rep, open(os.path.join(ROOT, "previews", "preview.json"), "w"), indent=2)
print(json.dumps(rep, indent=2))
