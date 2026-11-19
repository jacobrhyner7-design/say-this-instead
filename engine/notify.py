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


def carousel_kit(brand, when_utc, tiktok_caption, ig_caption, slide_urls):
    """Carousel slot: TikTok gets the slides as a draft; Instagram has no drafts through its API, so the slides
    and both captions come to Jacob's phone (ntfy) at post time, to post by hand with a sound."""
    cfg = json.load(open(os.path.join(ROOT, "config.json")))
    topic = cfg.get("tiktok", {}).get("draft_notify_topic")
    if not topic:
        return
    delay = str(int(when_utc.timestamp()))

    def send(body, title, extra=None):
        h = {"Title": title, "Tags": "camera_flash", "Delay": delay}
        h.update(extra or {})
        req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode("utf-8"), method="POST", headers=h)
        try:
            urllib.request.urlopen(req, timeout=20).read()
        except Exception as e:
            print("carousel notification failed:", e)

    send(tiktok_caption, f"{brand}: TikTok carousel draft is in your TikTok inbox. Caption below")
    send(ig_caption, f"{brand}: Instagram carousel caption (slides follow)")
    for i, u in enumerate(slide_urls, 1):
        send(f"Slide {i} of {len(slide_urls)}", f"{brand}: Instagram slide {i}",
             {"Attach": u, "Filename": f"slide_{i:02d}.jpg"})
