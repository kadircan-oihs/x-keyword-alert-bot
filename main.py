import os, time, json, requests
from dotenv import load_dotenv
load_dotenv()

TW_BEARER     = os.getenv("TW_BEARER", "").strip()
TG_BOT_TOKEN  = os.getenv("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID    = os.getenv("TG_CHAT_ID", "").strip()
MIN_FOLLOWERS = int(os.getenv("MIN_FOLLOWERS", "5000").strip())
TWEET_LANG    = os.getenv("TWEET_LANG", "tr").strip()
SLEEP_SECONDS = int(os.getenv("SLEEP_SECONDS", "15").strip())

KEYWORDS = [
    "kanada lise",
    "yurtdışında üniversite",
    "yurt dışında üniversite",
    "OSSD",
    "Ontario Secondary School Diploma",
    "Canada high school",
    "study in Canada"
]
quoted = [f'"{k}"' if " " in k else k for k in KEYWORDS]
QUERY = "(" + " OR ".join(quoted) + f") lang:{TWEET_LANG} -is:retweet -is:reply"

BASE = "https://api.x.com/2"

def tg_send(text):
    if not TG_BOT_TOKEN or not TG_CHAT_ID: return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT_ID, "text": text, "disable_web_page_preview": True},
            timeout=10
        )
    except Exception as e:
        print("TG error:", e)

def search_once(since_id=None):
    headers = {"Authorization": f"Bearer {TW_BEARER}"}
    params = {
        "query": QUERY,
        "max_results": 10,  # daha az sonuç = daha az kota
        "tweet.fields": "created_at,lang,author_id,public_metrics",
        "expansions": "author_id",
        "user.fields": "username,verified,public_metrics,name"
    }
    if since_id:
        params["since_id"] = since_id
    r = requests.get(f"{BASE}/tweets/search/recent", headers=headers, params=params, timeout=15)
    if r.status_code == 403:
        raise SystemExit("403 Forbidden: Mevcut dev paketinde 'recent search' kapalı olabilir.")
    r.raise_for_status()
    return r.json()

def run_polling():
    print("Polling started. Query:", QUERY)
    since_id = None
    backoff = SLEEP_SECONDS

    # Bootstrap: en yeni ID'yi referans al
    try:
        data = search_once()
        since_id = data.get("meta", {}).get("newest_id", None)
        print("Bootstrap newest_id:", since_id)
    except Exception as e:
        print("Bootstrap error:", e)

    while True:
        try:
            data = search_once(since_id)
            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
            tweets = sorted(data.get("data", []), key=lambda t: t["id"])

            for t in tweets:
                author = users.get(t["author_id"], {})
                followers = author.get("public_metrics", {}).get("followers_count", 0)
                if followers < MIN_FOLLOWERS: 
                    since_id = t["id"]
                    continue
                username = author.get("username", "user")
                tid = t["id"]
                link = f"https://twitter.com/{username}/status/{tid}"
                msg = (
                    "🚨 Yeni tweet yakalandı\n"
                    f"👤 @{username} ({followers} takipçi)\n"
                    f"🧵 {link}\n\n"
                    "⚠️ Okul hesabından cevap ver.\n"
                    "✍️ Şablon: OSSD ile Kanada’da lise/üniv. kabulleri hakkında bilgi isterseniz DM yazın. "
                    "Ontario resmî diploması (OSSD) sunuyoruz."
                )
                tg_send(msg)
                print("Sent:", link)
                since_id = tid

            # Başarılı tur: backoff'u normale çek
            time.sleep(SLEEP_SECONDS)
            backoff = SLEEP_SECONDS

        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                print("Rate limit (429). Backing off:", backoff, "s")
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)  # max 5 dk
            else:
                print("HTTP error:", e)
                time.sleep(backoff)
        except Exception as e:
            print("Poll error:", e)
            time.sleep(backoff)

def require_env():
    missing = [k for k, v in {
        "TW_BEARER": TW_BEARER,
        "TG_BOT_TOKEN": TG_BOT_TOKEN,
        "TG_CHAT_ID": TG_CHAT_ID
    }.items() if not v]
    if missing:
        raise SystemExit(f"Missing env vars: {', '.join(missing)}")

if __name__ == "__main__":
    require_env()
    run_polling()
