from flask import Flask, request, jsonify, send_from_directory
import requests
import time
import random
import os

app = Flask(__name__, static_folder='static')

# ─── Platform definitions ───────────────────────────────────────────────
# Only platforms that are reliable to check without getting insta-banned
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
}

# Rotate these headers to look more like a real browser
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

request_counter = 0  # tracks how many requests made (for VPN rotation reminder)

def check_username(username, platform_name):
    platform = PLATFORMS[platform_name]
    url = platform["url"].format(username)
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        r = requests.get(url, headers=headers, timeout=6, allow_redirects=True)
        if r.status_code == platform["taken_code"]:
            return "taken"
        elif r.status_code == platform["available_code"]:
            return "available"
        else:
            return "unknown"
    except requests.exceptions.Timeout:
        return "timeout"
    except requests.exceptions.ConnectionError:
        return "error"
    except Exception:
        return "error"

# ─── Routes ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/check", methods=["POST"])
def check():
    global request_counter

    data = request.get_json()
    usernames = data.get("usernames", [])
    platforms = data.get("platforms", list(PLATFORMS.keys()))
    delay = float(data.get("delay", 1.5))

    results = []

    for i, username in enumerate(usernames):
        username = username.strip()
        if not username or len(username) != 4:
            continue

        row = {"username": username, "platforms": {}}

        for platform in platforms:
            if platform not in PLATFORMS:
                continue

            status = check_username(username, platform)
            row["platforms"][platform] = status
            request_counter += 1

            # Warn frontend every 50-100 requests to rotate VPN
            if request_counter % 75 == 0:
                row["vpn_reminder"] = True

            # Delay between each request to avoid rate limiting
            time.sleep(delay + random.uniform(0, 0.5))

        results.append(row)

    return jsonify({"results": results, "total_requests": request_counter})

@app.route("/platforms", methods=["GET"])
def get_platforms():
    return jsonify(list(PLATFORMS.keys()))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
