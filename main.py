import os, time, requests

# ============== ENV OKUMA (hatalara dayanıklı) ==============
def clean_env(key, default=None):
    val = os.getenv(key, default)
    if val is None:
        return default
    # Baştaki/sondaki boşlukları, yanlışlıkla konan '=' işaretini ve satır sonlarını temizle
    return str(val).strip().lstrip("=").strip()

BEARER_TOKEN = clean_env("BEARER_TOKEN")  # X API v2 Bearer Token
QUERY = clean_env(
    "QUERY",
    '("OSSD" OR "Ontario Secondary School Diploma" OR "kanada lise" OR "yurtdışında üniversite") lang:tr'
)
SLEEP_SECONDS = int(clean_env("SLEEP_SECONDS", "900"))  # Free planda önerilen: 900 = 15dk
MIN_FOLLOWERS = int(clean_env("MIN_FOLLOWERS", "0"))    # Testte 0, sonra 5000 yap
TG_BOT_TOKEN  = clean_env("TG_BOT_TOKEN", "")
TG_CHAT_ID    = clean_env("TG_CHAT_ID", "")             # Örn: 7124529797

# ============== SABİTLER ==============
HEADERS = {"Authorization": f"Bearer {BEARER_TOKEN}"}
BASE = "https://api.twitter.com/2"
SEARCH_URL = f"{BASE}/tweets/search/recent"

# ============== TELEGRAM ==============
def tg_send(text: str):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("ℹ️ Telegram ayarlı değil (TG_BOT_TOKEN/TG_CHAT_ID yok). Sadece log basacağım.")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT_ID, "text": text, "disable_web_page_preview": True},
            timeout=10,
        )
    except Exception as e:
        print("TG error:", e)

# ============== TWITTER ARAMA ==============
def search_once(since_id=None, max_results=10):
    """
    Free/Basic planda rate limit düşük. max_results düşük tut (10).
    since_id verirsen sadece yeni tweetleri çeker.
    """
    params = {
        "query": QUERY,  # Örn: ("OSSD" OR "kanada lise") lang:tr -is:retweet -is:reply
        "max_results": max_results,
        "tweet.fields": "created_at,lang,author_id,public_metrics",
        "expansions": "author_id",
        "user.fields": "username,verified,public_metrics,name",
    }
    if since_id:
        params["since_id"] = since_id

    r = requests.get(SEARCH_URL, headers=HEADERS, params=params, timeout=20)
    if r.status_code == 429:
        # Rate limit: geri çekil
        print("⚠️ 429 Too Many Requests — 15 dk bekliyorum.")
        time.sleep(900)
        return None
    if r.status_code == 403:
        print("❌ 403 Forbidden — Plan/izin kısıtı. (Streaming yok, polling de kısıtlı olabilir.)")
        return None
    if r.status_code >= 400:
        print(f"❌ API error {r.status_code}: {r.text}")
        return None

    return r.json()

# ============== POLLING DÖNGÜSÜ ==============
def run():
    if not BEARER_TOKEN:
        raise SystemExit("❌ BEARER_TOKEN env eksik. Developer portalden alıp Railway Variables'a ekleyin.")

    print("✅ Bot başladı.")
    print("🔎 Query:", QUERY)
    print(f"⏱️ Tarama sıklığı: {SLEEP_SECONDS} sn")
    print(f"👥 Min. takipçi filtresi: {MIN_FOLLOWERS}")

    since_id = None

    # İlk çalıştırmada flood olmasın: en yeni tweet ID'sini referans al
    boot = search_once(max_results=10)
    if boot and boot.get("meta", {}).get("newest_id"):
        since_id = boot["meta"]["newest_id"]
        print("🔧 Bootstrap newest_id:", since_id)

    backoff = SLEEP_SECONDS  # dinamik backoff
    while True:
        try:
            data = search_once(since_id=since_id, max_results=10)
            if not data:
                print(f"😴 Uyku: {SLEEP_SECONDS} sn")
                time.sleep(SLEEP_SECONDS)
                continue

            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
            tweets = sorted(data.get("data", []), key=lambda t: t["id"]) if data.get("data") else []

            sent_count = 0
            for t in tweets:
                author = users.get(t["author_id"], {})
                followers = author.get("public_metrics", {}).get("followers_count", 0)
                tid = t["id"]
                since_id = tid  # bir sonraki turda bunu referans al

                if followers < MIN_FOLLOWERS:
                    continue

                username = author.get("username", "user")
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
                sent_count += 1

            print(f"✅ Tur bitti. Gönderilen bildirim: {sent_count}.")
            print(f"😴 Uyku: {SLEEP_SECONDS} sn")
            time.sleep(SLEEP_SECONDS)
            backoff = SLEEP_SECONDS  # başarılı tur → backoff reset

        except requests.HTTPError as e:
            print("HTTP error:", e)
            print(f"⏳ Backoff: {backoff} sn")
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)
        except Exception as e:
            print("❌ Poll error:", e)
            print(f"⏳ Backoff: {backoff} sn")
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)

if __name__ == "__main__":
    run()
