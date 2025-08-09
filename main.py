import os
import time
import requests

# ---------------- CONFIG ----------------
BEARER_TOKEN = os.getenv("BEARER_TOKEN")  # Railway Variables'da tanımlı
QUERY = os.getenv("QUERY", '("OSSD" OR "Ontario Secondary School Diploma" OR "kanada lise" OR "yurtdışında üniversite") lang:tr')
SLEEP_SECONDS = int(os.getenv("SLEEP_SECONDS", "900"))  # 15 dk default
MIN_FOLLOWERS = int(os.getenv("MIN_FOLLOWERS", "0"))

# -----------------------------------------

HEADERS = {"Authorization": f"Bearer {BEARER_TOKEN}"}
SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"

def search_tweets():
    params = {
        "query": QUERY,
        "max_results": 50,
        "tweet.fields": "created_at,lang,author_id,public_metrics",
        "expansions": "author_id",
        "user.fields": "username,verified,public_metrics,name"
    }
    r = requests.get(SEARCH_URL, headers=HEADERS, params=params, timeout=15)
    
    if r.status_code == 429:
        print("⚠️ Rate limit aşıldı! 5 dakika bekleniyor...")
        time.sleep(300)
        return []
    r.raise_for_status()
    
    data = r.json()
    tweets = []
    if "data" in data and "includes" in data:
        users = {u["id"]: u for u in data["includes"]["users"]}
        for t in data["data"]:
            user = users.get(t["author_id"], {})
            followers = user.get("public_metrics", {}).get("followers_count", 0)
            if followers >= MIN_FOLLOWERS:
                tweets.append({
                    "text": t["text"],
                    "username": user.get("username"),
                    "followers": followers,
                    "created_at": t["created_at"]
                })
    return tweets

if __name__ == "__main__":
    if not BEARER_TOKEN:
        print("❌ BEARER_TOKEN env değişkeni tanımlı değil!")
        exit(1)

    print("✅ Bot başladı. Her", SLEEP_SECONDS, "saniyede bir kontrol ediliyor.")
    while True:
        try:
            results = search_tweets()
            for tw in results:
                print(f"@{tw['username']} ({tw['followers']} takipçi) - {tw['created_at']}\n{tw['text']}\n---")
        except Exception as e:
            print("❌ Hata:", e)
        
        time.sleep(SLEEP_SECONDS)
