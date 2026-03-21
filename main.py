from flask import Flask, request, jsonify, send_from_directory
import requests
import time
import random
import os

app = Flask(__name__, static_folder='static')

# ─── Platform definitions ─────────────────────────────────────────────────
PLATFORMS = {
    "GitHub": {
        "url": "https://github.com/{}",
        "taken_code": 200,
        "available_code": 404,
    },
    "Reddit": {
        "url": "https://www.reddit.com/user/{}/about.json",
        "taken_code": 200,
        "available_code": 404,
    },
    "Twitch": {
        "url": "https://www.twitch.tv/{}",
        "taken_code": 200,
        "available_code": 404,
    },
    "TikTok": {
        "url": "https://www.tiktok.com/@{}",
        "taken_code": 200,
        "available_code": 404,
    },
    "Telegram": {
        "url": "https://t.me/{}",
        "taken_code": 200,
        "available_code": 404,
    },
    "Kick": {
        "url": "https://kick.com/{}",
        "taken_code": 200,
        "available_code": 404,
    },
}

# ─── Rotation pools ───────────────────────────────────────────────────────

USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    # Mobile
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.90 Mobile Safari/537.36",
]

ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "en-US,en;q=0.8,de;q=0.5",
    "en-US,en;q=0.9,fr;q=0.8",
    "en-CA,en;q=0.9",
    "en-AU,en;q=0.9",
]

REFERERS = [
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://duckduckgo.com/",
    "https://www.reddit.com/",
    "",  # no referer sometimes
]

# Session pool — rotate between multiple sessions to spread requests
SESSION_POOL = [requests.Session() for _ in range(5)]

request_counter = 0
session_index = 0

def get_headers():
    """Generate randomized headers that look like a real browser."""
    ua = random.choice(USER_AGENTS)
    headers = {
        "User-Agent": ua,
        "Accept-Language": random.choice(ACCEPT_LANGUAGES),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    }
    referer = random.choice(REFERERS)
    if referer:
        headers["Referer"] = referer
    # Add sec-ch-ua for Chrome agents
    if "Chrome" in ua:
        headers["sec-ch-ua"] = '"Chromium";v="122", "Not(A:Brand";v="24"'
        headers["sec-ch-ua-mobile"] = "?0"
        headers["sec-ch-ua-platform"] = '"Windows"'
    return headers

def get_session():
    """Rotate between session pool."""
    global session_index
    session = SESSION_POOL[session_index % len(SESSION_POOL)]
    session_index += 1
    return session

def human_delay(base_delay):
    """Add human-like random delay variation."""
    # Occasionally add a longer pause like a human would
    if random.random() < 0.1:  # 10% chance of longer pause
        extra = random.uniform(2, 5)
    else:
        extra = random.uniform(0, 0.8)
    time.sleep(base_delay + extra)

def check_username(username, platform_name):
    global request_counter
    platform = PLATFORMS[platform_name]
    url = platform["url"].format(username)
    session = get_session()
    headers = get_headers()

    try:
        r = session.get(url, headers=headers, timeout=8, allow_redirects=True)
        request_counter += 1

        if r.status_code == platform["taken_code"]:
            return "taken"
        elif r.status_code == platform["available_code"]:
            return "available"
        elif r.status_code == 429:
            # Rate limited — wait longer
            time.sleep(random.uniform(5, 10))
            return "rate_limited"
        elif r.status_code in [403, 401]:
            return "blocked"
        else:
            return "unknown"
    except requests.exceptions.Timeout:
        return "timeout"
    except requests.exceptions.ConnectionError:
        return "error"
    except Exception:
        return "error"

# ─── Routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/check", methods=["POST"])
def check():
    data = request.get_json()
    usernames = data.get("usernames", [])
    platforms = data.get("platforms", list(PLATFORMS.keys()))
    delay = float(data.get("delay", 2.0))

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

            # Warn frontend every 75 requests to rotate VPN
            if request_counter > 0 and request_counter % 75 == 0:
                row["vpn_reminder"] = True

            # Human-like delay between requests
            human_delay(delay)

        results.append(row)

    return jsonify({"results": results, "total_requests": request_counter})

@app.route("/platforms", methods=["GET"])
def get_platforms():
    return jsonify(list(PLATFORMS.keys()))

@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "status": "online",
        "total_requests": request_counter,
        "platforms": list(PLATFORMS.keys()),
        "sessions": len(SESSION_POOL)
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False) 
