"""Render one feel post with the ElevenLabs voice (no posting). Fails loudly if ElevenLabs is not working.
Writes out/voice-test.mp4 and data/voice-test.json (what happened), which the workflow commits back."""
import json, os, sys, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
import voice
from feel_posts import FEEL
from make_video import render, HERE

ROOT = os.path.dirname(HERE)
report = {"voice_id": voice.VCFG.get("eleven_voice_id"), "key_present": bool(os.environ.get("ELEVENLABS_API_KEY"))}
# 1) one direct ElevenLabs call, so we see the real error if it fails
try:
    key = os.environ["ELEVENLABS_API_KEY"]
    body = json.dumps({"text": "If you yelled today, read this.", "model_id": voice.VCFG.get("eleven_model")}).encode()
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{report['voice_id']}",
                                 data=body, headers={"xi-api-key": key, "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        report["tts_ok"] = True
        report["headers"] = {k: v for k, v in r.headers.items() if "char" in k.lower() or "cost" in k.lower()
                             or k.lower().startswith("x-")}
except urllib.error.HTTPError as e:
    report["tts_ok"] = False
    report["error"] = f"{e.code} {e.read()[:400].decode(errors='ignore')}"
except Exception as e:
    report["tts_ok"] = False
    report["error"] = str(e)[:400]
# 2) subscription usage, if the key is allowed to read it
try:
    req = urllib.request.Request("https://api.elevenlabs.io/v1/user/subscription",
                                 headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]})
    with urllib.request.urlopen(req, timeout=30) as r:
        s = json.load(r)
    report["subscription"] = {k: s.get(k) for k in ("tier", "character_count", "character_limit", "status")}
except Exception as e:
    report["subscription"] = f"not readable with this key ({str(e)[:80]})"
# 3) a full video with the real voice
if report["tts_ok"]:
    os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)
    out, imgs, total = render(FEEL[3], os.path.join(ROOT, "out", "voice-test.mp4"),
                              os.path.join(HERE, "music", "soft-sunrise.m4a"), seed=3)
    report["video_seconds"] = round(total, 1)
json.dump(report, open(os.path.join(ROOT, "data", "voice-test.json"), "w"), indent=2)
print(json.dumps(report, indent=2))
