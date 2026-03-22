import requests
import time
import os
import random
import threading
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
# Set these as environment variables in Railway:
# TELEGRAM_BOT_TOKEN = your bot token from @BotFather
# TELEGRAM_CHAT_ID   = your chat ID (get from @userinfobot)

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID   = os.environ.get('TELEGRAM_CHAT_ID', '')
CHECK_INTERVAL     = int(os.environ.get('CHECK_INTERVAL', 30))  # seconds between checks

USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 Version/17.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/122.0.6261.90 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
]

# In-memory store for monitored usernames
# Format: { "username": { "status": "taken/available/unknown", "since": timestamp } }
monitored = {}
monitor_lock = threading.Lock()
monitor_thread = None
monitoring_active = False

# ── Telegram notifications ────────────────────────────────────────────────────

def send_telegram_to(message, token, chat_id):
    if not token or not chat_id:
        print("Telegram not configured — skipping notification")
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def send_telegram(message):
    return send_telegram_to(message, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)

# ── Instagram username check ──────────────────────────────────────────────────

def check_username_on_platform(username, platform="instagram"):
    """Route to appropriate checker based on platform."""
    if platform == "github":
        try:
            r = requests.get(f"https://api.github.com/users/{username}",
                headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "username-checker/1.0"},
                timeout=6)
            if r.status_code == 200: return "taken"
            if r.status_code == 404: return "available"
            return "unknown"
        except: return "unknown"
    elif platform == "reddit":
        try:
            r = requests.get(f"https://www.reddit.com/user/{username}/about.json",
                headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=6)
            if r.status_code == 200: return "taken"
            if r.status_code == 404: return "available"
            return "unknown"
        except: return "unknown"
    elif platform == "twitch":
        try:
            r = requests.get(f"https://www.twitch.tv/{username}",
                headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=5)
            return "taken" if r.status_code == 200 else "available"
        except: return "unknown"
    elif platform == "telegram":
        try:
            r = requests.get(f"https://t.me/{username}",
                headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=5)
            return "taken" if r.status_code == 200 else "available"
        except: return "unknown"
    else:
        return check_instagram_username(username)

def check_instagram_username(username):
    """
    Check via Instagram's signup validation endpoint.
    Returns: 'available', 'taken', or 'unknown'
    """
    try:
        session = requests.Session()
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "X-Instagram-AJAX": "1",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.instagram.com/accounts/emailsignup/",
            "Origin": "https://www.instagram.com",
        }

        # First get cookies
        session.get("https://www.instagram.com/accounts/emailsignup/",
                   headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=8)

        # Check username via their validation endpoint
        resp = session.get(
            f"https://www.instagram.com/api/v1/users/check_username/",
            params={"username": username},
            headers=headers,
            timeout=8
        )

        if resp.status_code == 200:
            data = resp.json()
            if data.get("available") == True:
                return "available"
            elif data.get("available") == False:
                return "taken"

        # Fallback: check profile page
        profile = session.get(
            f"https://www.instagram.com/{username}/",
            headers={"User-Agent": random.choice(USER_AGENTS)},
            timeout=6,
            allow_redirects=True
        )
        if profile.status_code == 404:
            return "available"
        elif profile.status_code == 200:
            return "taken"
        else:
            return "unknown"

    except requests.exceptions.Timeout:
        return "unknown"
    except Exception as e:
        print(f"Check error for {username}: {e}")
        return "unknown"

# ── Monitor loop ──────────────────────────────────────────────────────────────

def monitor_loop():
    global monitoring_active
    print("Monitor loop started")

    while monitoring_active:
        with monitor_lock:
            usernames = list(monitored.keys())

        if not usernames:
            time.sleep(CHECK_INTERVAL)
            continue

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking {len(usernames)} usernames...")

        for username in usernames:
            if not monitoring_active:
                break

            prev_status = monitored.get(username, {}).get("status", "unknown")
            platform = monitored.get(username, {}).get("platform", "instagram")
            new_status = check_username_on_platform(username, platform)

            with monitor_lock:
                if username in monitored:
                    monitored[username]["status"] = new_status
                    monitored[username]["last_checked"] = datetime.now().isoformat()

            print(f"  @{username}: {new_status}")

            # Alert if became available
            if new_status == "available" and prev_status != "available":
                platform_name = info.get("platform", "instagram").capitalize()
                msg = (
                    f"🚨 <b>USERNAME AVAILABLE!</b>\n\n"
                    f"✅ <b>@{username}</b> is now available on <b>{platform_name}</b>!\n\n"
                    f"⚡ Claim it NOW — open {platform_name} and set your username to <b>{username}</b>\n\n"
                    f"⏰ {datetime.now().strftime('%H:%M:%S')}"
                )
                # Use per-username credentials if available
                info = monitored.get(username, {})
                token = info.get("token", TELEGRAM_BOT_TOKEN)
                chat_id = info.get("chat_id", TELEGRAM_CHAT_ID)
                send_telegram_to(msg, token, chat_id)
                print(f"  *** ALERT SENT for @{username} ***")

            # Small delay between each check to avoid rate limiting
            time.sleep(random.uniform(3, 6))

        print(f"  Cycle complete. Next check in {CHECK_INTERVAL}s")
        time.sleep(CHECK_INTERVAL)

    print("Monitor loop stopped")

def start_monitor():
    global monitor_thread, monitoring_active
    if monitoring_active:
        return
    monitoring_active = True
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()

def stop_monitor():
    global monitoring_active
    monitoring_active = False

# ── Flask routes (added to main app) ─────────────────────────────────────────

def register_monitor_routes(app):

    @app.route("/monitor/add", methods=["POST"])
    def monitor_add():
        from flask import request, jsonify
        data = request.get_json(silent=True) or {}
        usernames = data.get("usernames", [])
        token = data.get("token", TELEGRAM_BOT_TOKEN)
        chat_id = data.get("chat_id", TELEGRAM_CHAT_ID)
        if not usernames:
            return jsonify({"error": "No usernames provided"}), 400

        added = []
        with monitor_lock:
            for u in usernames:
                u = u.strip().lower()
                if u and len(u) <= 30 and u not in monitored:
                    monitored[u] = {
                        "status": "unknown",
                        "added": datetime.now().isoformat(),
                        "last_checked": None,
                        "token": token,
                        "chat_id": chat_id,
                        "platform": data.get("platform", "instagram"),
                    }
                    added.append(u)

        if not monitoring_active:
            start_monitor()

        return jsonify({"added": added, "total_monitored": len(monitored)})

    @app.route("/monitor/remove", methods=["POST"])
    def monitor_remove():
        from flask import request, jsonify
        data = request.get_json(silent=True) or {}
        username = data.get("username", "").strip().lower()
        with monitor_lock:
            if username in monitored:
                del monitored[username]
        return jsonify({"removed": username, "total_monitored": len(monitored)})

    @app.route("/monitor/list", methods=["GET"])
    def monitor_list():
        from flask import jsonify
        with monitor_lock:
            return jsonify({
                "monitored": monitored,
                "active": monitoring_active,
                "count": len(monitored)
            })

    @app.route("/monitor/clear", methods=["POST"])
    def monitor_clear():
        from flask import jsonify
        with monitor_lock:
            monitored.clear()
        return jsonify({"cleared": True})

    @app.route("/monitor/test-telegram", methods=["GET", "POST"])
    def test_telegram():
        from flask import request, jsonify
        data = request.get_json(silent=True) or {}
        token = data.get("token", TELEGRAM_BOT_TOKEN)
        chat_id = data.get("chat_id", TELEGRAM_CHAT_ID)
        if not token or not chat_id:
            return jsonify({"sent": False, "configured": False})
        ok = send_telegram_to("✅ <b>Monitor connected!</b>\nYour Instagram username monitor is working. You will be notified here when a username becomes available.", token, chat_id)
        return jsonify({"sent": ok, "configured": True})
