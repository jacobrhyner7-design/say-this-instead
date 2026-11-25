"""Instagram engagement for @saythis.instead through Blotato.

  python engine/ig_engage.py setup-dm        create or update the "Comment SCRIPTS" auto-DM (idempotent)
  python engine/ig_engage.py draft           pull new audience comments, have Claude draft replies, save as pending
  python engine/ig_engage.py post --approve all|1,3,5   post the approved drafts (numbers from the summary)

Replies are never posted without approval. Drafts live in data/replies.json.
"""
import argparse, datetime as dt, json, os, re, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "engine"))
from publish import _call  # noqa: E402

CFG = json.load(open(os.path.join(ROOT, "config.json")))
IG = CFG["instagram"]
ENG = CFG.get("engagement", {})
DATA = os.path.join(ROOT, "data", "replies.json")
DM_NAME = "Comment PLAYBOOK: send the Playbook"
OLD_DM_NAMES = ("Comment SCRIPTS: send the Toolkit",)


def summary(text):
    print(text)
    p = os.environ.get("GITHUB_STEP_SUMMARY")
    if p:
        open(p, "a").write(text + "\n")


# ---------- auto-DM ----------
def setup_dm():
    kw = ENG.get("dm_keyword", "SCRIPTS")
    body = {
        "name": DM_NAME,
        "triggers": [
            {"type": "comment-received", "keywords": [kw], "postId": None},  # every post and reel on the account
            {"type": "message-received", "keywords": [kw]},
        ],
        "dmMessage": ENG["dm_message"],
        "buttons": [{"type": "url", "title": ENG.get("dm_button", "Get the Playbook"), "url": ENG["store_url"]}],
        "commentReply": {"variants": [{"text": t} for t in ENG["dm_public_replies"]]},
        "isActive": True,
    }
    existing = None
    cursor = None
    while True:
        q = "/dm-automations?limit=250" + (f"&cursor={urllib.parse.quote(cursor)}" if cursor else "")
        res = _call("GET", q)
        for it in res.get("items", []):
            if it.get("name") in (DM_NAME,) + OLD_DM_NAMES and str(it.get("accountId")) == str(IG["account_id"]):
                existing = it
        cursor = res.get("cursor")
        if not cursor:
            break
    if existing:
        flow = _call("PATCH", f"/dm-automations/{existing['id']}", {"patch": body})["flow"]
        summary(f"Updated auto-DM `{DM_NAME}` (id {flow['id']}, active: {flow.get('isActive')})")
    else:
        body.update(accountId=str(IG["account_id"]), platform="instagram", target={"targetType": "instagram"})
        flow = _call("POST", "/dm-automations", body)["flow"]
        summary(f"Created auto-DM `{DM_NAME}` (id {flow['id']}, active: {flow.get('isActive')})")


# ---------- reply drafts ----------
VOICE = """You reply to comments on Instagram posts for Say This Instead, a page that gives people the exact words
for hard work and money conversations: raises, salary, bosses, boundaries, clients, pricing and sales. Many followers
work remotely. You are confident, warm and brief, like a sharp friend who has been through it.

Rules:
- 1 or 2 short sentences, max 180 characters. Plain text, at most 1 emoji. No hashtags, no links.
- Respond to what they actually said. If they share a situation, validate it and add one tiny practical wording tip.
- Never give legal, tax, HR-dispute or investment advice; for those, suggest a qualified professional.
- Never use em dashes or en dashes. Don't mention you are an AI. Don't sell; the auto-DM handles the Playbook.
- If the comment is spam, rude, a bot, or needs a human (safety concern, complaint, very sensitive), reply exactly SKIP.

Return ONLY JSON: {"replies":[{"n":1,"reply":"..."}]}"""


def load():
    return json.load(open(DATA)) if os.path.exists(DATA) else {"last_check": None, "items": []}


def save(d):
    json.dump(d, open(DATA, "w"), indent=1, ensure_ascii=False)


def list_comments(since):
    out, cursor = [], None
    while True:
        q = {"accountId": str(IG["account_id"]), "limit": "100"}
        if since:
            q["since"] = since
        if cursor:
            q["cursor"] = cursor
        res = _call("GET", "/comments?" + urllib.parse.urlencode(q))
        out += res.get("items", [])
        cursor = res.get("cursor")
        if not cursor or len(out) > 400:
            return out


def already_answered(c):
    res = _call("GET", "/comments?" + urllib.parse.urlencode({"parentCommentId": c["id"], "limit": "50"}))
    return any(x.get("isAuthor") for x in res.get("items", []))


def claude(texts):
    ask = "Draft a reply for each comment:\n" + "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
    body = json.dumps({"model": CFG["claude_model"], "max_tokens": 2000, "system": VOICE,
                       "messages": [{"role": "user", "content": ask}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
        "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        text = json.load(r)["content"][0]["text"]
    reps = json.loads(re.search(r"\{.*\}", text, re.S).group(0))["replies"]
    fix = lambda s: re.sub(r"\s*[—–]\s*", ", ", s).strip()
    return {int(x["n"]): fix(x["reply"]) for x in reps}


def draft():
    d = load()
    kw = ENG.get("dm_keyword", "SCRIPTS").lower()
    since = d["last_check"] or (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    started = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    known = {i["comment_id"] for i in d["items"]}
    new = [c for c in list_comments(since)
           if not c.get("isAuthor") and not c.get("parentCommentId") and c.get("status") in (None, "posted")
           and c["id"] not in known and c.get("postId") and kw not in (c.get("text") or "").lower()]
    new = [c for c in new if not already_answered(c)][:40]
    if new:
        reps = claude([c["text"] for c in new])
        nxt = max([i["n"] for i in d["items"]] + [0]) + 1
        for k, c in enumerate(new):
            r = reps.get(k + 1, "SKIP")
            d["items"].append({"n": nxt, "comment_id": c["id"], "post_id": c["postId"], "comment": c["text"],
                               "reply": r, "status": "skipped" if r == "SKIP" else "pending",
                               "created": c.get("createdAt")})
            nxt += 1
    d["last_check"] = started
    save(d)
    pend = [i for i in d["items"] if i["status"] == "pending"]
    summary(f"## Instagram replies waiting for you: {len(pend)}\n")
    if pend:
        summary("| # | Comment | Draft reply |\n|---|---|---|")
        for i in pend:
            clean = lambda s: s.replace("|", "/").replace("\n", " ")
            summary(f"| {i['n']} | {clean(i['comment'])[:140]} | {clean(i['reply'])} |")
        summary("\nTo post them: Actions > **Instagram replies** > Run workflow > approve `all`, "
                "or list the numbers to post, like `1,3,4`. Anything not listed is skipped.")
    flagged = [i for i in d["items"] if i["status"] == "skipped" and i.get("created", "") >= since]
    if flagged:
        summary(f"\n{len(flagged)} comment(s) look like spam or need a personal reply; check them in Instagram.")


def post(approve):
    d = load()
    pend = [i for i in d["items"] if i["status"] == "pending"]
    ok = {i["n"] for i in pend} if approve.strip().lower() == "all" else \
        {int(x) for x in re.findall(r"\d+", approve)}
    posted = 0
    for i in pend:
        if i["n"] in ok:
            try:
                r = _call("POST", "/comments", {"postId": i["post_id"], "text": i["reply"],
                                                "parentCommentId": i["comment_id"]})
                i.update(status="sent", reply_id=r.get("id"))
                posted += 1
                time.sleep(2.5)  # stay well under 30 requests a minute
            except Exception as e:
                i.update(status="failed", error=str(e)[:150])
        else:
            i["status"] = "declined"
    save(d)
    summary(f"Posted {posted} repl{'y' if posted == 1 else 'ies'}; {len(pend) - posted} skipped.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["setup-dm", "draft", "post"])
    ap.add_argument("--approve", default="")
    a = ap.parse_args()
    {"setup-dm": setup_dm, "draft": draft, "post": lambda: post(a.approve)}[a.action]()
