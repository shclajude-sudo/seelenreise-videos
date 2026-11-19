import json, os, sys, time, urllib.request, urllib.parse, urllib.error

API = "https://graph.facebook.com/v21.0"
REPO_RAW = "https://raw.githubusercontent.com/shclajude-sudo/seelenreise-videos/main/"
TOKEN = os.environ["META_PAGE_TOKEN"]
PAGE_ID = os.environ.get("PAGE_ID", "1409838638884415")
IG_ID = os.environ.get("IG_USER_ID", "").strip()
COUNT = int(os.environ.get("COUNT", "1"))
PLATFORMS = [p for p in os.environ.get("PLATFORMS", "fb,ig").split(",") if p]


def call(method, url, data=None, headers=None):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code} {e.read().decode()[:400]}")


def post_fb(v):
    url = REPO_RAW + v["file"]
    s = call("POST", f"{API}/{PAGE_ID}/video_reels", {"upload_phase": "start", "access_token": TOKEN})
    vid = s["video_id"]
    r = call("POST", s["upload_url"], None, {"Authorization": "OAuth " + TOKEN, "file_url": url})
    if not r.get("success", True):
        raise RuntimeError(f"upload failed {r}")
    for _ in range(40):
        st = call("GET", f"{API}/{vid}?fields=status&access_token={TOKEN}")
        phase = st.get("status", {}).get("video_status")
        if phase in ("ready", "upload_complete", "processing"):
            if phase != "processing":
                break
        if phase == "error":
            raise RuntimeError(f"processing error {st}")
        time.sleep(15)
    f = call("POST", f"{API}/{PAGE_ID}/video_reels", {
        "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
        "description": v["fb"], "access_token": TOKEN})
    return f


def post_ig(v):
    c = call("POST", f"{API}/{IG_ID}/media", {
        "media_type": "REELS", "video_url": REPO_RAW + v["file"],
        "caption": v["ig"], "share_to_feed": "true", "access_token": TOKEN})
    cid = c["id"]
    for _ in range(40):
        st = call("GET", f"{API}/{cid}?fields=status_code&access_token={TOKEN}")
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"ig processing error {st}")
        time.sleep(15)
    return call("POST", f"{API}/{IG_ID}/media_publish", {"creation_id": cid, "access_token": TOKEN})


vids = json.load(open("captions.json", encoding="utf8"))
state = json.load(open("state.json")) if os.path.exists("state.json") else {"fb": [], "ig": []}
fails = 0
for plat in PLATFORMS:
    if plat == "ig" and not IG_ID:
        print("ig: kein IG_USER_ID, uebersprungen")
        continue
    done = state.setdefault(plat, [])
    todo = [v for v in vids if v["n"] not in done][:COUNT]
    for v in todo:
        try:
            res = post_fb(v) if plat == "fb" else post_ig(v)
            print(plat, "OK Video", v["n"], res)
            done.append(v["n"])
        except Exception as e:
            print(plat, "FEHLER Video", v["n"], e)
            fails += 1
            break
        finally:
            json.dump(state, open("state.json", "w"), indent=1)
sys.exit(1 if fails else 0)
