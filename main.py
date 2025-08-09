import os, json, time, requests
from dotenv import load_dotenv

load_dotenv()

# === ENV (tek satır olacak şekilde doldur) ===
TW_BEARER     = os.getenv("TW_BEARER", "").strip()
TG_BOT_TOKEN  = os.getenv("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID    = os.getenv("TG_CHAT_ID", "").strip()
MIN_FOLLOWERS = int(os.getenv("MIN_FOLLOWERS", "5000").strip())   # testte 0 yap
TWEET_LANG    = os.getenv("TWEET_LANG", "tr").strip()

# === Anahtar kelimeler ===
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
RULE_VALUE = "(" + " OR ".join(quoted) + f") lang:{TWEET_LANG} -is:retweet -is:reply"

BASE = "https://api.twitter.com/2"   # <- Buraya dikkat (api.twitter.com)

# === Yardımcılar ===
def require_env():
    missing = [k for k, v in {
        "TW_BEARER": TW_BEARER,
        "TG_BOT_TOKEN": TG_BOT_TOKEN,
        "TG_CHAT_ID": TG_CHAT_ID
    }.items() if not v]
    if missing:
        raise SystemExit(f"Missing env vars: {', '.join(missing)}")

def tg_send(text: str):
    if not TG_BOT_TOKEN or not TG_CHAT_ID: return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT_ID, "text": text, "disable_web_page_preview": True},
            timeout=10
        )
    except Exception as e:
        print("TG error:", e)

# === Rules yönetimi ===
def get_headers():
    return {"Authorization": f"Bearer {TW_BEARER}"}

def clear_rules():
    r = requests.get(f"{BASE}/tweets/search/stream/rules", headers=get_headers(), timeout=15)
    r.raise_for_status()
    data = r.json()
    if "data" in data:
        ids = [d["id"] for d in data["data"]]
        if ids:
            requests.post(f"{BASE}/tweets/search/stream/rules",
                          headers=get_headers(),
                          json={"delete": {"ids": ids}},
                          timeout=15).raise_for_status()

def add_rule():
    payload = {"add": [{"value": RULE_VALUE, "tag": "edu-watch"}]}
    r = requests.post(f"{BASE}/tweets/search/stream/rules",
                      headers=get_headers(), json=payload, timeout=15)
    if r.status_code == 403:
        # Plan/izin sorunu veya auth şekli hatalı
        raise SystemExit(
            "403 Forbidden (rules): Planın streaming'i desteklemiyor olabilir veya Bearer Token geçersiz.\n"
            "-> X Developer portalda planını yükselt / doğru projedeki Bearer Token'ı kullan.\n"
            "-> TW_BEARER tek satır olduğundan emin ol."
        )
    r.raise_for_status()
    print("Rules set:", r.json())

# === Stream ===
def run_stream():
    params = {
        "tweet.fields": "created_at,lang,author_id,public_metrics",
        "expansions": "author_id",
        "user.fields": "username,verified,public_metrics,name"
    }
    backoff = 1
    while True:
        try:
            with requests.get(f"{BASE}/tweets/search/stream",
                              headers=get_headers(), params=params,
                              stream=True, timeout=0) as r:
                if r.status_code == 403:
                    raise SystemExit(
                        "403 Forbidden (stream): Planın streaming'e izin vermiyor veya auth hatalı."
                    )
                r.raise_for_status()
                print("Connected to stream. Listening…")
                backoff = 1
                for raw in r.iter_lines():
                    if not raw:
                        continue
                    try:
                        obj = json.loads(raw.decode("utf-8"))
                        tweet = obj.get("data", {})
                        users = {u["id"]: u for u in obj.get("includes", {}).get("users", [])}
                        author = users.get(tweet.get("author_id"), {})
                        followers = author.get("public_metrics", {}).get("followers_count", 0)
                        if followers < MIN_FOLLOWERS:
                            continue
                        username = author.get("username", "user")
                        tid = tweet.get("id")
                        link = f"https://twitter.com/{username}/status/{tid}"
                        msg = (
                            "🚨 Yeni tweet yakalandı\n"
                            f"👤 @{username} ({followers} takipçi)\n"
                            f"🧵 {link}\n\n"
                            "⚠️ Okul hesabından cevap ver.\n"
                            "✍️ Şablon: OSSD ile Kanada’da lise/üniv. kabulleri için DM atabilirsiniz. "
                            "Ontario resmî diploması (OSSD) sunuyoruz."
                        )
                        tg_send(msg)
                        print("Sent:", link)
                    except Exception as e:
                        print("Parse error:", e)
        except requests.exceptions.ChunkedEncodingError:
            # Bağlantı koparsa yeniden bağlan
            print("Stream dropped. Reconnecting…")
        except requests.HTTPError as e:
            print("HTTP error:", e)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
        except Exception as e:
            print("Stream error:", e)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)

if __name__ == "__main__":
    require_env()
    try:
        clear_rules()
        add_rule()
    except requests.exceptions.InvalidHeader:
        raise SystemExit("TW_BEARER formatı hatalı: tek satır olarak yapıştır.")
    run_stream()
