"""Daily run: pick or write today's posts, render them, schedule them on TikTok, update the log.

Env: ANTHROPIC_API_KEY, BLOTATO_API_KEY, optional BLOTATO_TIKTOK_ACCOUNT_ID,
DRY_RUN=1 (render only), RUN_DATE=YYYY-MM-DD (override date).
"""
import csv, datetime as dt, json, os, sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "engine"))
from make_video import render  # noqa: E402

DATA, OUT = os.path.join(ROOT, "data"), os.path.join(ROOT, "out")
LOG = os.path.join(DATA, "log.csv")
MUSIC = os.path.join(ROOT, "engine", "music")
FIELDS = ["date", "time_ct", "format", "topic", "hook", "caption", "file", "submission_id", "status", "url", "source",
          "ig_submission_id", "ig_status", "ig_url", "ig_trial", "fb_submission_id", "fb_status", "fb_url"]


def load(name, default):
    p = os.path.join(DATA, name)
    return json.load(open(p)) if os.path.exists(p) else default



def publish_time(cfg, day, slot):
    """Posting time for a slot on a given day (Saturdays the first post moves later: people sleep in)."""
    wd = str(dt.date.fromisoformat(day).weekday())
    return cfg.get("day_overrides", {}).get(wd, {}).get(slot, slot)

def read_log():
    return list(csv.DictReader(open(LOG))) if os.path.exists(LOG) else []


def write_log(rows):
    with open(LOG, "w", newline="") as f:
        w = csv.DictWriter(f, FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def refresh_statuses(rows):
    from publish import status
    for r in rows:
        for sid, st, url in (("submission_id", "status", "url"), ("ig_submission_id", "ig_status", "ig_url"),
                             ("fb_submission_id", "fb_status", "fb_url")):
            cur = r.get(st) or ""
            if r.get(sid) and cur != "published" and not cur.startswith("failed"):
                try:
                    s = status(r[sid])
                    r[st] = s.get("status", cur)
                    r[url] = s.get("publicUrl") or r.get(url, "")
                    if s.get("errorMessage"):
                        r[st] = "failed: " + s["errorMessage"][:120]
                except Exception as e:
                    print("status check failed:", e)

def hook_of(p):
    return p.get("says") or p.get("title", "")


# Broad tags rotate so every post isn't identical; the post's own topic tags always stay.
TAG_POOL = ["#careeradvice", "#worklife", "#salarynegotiation", "#careertips", "#corporatelife",
            "#negotiation", "#jobsearch", "#moneytips", "#salestips", "#freelancetips"]


IG_TAGS = {}


SHARE_ASKS = ["Send this to someone who needs these words this week 💬",
              "Share this with a coworker who needs it 🙌",
              "Send this to the friend who undercharges 💬",
              "Share this with someone who's job hunting right now 🙌"]
OPENERS = {"translator": ["Leave a 🙋 if you've heard this at work…", "Ever been told this? 👇",
                          "Leave a 💬 if this happened to you…"],
           "swap": ["Which one do you catch yourself saying? 👇", "Leave a 🙌 if you're working on this too…"],
           "feel": ["Leave a 🙌 if you needed this today…", "Leave a 💬 if you feel this too…",
                    "Leave a 🙌 if this is you…"]}
BROAD_TAGS = {"tiktok": ["#careeradvice", "#worklife", "#salarynegotiation"],
              "instagram": ["#careeradvice", "#worklife", "#salarynegotiation"],
              "facebook": ["#careeradvice", "#worklife", "#money"]}


def search_line(p):
    topic = p["topic"].lower()
    if p["format"] == "translator":
        says = p["says"]
        if says.startswith("*"):
            return f"What to say when {p.get('who', 'they')} {says.strip('* ')} ({topic} script)"
        return f"What to say when {p.get('who', 'they')} says \u201c{says}\u201d ({topic} script)"
    if p["format"] == "feel":
        return p["title"]
    t = p["title"]
    return t if "instead" in t.lower() else f"{t}, and what to say instead"


def build_caption(p, seed, promo_add="", platform="tiktok"):
    """The viral caption template (modeled on the biggest parenting pages):
    engagement ask, share ask, the searchable phrase and short lines, the comment question,
    the share ask again, dot spacer, 3 broad hashtags plus the post's own topic tag."""
    r = seed // 10 + seed % 10
    opener = OPENERS.get(p["format"], OPENERS["feel"])[r % len(OPENERS.get(p["format"], OPENERS["feel"]))]
    share = SHARE_ASKS[r % len(SHARE_ASKS)]
    body = [search_line(p), p["caption"]]
    if p.get("cta"):
        body.append(f"Tell me in the comments: {p['cta']}")
    parts = [opener + "\n" + share, "\n\n".join(body)]
    if promo_add:
        parts.append(promo_add)
    parts.append(share)
    own = next((t for t in p.get("tags", []) if t not in TAG_POOL and t not in sum(BROAD_TAGS.values(), [])), None)
    tags = BROAD_TAGS.get(platform, BROAD_TAGS["tiktok"]) + ([own] if own else [])
    if platform == "instagram":
        tags = [IG_TAGS.get(t, t) for t in tags]
    return "\n\n".join(parts) + "\n\n•\n•\n•\n" + " ".join(tags)


def post_carousel(cfg, p, day, slot, seed, caption, tz, dry, rows):
    """Carousel slot: the post's cards as swipe-style slides in a video with music that fits the post's mood,
    on TikTok, Instagram and Facebook. (Real photo carousels sent through the API go out silent.)"""
    from make_video import make_carousel, emotional_track
    import slideshow
    folder = os.path.join(OUT, f"{day}_{slot.replace(':', '')}_carousel")
    tall, crops = make_carousel(dict(p), folder, seed)
    music = emotional_track(p, seed)
    path = os.path.join(OUT, f"{day}_{slot.replace(':', '')}_carousel.mp4")
    slideshow.make(tall, music, path)
    row = {"date": day, "time_ct": slot, "format": "carousel", "topic": p["topic"], "hook": hook_of(p),
           "caption": caption, "file": os.path.basename(path), "submission_id": "", "status": "rendered",
           "url": "", "source": p["source"]}
    if not dry:
        from publish import upload, schedule, schedule_instagram, schedule_facebook
        when = dt.datetime.fromisoformat(f"{day}T{publish_time(cfg, day, slot)}").replace(tzinfo=tz).astimezone(dt.timezone.utc)
        when_s = when.strftime("%Y-%m-%dT%H:%M:%SZ")
        media = None
        try:
            media = upload(path)
            row["submission_id"] = schedule(path, caption, when_s, cfg, False, media_url=media)
            row["status"] = "scheduled"
        except SystemExit as e:
            row["status"] = f"error: {e}"[:200]
        except Exception as e:
            row["status"] = f"error: {str(e)[:150]}"
        ig, fb = cfg.get("instagram", {}), cfg.get("facebook", {})
        if ig.get("enabled") and media:
            try:
                row["ig_submission_id"] = schedule_instagram(
                    media, build_caption(p, seed, ig.get("caption_add", ""), platform="instagram"),
                    when_s, cfg, first_comment=first_comment(cfg))
                row["ig_status"] = "scheduled"
            except Exception as e:
                row["ig_status"] = f"error: {str(e)[:150]}"
        if fb.get("enabled") and media:
            try:
                row["fb_submission_id"] = schedule_facebook(
                    media, build_caption(p, seed, fb.get("caption_add", ""), platform="facebook"),
                    when_s, cfg, first_comment=first_comment(cfg))
                row["fb_status"] = "scheduled"
            except Exception as e:
                row["fb_status"] = f"error: {str(e)[:150]}"
    rows.append(row)
    print(slot, "carousel video | music:", os.path.basename(music or "none"), "| tiktok:", row["status"],
          "| ig:", row.get("ig_status") or "off", "| fb:", row.get("fb_status") or "off")


def first_comment(cfg):
    return cfg.get("engagement", {}).get("first_comment", "Share this with another parent who needs to hear this today 💛")

def main():
    cfg = json.load(open(os.path.join(ROOT, "config.json")))
    tz = ZoneInfo(cfg["timezone"])
    day = os.environ.get("RUN_DATE") or dt.datetime.now(tz).date().isoformat()
    launch = cfg.get("launch_date")
    if not launch or day < launch:  # accounts are warming up by hand; nothing posts before launch
        print(f"Before launch ({launch or 'no launch date set'}), nothing to post on {day}.")
        return
    dry = os.environ.get("DRY_RUN") == "1"
    rows = read_log()
    if not dry:
        refresh_statuses(rows)

    times, ramping = cfg["post_times"], False
    for step in cfg.get("ramp", []):  # warm-up: fewer posts a day while the account is new
        if day <= step["until"]:
            times, ramping = step["post_times"], True
            print("Ramp:", step.get("note", ""), times)
            break
    done = {(r["date"], r["time_ct"]) for r in rows if r.get("submission_id")}
    now = dt.datetime.now(tz)
    slots = [s for s in times if (day, s) not in done]
    if not dry:
        slots = [s for s in slots if dt.datetime.fromisoformat(f"{day}T{publish_time(cfg, day, s)}").replace(tzinfo=tz) > now + dt.timedelta(minutes=10)]
    if not slots:
        print("Nothing left to schedule for", day)
        write_log(rows)
        return

    queue, history = load("queue.json", []), load("history.json", [])
    posts = {}
    ordered = sorted(queue, key=lambda q: (q["date"], q["time"]))
    used = set()
    for s in slots:
        # the next post written for this time slot; while ramping, fall back to the next post of any slot
        pick = next((i for i, p in enumerate(ordered) if i not in used and p["time"] == s), None)
        if pick is None and ramping:
            pick = next((i for i in range(len(ordered)) if i not in used), None)
        if pick is not None:
            used.add(pick)
            posts[s] = dict(ordered[pick], time=s, source="queue")
    rest = [p for i, p in enumerate(ordered) if i not in used]
    missing = [s for s in slots if s not in posts]
    if missing:
        try:
            from generate import generate
            for p in generate(missing, cfg["slot_themes"], history, cfg["claude_model"]):
                posts[p["slot"]] = dict(p, time=p["slot"], source="claude")
        except Exception as e:
            print("Could not write new posts with Claude:", e)
            for s in missing:
                rows.append({"date": day, "time_ct": s, "status": f"skipped: writing failed ({str(e)[:80]})", "source": "claude"})

    os.makedirs(OUT, exist_ok=True)
    tracks = sorted(f for f in os.listdir(MUSIC) if f.endswith(".m4a"))
    promo_cfg = cfg["promo"]
    count = sum(1 for r in rows if r.get("submission_id"))
    for i, slot in enumerate(slots):
        p = posts.get(slot)
        if not p:
            continue
        n = count + i + 1
        promo = promo_cfg["enabled"] and n % promo_cfg["every_nth_post"] == 0
        if promo:
            p = dict(p, footer=promo_cfg["footer"], footer_voice=promo_cfg["footer_voice"])
        seed = int(day.replace("-", "")) * 10 + i
        fname = f"{day}_{slot.replace(':', '')}.mp4"
        path = os.path.join(OUT, fname)
        caption = build_caption(p, seed, promo_cfg["caption_add"] if promo else "")
        if slot in cfg.get("carousel_slots", []):  # one post a day is a swipeable carousel instead of a video
            post_carousel(cfg, p, day, slot, seed, caption, tz, dry, rows)
            history.append(hook_of(p))
            continue
        render(p, path, music=os.path.join(MUSIC, tracks[seed % len(tracks)]), seed=seed)
        draft = slot in cfg["tiktok"].get("draft_slots", [])  # TikTok copy goes to drafts for a trending sound
        if draft:
            from make_video import render as _r
            draft_path = path.replace(".mp4", "_draft.mp4")
            _r(dict(p), draft_path, music=os.path.join(MUSIC, tracks[seed % len(tracks)]), seed=seed, no_music=True)
        row = {"date": day, "time_ct": slot, "format": p["format"], "topic": p["topic"], "hook": hook_of(p),
               "caption": caption, "file": fname, "submission_id": "", "status": "rendered", "url": "",
               "source": p["source"]}
        if not dry:
            from publish import schedule, schedule_instagram, upload
            when = dt.datetime.fromisoformat(f"{day}T{publish_time(cfg, day, slot)}").replace(tzinfo=tz).astimezone(dt.timezone.utc)
            when_s = when.strftime("%Y-%m-%dT%H:%M:%SZ")
            media = None
            try:
                media = upload(path)
                if draft:
                    row["submission_id"] = schedule(draft_path, caption, when_s, cfg, promo,
                                                    media_url=upload(draft_path), draft=True)
                    row["status"] = "draft sent"
                    from notify import draft_caption
                    draft_caption(caption, "Say This Instead", when)
                else:
                    row["submission_id"] = schedule(path, caption, when_s, cfg, promo, media_url=media)
                    row["status"] = "scheduled"
            except SystemExit as e:
                row["status"] = f"error: {e}"[:200]
            except Exception as e:
                row["status"] = f"error: {str(e)[:150]}"
            ig = cfg.get("instagram", {})
            if ig.get("enabled") and media:
                try:  # Instagram never blocks TikTok: its errors only land in ig_status
                    ig_caption = build_caption(p, seed, ig.get("caption_add", ""), platform="instagram")
                    # half of the test-format posts go out as Trial Reels so the grid still fills up
                    trial = p["format"] in ig.get("trial_formats", []) and (n % 2 == 0)
                    row["ig_submission_id"] = schedule_instagram(media, ig_caption, when_s, cfg, trial=trial,
                                                                 first_comment=first_comment(cfg))
                    row["ig_trial"] = "yes" if trial else ""
                    row["ig_status"] = "scheduled"
                except SystemExit as e:
                    row["ig_status"] = f"error: {e}"[:200]
                except Exception as e:
                    row["ig_status"] = f"error: {str(e)[:150]}"
            fb = cfg.get("facebook", {})
            if fb.get("enabled") and media:
                try:  # Facebook never blocks the other platforms
                    from publish import schedule_facebook
                    row["fb_submission_id"] = schedule_facebook(media, build_caption(p, seed, fb.get("caption_add", ""),
                                                                                     platform="facebook"),
                                                                when_s, cfg, first_comment=first_comment(cfg))
                    row["fb_status"] = "scheduled"
                except SystemExit as e:
                    row["fb_status"] = f"error: {e}"[:200]
                except Exception as e:
                    row["fb_status"] = f"error: {str(e)[:150]}"
        rows.append(row)
        history.append(hook_of(p))
        print(slot, "tiktok:", row["status"], "| ig:", row.get("ig_status") or "off",
              "| fb:", row.get("fb_status") or "off", "|", row["hook"])

    if dry:
        print("Dry run: videos rendered to out/, nothing posted, data files untouched.")
        return
    json.dump(rest, open(os.path.join(DATA, "queue.json"), "w"), indent=1, ensure_ascii=False)
    json.dump(history[-1500:], open(os.path.join(DATA, "history.json"), "w"), indent=0, ensure_ascii=False)
    write_log(rows)

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(f"## Toddler Translator {day}\n\n| Time CT | Hook | TikTok | Instagram |\n|---|---|---|---|\n")
            for r in rows[-6:]:
                f.write(f"| {r['date']} {r['time_ct']} | {r.get('hook', '')} | {r['status']} {r.get('url', '')} | "
                        f"{r.get('ig_status') or 'off'} {r.get('ig_url') or ''} |\n")


if __name__ == "__main__":
    main()
