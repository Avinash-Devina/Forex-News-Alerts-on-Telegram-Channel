import os
import requests
from datetime import datetime, timedelta, timezone

# --- ENV ---
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
FEED_URL = os.environ["FEED_URL"]

# --- TIMEZONES ---
UTC = timezone.utc
IST = timezone(timedelta(hours=5, minutes=30))

# --- FILTERS ---
ALLOWED_IMPACT = {"High", "Medium"}
ALLOWED_COUNTRY = {"USD", "CNY"}

# --- ALERT WINDOW (minutes before event) ---
# PRODUCTION (recommended)
ALERT_MIN = 10
ALERT_MAX = 20

# ---- TESTING EXAMPLE (comment out in prod) ----
# ALERT_MIN = 1000
# ALERT_MAX = 2000

def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": msg,
            "disable_web_page_preview": True
        },
        timeout=20
    ).raise_for_status()

# Fetch Forex Factory weekly feed
events = requests.get(FEED_URL, timeout=20).json()

now_utc = datetime.now(UTC)

for e in events:
    # --- BASIC FILTERS ---
    if e.get("impact") not in ALLOWED_IMPACT:
        continue

    if e.get("country") not in ALLOWED_COUNTRY:
        continue

    date_raw = e.get("date")
    time_raw = e.get("time")

    if not date_raw:
        continue

    event_dt_utc = None

    # ✅ PRIMARY: use scheduled date + time (authoritative)
    if time_raw and time_raw not in ("", "All Day"):
        try:
            event_dt_utc = datetime.strptime(
                f"{date_raw[:10]} {time_raw}",
                "%Y-%m-%d %H:%M"
            ).replace(tzinfo=UTC)
        except ValueError:
            pass

    # ⛑️ FALLBACK: ISO timestamp only if no time exists
    if event_dt_utc is None:
        try:
            iso_dt = datetime.fromisoformat(date_raw)
            if iso_dt.tzinfo:
                event_dt_utc = iso_dt.astimezone(UTC)
            else:
                event_dt_utc = iso_dt.replace(tzinfo=UTC)
        except ValueError:
            continue

    # Minutes until event
    minutes_to_event = (event_dt_utc - now_utc).total_seconds() / 60

    # --- ALERT WINDOW CHECK ---
    if not (ALERT_MIN <= minutes_to_event <= ALERT_MAX):
        continue

    # Convert to IST
    event_dt_ist = event_dt_utc.astimezone(IST)

    # Human-friendly countdown
    total_minutes = int(round(minutes_to_event))
    hours = total_minutes // 60
    minutes = total_minutes % 60

    if hours > 0:
        countdown = f"{hours}h {minutes}m"
    else:
        countdown = f"{minutes}m"

    message = (
        f"🚨 UPCOMING ECONOMIC EVENT 🚨\n\n"
        f"📊 {e['title']}\n"
        f"🕒 {event_dt_ist.strftime('%d %b %Y, %I:%M %p')} IST\n"
        f"🌍 {e['country']}\n"
        f"⚠️ Impact: {e['impact']}\n\n"
        f"⏰ Releasing in {countdown}"
    )

    send(message)
