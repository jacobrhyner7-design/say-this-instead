"""Upload a video to Blotato and schedule it on the Say This Instead TikTok (@saythis.instead).

The account is picked by handle, never "the first TikTok account", because the same
Blotato workspace also posts for Lunar Scripts."""
import json, os, urllib.request

BASE = "https://backend.blotato.com/v2"
HANDLE = os.environ.get("LM_TIKTOK_HANDLE", "saythis.instead")


def _call(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"blotato-api-key": os.environ["BLOTATO_API_KEY"],
                                          "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def tiktok_account_id():
    if os.environ.get("BLOTATO_TIKTOK_ACCOUNT_ID"):
        return os.environ["BLOTATO_TIKTOK_ACCOUNT_ID"]
    res = _call("GET", "/users/me/accounts?platform=tiktok")
    items = res.get("items", res) if isinstance(res, dict) else res
    wants = {HANDLE.lower().replace(".", ""), HANDLE.lower().split(".")[0]}  # saythisinstead, saythis
    for a in items or []:
        blob = json.dumps(a).lower().replace(".", "").replace(" ", "")
        if any(w in blob for w in wants):
            return str(a["id"])
    names = [{k: a.get(k) for k in ("id", "username", "fullname", "name") if k in a} for a in items or []]
    raise SystemExit(f"@{HANDLE} is not connected in Blotato yet. Connected TikTok accounts: {names}")


def upload(path):
    res = _call("POST", "/media/uploads", {"filename": os.path.basename(path)})
    ctype = "image/jpeg" if path.lower().endswith((".jpg", ".jpeg")) else "video/mp4"
    with open(path, "rb") as f:
        put = urllib.request.Request(res["presignedUrl"], data=f.read(), method="PUT",
                                     headers={"content-type": ctype})
        urllib.request.urlopen(put, timeout=300).read()
    return res["publicUrl"]


def account_by_handle(platform, handle):
    res = _call("GET", f"/users/me/accounts?platform={platform}")
    items = res.get("items", res) if isinstance(res, dict) else res
    wants = {handle.lower().replace(".", ""), handle.lower().split(".")[0]}
    for a in items or []:
        blob = json.dumps(a).lower().replace(".", "").replace(" ", "")
        if any(w in blob for w in wants):
            return str(a["id"])
    names = [{k: a.get(k) for k in ("id", "username", "fullname", "name") if k in a} for a in items or []]
    raise SystemExit(f"@{handle} is not connected on {platform} in Blotato yet. Connected: {names}")


def schedule_instagram(media_url, caption, when_utc_iso, cfg, trial=False, first_comment=None):
    """Same video as a Reel. First comment goes up with the post (the share ask).
    trial=True sends it as a Trial Reel: shown to non-followers first, auto-shared to followers if it does well."""
    ig = cfg["instagram"]
    target = {"targetType": "instagram", "mediaType": "reel", "shareToFeed": True}
    if first_comment:
        target["firstComment"] = first_comment[:2200]
    if trial:
        target["trial"] = {"graduationStrategy": "SS_PERFORMANCE"}
    body = {
        "post": {
            "accountId": ig.get("account_id") or account_by_handle("instagram", ig["handle"]),
            "content": {"text": caption, "mediaUrls": [media_url], "platform": "instagram"},
            "target": target,
        },
        "scheduledTime": when_utc_iso,
    }
    return _call("POST", "/posts", body)["postSubmissionId"]


def facebook_page_id(fb):
    """The Facebook Page to post to, from config or the account's subaccounts (first Page matching the name)."""
    if fb.get("page_id"):
        return str(fb["page_id"])
    res = _call("GET", f"/users/me/accounts/{fb['account_id']}/subaccounts")
    items = res.get("items", res) if isinstance(res, dict) else res
    want = (fb.get("page_name") or "").lower().replace(" ", "")
    for s in items or []:
        if not want or want in json.dumps(s).lower().replace(" ", ""):
            return str(s["id"])
    raise SystemExit(f"No Facebook Page found for {fb.get('page_name')}: {items}")


def schedule_facebook(media_url, caption, when_utc_iso, cfg, first_comment=None):
    """Cross-post the same video to the brand's Facebook Page as a Reel."""
    fb = cfg["facebook"]
    target = {"targetType": "facebook", "pageId": facebook_page_id(fb), "mediaType": "reel"}
    if first_comment:
        target["firstComment"] = first_comment[:2200]
    body = {
        "post": {
            "accountId": str(fb["account_id"]),
            "content": {"text": caption, "mediaUrls": [media_url], "platform": "facebook"},
            "target": target,
        },
        "scheduledTime": when_utc_iso,
    }
    return _call("POST", "/posts", body)["postSubmissionId"]


def schedule_carousel(platform, image_urls, caption, when_utc_iso, cfg, title="", first_comment=None):
    """A swipeable photo post (TikTok photo mode, Instagram carousel, Facebook multi-photo post)."""
    if platform == "tiktok":
        t = cfg["tiktok"]
        acct = t.get("account_id") or tiktok_account_id()
        target = {"targetType": "tiktok", "privacyLevel": t["privacy"], "disabledComments": False,
                  "disabledDuet": False, "disabledStitch": False, "isBrandedContent": False, "isYourBrand": False,
                  "isAiGenerated": bool(t["ai_label"]), "title": title[:90], "autoAddMusic": True,
                  "imageCoverIndex": 0}
    elif platform == "instagram":
        ig = cfg["instagram"]
        acct = ig.get("account_id") or account_by_handle("instagram", ig["handle"])
        target = {"targetType": "instagram", "altText": title[:1000]}
        if first_comment:
            target["firstComment"] = first_comment[:2200]
    else:
        fb = cfg["facebook"]
        acct = str(fb["account_id"])
        target = {"targetType": "facebook", "pageId": facebook_page_id(fb)}
        if first_comment:
            target["firstComment"] = first_comment[:2200]
    body = {"post": {"accountId": str(acct),
                     "content": {"text": caption, "mediaUrls": list(image_urls), "platform": platform},
                     "target": target},
            "scheduledTime": when_utc_iso}
    return _call("POST", "/posts", body)["postSubmissionId"]


def schedule(video_path, caption, when_utc_iso, cfg, promo=False, media_url=None, draft=None):
    t = cfg["tiktok"]
    body = {
        "post": {
            # pinned Blotato account ID first, so renaming the TikTok handle can't break posting
            "accountId": t.get("account_id") or tiktok_account_id(),
            "content": {"text": caption, "mediaUrls": [media_url or upload(video_path)], "platform": "tiktok"},
            "target": {
                "targetType": "tiktok",
                "privacyLevel": t["privacy"],
                "disabledComments": False, "disabledDuet": False, "disabledStitch": False,
                "isBrandedContent": False,
                "isYourBrand": bool(promo),
                "isAiGenerated": bool(t["ai_label"]),
                "isDraft": bool(t["save_as_draft_instead"]) if draft is None else bool(draft),
            },
        },
        "scheduledTime": when_utc_iso,
    }
    return _call("POST", "/posts", body)["postSubmissionId"]


def status(submission_id):
    return _call("GET", f"/posts/{submission_id}")
