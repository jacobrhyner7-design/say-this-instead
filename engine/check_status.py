"""Refresh Blotato status for recent posts and write data/status-check.json (triggered by data/check.json)."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "engine"))
import daily
from publish import status
rows = daily.read_log()
out = []
for r in rows[-8:]:
    item = {"date": r.get("date"), "time": r.get("time_ct"), "hook": (r.get("hook") or "")[:60]}
    for key, sid in (("tiktok", "submission_id"), ("instagram", "ig_submission_id"), ("facebook", "fb_submission_id")):
        if r.get(sid):
            try:
                s = status(r[sid])
                item[key] = {"status": s.get("status"), "error": s.get("errorMessage"), "url": s.get("publicUrl")}
            except Exception as e:
                item[key] = {"status": "lookup failed", "error": str(e)[:150]}
    out.append(item)
json.dump(out, open(os.path.join(ROOT, "data", "status-check.json"), "w"), indent=2)
print(json.dumps(out, indent=2))

# Facebook accounts and Pages connected in Blotato (to fill config.json facebook.account_id and page_id)
from publish import _call
fb = {}
try:
    fb["all_accounts"] = _call("GET", "/users/me/accounts")  # every platform, to see how Facebook shows up
    accts = _call("GET", "/users/me/accounts?platform=facebook")
    fb["accounts"] = accts
    for a in (accts.get("items") or accts.get("data") or (accts if isinstance(accts, list) else [])):
        aid = a.get("id")
        try:
            fb.setdefault("pages", {})[str(aid)] = _call("GET", f"/users/me/accounts/{aid}/subaccounts")
        except Exception as e:
            fb.setdefault("pages", {})[str(aid)] = {"error": str(e)[:200]}
except Exception as e:
    fb["error"] = str(e)[:200]
json.dump(fb, open(os.path.join(ROOT, "data", "facebook-accounts.json"), "w"), indent=2)
print(json.dumps(fb, indent=2))
