from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import time
import random
import os

app = Flask(__name__, static_folder='static')
CORS(app)

PLATFORMS = {
    "GitHub":   {"url": "https://github.com/{}", "taken_code": 200, "available_code": 404},
    "Reddit":   {"url": "https://www.reddit.com/user/{}/about.json", "taken_code": 200, "available_code": 404},
    "Twitch":   {"url": "https://www.twitch.tv/{}", "taken_code": 200, "available_code": 404},
    "TikTok":   {"url": "https://www.tiktok.com/@{}", "taken_code": 200, "available_code": 404},
    "Telegram": {"url": "https://t.me/{}", "taken_code": 200, "available_code": 404},
    "Kick":     {"url": "https://kick.com/{}", "taken_code": 200, "available_code": 404},
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/605.1.15 Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 Version/17.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/122.0.6261.90 Mobile Safari/537.36",
]

SESSION_POOL = [requests.Session() for _ in range(6)]
request_counter = 0
session_index = 0

def get_headers():
    ua = random.choice(USER_AGENTS)
    return {
        "User-Agent": ua,
        "Accept-Language": random.choice(["en-US,en;q=0.9", "en-GB,en;q=0.9", "en-CA,en;q=0.9"]),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
    }

def get_session():
    global session_index
    s = SESSION_POOL[session_index % len(SESSION_POOL)]
    session_index += 1
    return s

def check_username(username, platform_name):
    global request_counter
    platform = PLATFORMS[platform_name]
    url = platform["url"].format(username)
    try:
        r = get_session().get(url, headers=get_headers(), timeout=4, allow_redirects=True)
        request_counter += 1
        if r.status_code == platform["taken_code"]:
            return "taken"
        elif r.status_code == platform["available_code"]:
            return "available"
        elif r.status_code == 429:
            time.sleep(random.uniform(4, 8))
            return "rate_limited"
        elif r.status_code in [403, 401]:
            return "blocked"
        else:
            return "unknown"
    except:
        return "error"

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/check", methods=["POST"])
def check():
    data = request.get_json()
    usernames = data.get("usernames", [])
    platforms = data.get("platforms", list(PLATFORMS.keys()))
    delay = float(data.get("delay", 0.5))
    results = []
    for username in usernames:
        username = username.strip()
        if not username:
            continue
        row = {"username": username, "platforms": {}}
        for platform in platforms:
            if platform not in PLATFORMS:
                continue
            status = check_username(username, platform)
            row["platforms"][platform] = status
            if request_counter > 0 and request_counter % 75 == 0:
                row["vpn_reminder"] = True
            time.sleep(delay + random.uniform(0, 0.3))
        results.append(row)
    return jsonify({"results": results, "total_requests": request_counter})

@app.route("/platforms", methods=["GET"])
def get_platforms():
    return jsonify(list(PLATFORMS.keys()))

@app.route("/status", methods=["GET"])
def status():
    return jsonify({"status": "online", "total_requests": request_counter, "platforms": list(PLATFORMS.keys())})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False) 
