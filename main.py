import os, time, json, requests
from dotenv import load_dotenv

load_dotenv()

TW_BEARER     = os.getenv("TW_BEARER", "").strip()
TG_BOT_TOKEN  = os.getenv("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID    = os.getenv("TG_CHAT_ID", "").strip()
MIN_FOLLOWERS = int(os.getenv("MIN_FOLLOWERS", "5000").strip())  # Testte 0 yap
LANG          = os.getenv("LANG", "tr").strip()

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
QUERY = "(" + " OR ".join(quoted) + f") lang:{LANG} -is:retweet -is:reply"

BASE = "https://api.x.com/2"

def tg_send(text: str):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("Telegram env eksik; mesaj gönderilmedi.")
        return
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
        "max_results": 50,  # 10-100
        "tweet.fields": "created_at,lang,author_id,public_metrics",
        "expansions": "author_id",
        "user.fields": "username,verified,public_metrics,name"
    }
    if since_id:
        params["since_id"] = since_id

    r = requests.get(f"{BASE}/tweets/search/recent", headers=headers, params=params, timeout=15)
    if r.status_code == 403:
        raise SystemExit("403 Forbidden: Geliştirici paketinde 'recent search' kapalı olabilir.")
    r.raise_for_status()
    return r.json()

def run_polling():
    print("Polling started. Query:", QUERY)
    since_id = None
    # start bootstrap: altta kalmış en yeniyi referans al ki eski flood düşmesin
    try:
        data = search_once()
        if "meta" in data and "newest_id" in data["meta"]:
            since_id = data["meta"]["newest_id"]
            print("Bootstrap newest_id:", since_id)
    except Exception as e:
        print("Bootstrap error:", e)

    while True:
        try:
            data = search_once(since_id)
            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
            tweets = data.get("data", [])
            # En eskiden en yeniye sırala ki Telegram bildirimleri doğru sırada gitsin
            tweets = sorted(tweets, key=lambda t: t["id"])
            for t in tweets:
                author = users.get(t["author_id"], {})
                followers = author.get("public_metrics", {}).get("followers_count", 0)
                if followers < MIN_FOLLOWERS:
                    continue
                username = author.get("username", "user")
                tid = t["id"]
                link = f"https://twitter.com/{username}/status/{tid}"
                msg = (
                    "🚨 Yeni tweet yakalandı\n"
                    f"👤 @{username} ({followers} takipçi)\n"
                    f"🧵 {link}\n\n"
                    "⚠️ Okul hesabından cevap ver.\n"
                    "✍️ Şablon: OSSD ile Kanada’da lise/üniversite kabulleri hakkında bilgi isterseniz DM yazın. "
                    "Ontario resmî diploması (OSSD) sunuyoruz."
                )
                tg_send(msg)
                print("Sent:", link)
                since_id = tid  # en yeni id'yi ilerlet
        except Exception as e:
            print("Poll error:", e)

        time.sleep(7)  # 5–10 sn arası idealdir (limitine göre ayarla)

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
