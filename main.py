import os, json, time, requests
from dotenv import load_dotenv
load_dotenv()

TW_BEARER = os.getenv("TW_BEARER")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
MIN_FOLLOWERS = int(os.getenv("MIN_FOLLOWERS", "5000"))
LANG = os.getenv("LANG", "tr")

KEYWORDS = [
    "kanada lise",
    "yurtdışında üniversite",
    "yurt dışında üniversite",
    "OSSD",
    "Ontario Secondary School Diploma",
    "Canada high school",
    "study in Canada"
]
RULE_VALUE = "(" + " OR ".join([f'"{k}"' if " " in k else k for k in KEYWORDS]) + f") lang:{LANG} -is:retweet -is:reply"

def tg_send(text):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TG_CHAT_ID, "text": text, "disable_web_page_preview": True}, timeout=10)
    except Exception as e:
        print("TG error:", e)

def set_rules():
    headers = {"Authorization": f"Bearer {TW_BEARER}"}
    r = requests.get("https://api.x.com/2/tweets/search/stream/rules", headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()
    if "data" in data:
        ids = [r["id"] for r in data["data"]]
        if ids:
            requests.post("https://api.x.com/2/tweets/search/stream/rules",
                          headers=headers, json={"delete": {"ids": ids}}, timeout=15)
    payload = {"add": [{"value": RULE_VALUE, "tag": "edu-watch"}]}
    r = requests.post("https://api.x.com/2/tweets/search/stream/rules",
                      headers=headers, json=payload, timeout=15)
    r.raise_for_status()
    print("Rules set:", r.json())

def stream():
    headers = {"Authorization": f"Bearer {TW_BEARER}"}
    params = {
        "tweet.fields": "created_at,lang,author_id,public_metrics,entities",
        "expansions": "author_id",
        "user.fields": "username,verified,public_metrics,name"
    }
    with requests.get("https://api.x.com/2/tweets/search/stream",
                      headers=headers, params=params, stream=True, timeout=0) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line: continue
            try:
                obj = json.loads(line.decode("utf-8"))
                tweet = obj.get("data", {})
                users = {u["id"]: u for u in obj.get("includes", {}).get("users", [])}
                author = users.get(tweet.get("author_id"), {})
                followers = author.get("public_metrics", {}).get("followers_count", 0)
                if followers < MIN_FOLLOWERS: continue
                username = author.get("username", "user")
                tid = tweet.get("id")
                link = f"https://twitter.com/{username}/status/{tid}"
                msg = ("🚨 Yeni tweet yakalandı\n"
                       f"👤 @{username} ({followers} takipçi)\n"
                       f"🧵 {link}\n\n"
                       "⚠️ Okul hesabından cevap ver.\n"
                       "✍️ Şablon: OSSD ile Kanada’da lise/üniversite kabulleri hakkında bilgi isterseniz DM yazın. "
                       "Ontario resmî diploması (OSSD) sunuyoruz.")
                tg_send(msg)
                print("Sent:", link)
            except Exception as e:
                print("Parse error:", e)

if __name__ == "__main__":
    missing = [k for k in ["TW_BEARER","TG_BOT_TOKEN","TG_CHAT_ID"] if not os.getenv(k)]
    if missing: raise SystemExit(f"Missing env vars: {', '.join(missing)}")
    set_rules()
    backoff = 1
    while True:
        try: stream()
        except Exception as e:
            print("Stream error, reconnecting...", e)
            time.sleep(min(backoff, 60))
            backoff = min(backoff * 2, 60)
