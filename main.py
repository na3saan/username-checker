from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import time
import random
import os
import re

app = Flask(__name__, static_folder='static')
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization"]}})

PLATFORMS = {
    "GitHub": {
        "url": "https://api.github.com/users/{}",
        "taken_code": 200,
        "available_code": 404,
        "headers_override": {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "username-availability-checker/1.0",
        },
        "timeout": 6,
    },
    "Reddit": {
        "url": "https://www.reddit.com/user/{}/about.json",
        "taken_code": 200,
        "available_code": 404,
        "timeout": 6,
    },
    "Twitch": {
        "url": "https://www.twitch.tv/{}",
        "taken_code": 200,
        "available_code": 404,
        "timeout": 5,
    },
    "TikTok": {
        "url": "https://www.tiktok.com/@{}",
        "taken_code": 200,
        "available_code": 404,
        "timeout": 7,
    },
    "Telegram": {
        "url": "https://t.me/{}",
        "taken_code": 200,
        "available_code": 404,
        "timeout": 5,
    },
    "Kick": {
        "url": "https://kick.com/api/v1/channels/{}",
        "taken_code": 200,
        "available_code": 404,
        "timeout": 5,
    },
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.90 Mobile Safari/537.36",
]

ACCEPT_LANGS = ["en-US,en;q=0.9", "en-GB,en;q=0.9", "en-CA,en;q=0.9", "en-AU,en;q=0.9"]

# FIX 4: Recreate sessions periodically to avoid sticky ban cookies
def make_sessions(n=8):
    return [requests.Session() for _ in range(n)]

SESSION_POOL = make_sessions()
request_counter = 0
session_index = 0
session_request_counts = [0] * 8  # track per-session usage

# FIX 3: Only allow safe username characters
VALID_USERNAME_RE = re.compile(r'^[a-zA-Z0-9._\-]{1,50}$')

def get_browser_headers():
    ua = random.choice(USER_AGENTS)
    h = {
        "User-Agent": ua,
        "Accept-Language": random.choice(ACCEPT_LANGS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
        "DNT": "1",
    }
    if "Chrome" in ua:
        h["sec-ch-ua"] = '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"'
        h["sec-ch-ua-mobile"] = "?1" if "Mobile" in ua else "?0"
        h["sec-ch-ua-platform"] = '"Android"' if "Android" in ua else '"Windows"'
    return h

def get_session():
    global session_index, SESSION_POOL, session_request_counts
    idx = session_index % len(SESSION_POOL)

    # FIX 4: Reset a session after 50 requests to clear any ban cookies
    if session_request_counts[idx] >= 50:
        SESSION_POOL[idx] = requests.Session()
        session_request_counts[idx] = 0

    s = SESSION_POOL[idx]
    session_request_counts[idx] += 1
    session_index += 1
    return s

def check_username(username, platform_name):
    global request_counter

    # FIX 3: Validate username before making request
    if not VALID_USERNAME_RE.match(username):
        return {"status": "error", "code": "E006"}

    if platform_name not in PLATFORMS:
        return {"status": "error", "code": "E004"}

    platform = PLATFORMS[platform_name]
    url = platform["url"].format(username)
    headers = platform.get("headers_override") or get_browser_headers()
    timeout = platform.get("timeout", 5)
    session = get_session()

    try:
        r = session.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        request_counter += 1
        code = str(r.status_code)

        if r.status_code == platform["taken_code"]:
            return {"status": "taken", "code": code}
        elif r.status_code == platform["available_code"]:
            return {"status": "available", "code": code}
        elif r.status_code == 429:
            # Rate limited — wait and retry once with fresh session
            time.sleep(random.uniform(5, 10))
            fresh = requests.Session()
            try:
                r2 = fresh.get(url, headers=get_browser_headers(), timeout=timeout, allow_redirects=True)
                request_counter += 1
                if r2.status_code == platform["taken_code"]:
                    return {"status": "taken", "code": str(r2.status_code)}
                elif r2.status_code == platform["available_code"]:
                    return {"status": "available", "code": str(r2.status_code)}
            except Exception:
                pass
            return {"status": "rate_limited", "code": "E429"}
        elif r.status_code == 403:
            return {"status": "blocked", "code": "E403"}
        elif r.status_code == 401:
            return {"status": "blocked", "code": "E401"}
        elif r.status_code == 400:
            return {"status": "unknown", "code": "E400"}
        elif r.status_code == 500:
            return {"status": "error", "code": "E500"}
        elif r.status_code == 503:
            return {"status": "error", "code": "E503"}
        else:
            return {"status": "unknown", "code": "E" + code}

    except requests.exceptions.Timeout:
        return {"status": "timeout", "code": "E000"}
    except requests.exceptions.ConnectionError:
        return {"status": "error", "code": "E001"}
    except requests.exceptions.TooManyRedirects:
        return {"status": "error", "code": "E005"}
    except Exception:
        return {"status": "error", "code": "E003"}

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/check", methods=["POST"])
def check():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON", "code": "E400"}), 400

    usernames = data.get("usernames", [])
    platforms = [p for p in data.get("platforms", list(PLATFORMS.keys())) if p in PLATFORMS]
    delay = max(0.1, min(float(data.get("delay", 0.5)), 10.0))

    if not usernames:
        return jsonify({"results": [], "total_requests": request_counter})

    if len(usernames) > 500:
        return jsonify({"error": "Max 500 usernames per request", "code": "E007"}), 400

    results = []
    for username in usernames:
        username = username.strip()
        if not username:
            continue
        row = {"username": username, "platforms": {}}
        for platform in platforms:
            result = check_username(username, platform)
            row["platforms"][platform] = result
            if request_counter > 0 and request_counter % 75 == 0:
                row["vpn_reminder"] = True
            time.sleep(delay + random.uniform(0.05, 0.25))
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
        "sessions": len(SESSION_POOL),
        "version": "2.1"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
