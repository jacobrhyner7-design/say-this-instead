"""Send the draft's caption and hashtags to Jacob's phone (ntfy app), timed for when the TikTok draft arrives.
TikTok drops the caption on drafts sent from apps, so this gives him the text to paste."""
import json, os, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def draft_caption(caption, brand, when_utc):
    cfg = json.load(open(os.path.join(ROOT, "config.json")))
    topic = cfg.get("tiktok", {}).get("draft_notify_topic")
    if not topic:
        return
    req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=caption.encode("utf-8"), method="POST", headers={
        "Title": f"{brand}: TikTok draft caption (long-press to copy)",
        "Tags": "memo",
        "Delay": str(int(when_utc.timestamp())),
    })
    try:
        urllib.request.urlopen(req, timeout=20).read()
    except Exception as e:  # never block posting over a notification
        print("caption notification failed:", e)
