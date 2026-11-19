"""Set the launch date: python engine/assign_slots.py 2026-11-24
Writes real dates into the warm-up ramp (week 1: 1 a day, week 2: 2 a day, then 3 a day) and gives every queued
post a real slot, in queue order, so the daily run (which matches posts to slots by time) posts them in order."""
import datetime as dt, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
launch = dt.date.fromisoformat(sys.argv[1])
cfg_path = os.path.join(ROOT, "config.json")
cfg = json.load(open(cfg_path))
cfg["ramp"][0]["until"] = (launch + dt.timedelta(days=6)).isoformat()
cfg["ramp"][1]["until"] = (launch + dt.timedelta(days=13)).isoformat()
cfg["launch_date"] = launch.isoformat()
json.dump(cfg, open(cfg_path, "w"), indent=2, ensure_ascii=False)


def times(day):
    for step in cfg["ramp"]:
        if day <= step["until"]:
            return step["post_times"]
    return cfg["post_times"]


q_path = os.path.join(ROOT, "data", "queue.json")
queue = json.load(open(q_path))
slots, d = [], launch
while len(slots) < len(queue):
    slots += [(d.isoformat(), s) for s in times(d.isoformat())]
    d += dt.timedelta(days=1)
for p, (day, s) in zip(queue, slots):
    p["date"], p["time"] = day, s
json.dump(queue, open(q_path, "w"), indent=2, ensure_ascii=False)
print(f"launch {launch}, {len(queue)} posts through {queue[-1]['date']}")
