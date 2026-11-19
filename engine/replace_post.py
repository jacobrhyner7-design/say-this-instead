"""Swap an already-scheduled post for a new render, keeping its time slot.

Reads data/replace.json: {"when_ct": "2026-11-11 20:30", "mode": "list" | "replace"}
  list    -> only finds the scheduled TikTok/Instagram posts at that time (changes nothing)
  replace -> renders data/preview.json with the real voice, schedules it at the same time on the
             same accounts, then cancels the old scheduled posts. New posts are created first, so a
             failure never leaves the slot empty.
Writes previews/replace-result.json."""
import datetime as dt, json, os, sys
from zoneinfo import ZoneInfo
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "engine"))
from publish import _call, upload, schedule, schedule_instagram  # noqa: E402
import daily  # noqa: E402

cfg = json.load(open(os.path.join(ROOT, "config.json")))
job = json.load(open(os.path.join(ROOT, "data", "replace.json")))
tz = ZoneInfo(cfg["timezone"])
when_local = dt.datetime.strptime(job["when_ct"], "%Y-%m-%d %H:%M").replace(tzinfo=tz)
when_utc = when_local.astimezone(dt.timezone.utc)
when_s = when_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
ACCTS = {str(cfg["tiktok"]["account_id"]): "tiktok", str(cfg["instagram"]["account_id"]): "instagram"}
if cfg.get("facebook", {}).get("enabled") and cfg["facebook"].get("account_id"):
    ACCTS[str(cfg["facebook"]["account_id"])] = "facebook"


def cancel(schedule_id):
    """DELETE /schedules/:id. No JSON content-type on an empty body (the API rejects that with 400)."""
    import urllib.request
    req = urllib.request.Request(f"https://backend.blotato.com/v2/schedules/{schedule_id}", method="DELETE",
                                 headers={"blotato-api-key": os.environ["BLOTATO_API_KEY"]})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status


def find(obj, *names):
    """First value for any of these keys, searching nested dicts."""
    if isinstance(obj, dict):
        for n in names:
            if n in obj and obj[n] not in (None, ""):
                return obj[n]
        for v in obj.values():
            got = find(v, *names)
            if got not in (None, ""):
                return got
    return None


def scheduled_at(item):
    t = find(item, "scheduledAt", "scheduledTime", "scheduled_at")
    try:
        return dt.datetime.fromisoformat(str(t).replace("Z", "+00:00"))
    except Exception:
        return None


def matches():
    out, cursor = [], None
    for _ in range(10):
        res = _call("GET", "/schedules?limit=50" + (f"&cursor={cursor}" if cursor else ""))
        items = res.get("items") or res.get("data") or res.get("schedules") or (res if isinstance(res, list) else [])
        for it in items:
            acct = str(find(it, "accountId") or find(find(it, "account") or {}, "id") or "")
            t = scheduled_at(it)
            if acct in ACCTS and t and abs((t - when_utc).total_seconds()) <= 90:
                out.append({"id": it.get("id"), "platform": ACCTS[acct], "account": acct, "at": t.isoformat(),
                            "media": find(it, "mediaUrls")})
        cursor = res.get("cursor") if isinstance(res, dict) else None
        if not cursor:
            break
    return out


old = matches()
result = {"when_utc": when_s, "found": old, "mode": job["mode"]}
if job["mode"] == "cancel":  # cancel exactly these schedule ids (and only if they are at this time)
    ids = {str(x) for x in job["ids"]}
    result["cancelled"], result["cancel_errors"] = [], []
    for m in old:
        if str(m["id"]) in ids:
            try:
                cancel(m["id"])
                result["cancelled"].append(m["id"])
            except Exception as e:
                body = getattr(e, "read", lambda: b"")()[:200]
                result["cancel_errors"].append(f"{m['id']}: {str(e)[:80]} {body!r}")
    result["after"] = matches()
if job["mode"] == "add_facebook":  # cross-post an already-scheduled video to the Facebook Page at the same time
    from publish import schedule_facebook
    media = next((m["media"][0] for m in old if m.get("media")), None)
    if not media:
        raise SystemExit("Nothing scheduled at that time; not posting anything.")
    rows = daily.read_log()
    row = next((r for r in rows if r.get("date") == when_local.date().isoformat()
                and r.get("time_ct") == when_local.strftime("%H:%M") and not r.get("fb_submission_id")), None)
    if row is None:
        raise SystemExit("No log row for that slot, or it is already on Facebook.")
    sid = schedule_facebook(media, row["caption"], when_s, cfg, first_comment=daily.first_comment(cfg))
    row["fb_submission_id"], row["fb_status"] = sid, "scheduled"
    daily.write_log(rows)
    result["facebook_submission"] = sid
if job["mode"] == "replace":
    plats = {m["platform"] for m in old}
    if not old:
        raise SystemExit("Nothing scheduled at that time; not posting anything.")
    from make_video import render
    p = json.load(open(os.path.join(ROOT, "data", "preview.json")))
    seed = int(when_local.strftime("%Y%m%d")) * 10
    os.makedirs(daily.OUT, exist_ok=True)
    fname = when_local.strftime("%Y-%m-%d_%H%M") + "_v2.mp4"
    path = os.path.join(daily.OUT, fname)
    tracks = sorted(f for f in os.listdir(daily.MUSIC) if f.endswith(".m4a"))
    render(p, path, music=os.path.join(daily.MUSIC, tracks[seed % len(tracks)]), seed=seed)
    import shutil
    os.makedirs(os.path.join(ROOT, "previews"), exist_ok=True)
    shutil.copy(path, os.path.join(ROOT, "previews", "replaced.mp4"))  # the exact video that was scheduled
    media = upload(path)
    new = {}
    if "tiktok" in plats:
        new["tiktok"] = schedule(path, daily.build_caption(p, seed), when_s, cfg, media_url=media)
    if "instagram" in plats:
        new["instagram"] = schedule_instagram(media, daily.build_caption(p, seed, cfg["instagram"].get("caption_add", ""),
                                              platform="instagram"), when_s, cfg, first_comment=daily.first_comment(cfg))
    if "facebook" in plats:
        from publish import schedule_facebook
        new["facebook"] = schedule_facebook(media, daily.build_caption(p, seed, cfg["facebook"].get("caption_add", ""),
                                            platform="facebook"), when_s, cfg, first_comment=daily.first_comment(cfg))
    result["new_submissions"] = new
    cancelled = []
    for m in old:
        try:
            cancel(m["id"])
            cancelled.append(m["id"])
        except Exception as e:
            body = getattr(e, "read", lambda: b"")()[:200]
            result.setdefault("cancel_errors", []).append(f"{m['id']}: {str(e)[:80]} {body!r}")
    result["cancelled"] = cancelled
    result["after"] = matches()
    rows = daily.read_log()
    for r in rows:
        if r.get("date") == when_local.date().isoformat() and r.get("time_ct") == when_local.strftime("%H:%M"):
            r["file"] = fname
            if "tiktok" in new:
                r["submission_id"] = new["tiktok"]
            if "instagram" in new:
                r["ig_submission_id"] = new["instagram"]
            if "facebook" in new:
                r["fb_submission_id"] = new["facebook"]
    daily.write_log(rows)
os.makedirs(os.path.join(ROOT, "previews"), exist_ok=True)
json.dump(result, open(os.path.join(ROOT, "previews", "replace-result.json"), "w"), indent=2, default=str)
print(json.dumps(result, indent=2, default=str))
