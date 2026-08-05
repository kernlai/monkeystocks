"""Post the day's queue to X. SAFE BY DEFAULT: dry-run unless POST_LIVE=1.

Reads cards/latest/posts.json, posts only fact-check-verified items, one per
run (the next unposted one), and records it in cards/posted_log.json so nothing
is ever posted twice. Requires four X OAuth1.0a creds in env (as GitHub secrets):
  X_API_KEY  X_API_SECRET  X_ACCESS_TOKEN  X_ACCESS_SECRET
Set POST_LIVE=1 to actually publish; otherwise it prints what it *would* post.
"""
import json, os, pathlib, sys

HERE = pathlib.Path(__file__).parent
OUT = HERE.parent / "cards" / "latest"
LOG = HERE.parent / "cards" / "posted_log.json"

data = json.loads((OUT/"posts.json").read_text())
log = json.loads(LOG.read_text()) if LOG.exists() else {"posted": []}
posted_keys = {p["key"] for p in log["posted"]}

# pick the first verified, not-yet-posted item for today
queue = [p for p in data["posts"] if p["verified"]]
todo = None
for i, p in enumerate(queue):
    key = f"{data['date']}#{i}"
    if key not in posted_keys:
        todo = (key, p); break

if not todo:
    print("nothing new to post today"); sys.exit(0)

key, p = todo
live = os.environ.get("POST_LIVE") == "1"
img = OUT / p["image"] if p["image"] else None
print(f"[{'LIVE' if live else 'DRY-RUN'}] {key}\n{'—'*40}\n{p['copy']}\n{'—'*40}")
print(f"image: {p['image'] or 'none'}")

if not live:
    print("\nDRY-RUN: set POST_LIVE=1 (and provide X creds) to publish."); sys.exit(0)

import tweepy
client = tweepy.Client(consumer_key=os.environ["X_API_KEY"],
                       consumer_secret=os.environ["X_API_SECRET"],
                       access_token=os.environ["X_ACCESS_TOKEN"],
                       access_token_secret=os.environ["X_ACCESS_SECRET"])
media_ids = None
if img and img.exists():
    auth = tweepy.OAuth1UserHandler(os.environ["X_API_KEY"], os.environ["X_API_SECRET"],
                                    os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_SECRET"])
    api = tweepy.API(auth)
    media_ids = [api.media_upload(str(img)).media_id]
resp = client.create_tweet(text=p["copy"], media_ids=media_ids)
tid = resp.data["id"]
print(f"posted: https://x.com/i/web/status/{tid}")
log["posted"].append({"key": key, "id": str(tid), "copy": p["copy"][:80]})
LOG.write_text(json.dumps(log, indent=2))
