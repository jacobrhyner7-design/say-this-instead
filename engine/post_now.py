"""Post one script right now (a few minutes from now) to one platform, outside the daily schedule.

Example: python engine/post_now.py --says "I'm not tired!" --platform instagram
Finds the script in engine/seed_queue.py by its "says" text or swap title, renders it,
uploads once, posts, and adds a row to data/log.csv. The daily schedule is untouched.
"""
import argparse, csv, datetime as dt, json, os, sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "engine"))
from make_video import render  # noqa: E402
from seed_queue import POSTS  # noqa: E402
import daily  # noqa: E402
from publish import upload, schedule, schedule_instagram  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--says", required=True)
    ap.add_argument("--platform", choices=["instagram", "tiktok", "both"], default="instagram")
    a = ap.parse_args()
    cfg = json.load(open(os.path.join(ROOT, "config.json")))
    tz = ZoneInfo(cfg["timezone"])
    key = a.says.strip().lower()
    p = next((x for x in POSTS if (x.get("says") or x.get("title", "")).strip().lower() == key), None)
    if not p:
        raise SystemExit(f"No script found matching: {a.says}")
    now = dt.datetime.now(tz)
    seed = int(now.strftime("%Y%m%d")) * 10 + 7
    os.makedirs(daily.OUT, exist_ok=True)
    fname = f"now_{now.strftime('%Y-%m-%d_%H%M')}.mp4"
    path = os.path.join(daily.OUT, fname)
    tracks = sorted(f for f in os.listdir(daily.MUSIC) if f.endswith(".m4a"))
    render(p, path, music=os.path.join(daily.MUSIC, tracks[seed % len(tracks)]), seed=seed)
    when = (now + dt.timedelta(minutes=4)).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    media = upload(path)
    row = {"date": now.date().isoformat(), "time_ct": now.strftime("%H:%M") + " (manual)", "format": p["format"],
           "topic": p["topic"], "hook": daily.hook_of(p), "file": fname, "source": "manual"}
    if a.platform in ("tiktok", "both"):
        cap = daily.build_caption(p, seed)
        row.update(caption=cap, submission_id=schedule(path, cap, when, cfg, media_url=media), status="scheduled")
    if a.platform in ("instagram", "both"):
        cap = daily.build_caption(p, seed, cfg["instagram"].get("caption_add", ""), platform="instagram")
        row.update(ig_submission_id=schedule_instagram(media, cap, when, cfg, first_comment=daily.first_comment(cfg)), ig_status="scheduled")
        row.setdefault("caption", cap)
    rows = daily.read_log()
    rows.append(row)
    daily.write_log(rows)
    print("posting at", when, "|", row)


if __name__ == "__main__":
    main()
