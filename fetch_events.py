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

# --- ALERT WINDOW (minutes before confirmed event) ---
ALERT_MIN = 10
ALERT_MAX = 20

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
today_ist = datetime.now(IST).date()

for e in events:
    # --- FILTERS ---
    if e.get("impact") not in ALLOWED_IMPACT:
        continue

    if e.get("country") not in ALLOWED_COUNTRY:
        continue

    date_raw = e.get("date")
    time_raw = e.get("time")

    if not date_raw:
        continue

    # Detect tentative / all-day events
    is_tentative = not time_raw or time_raw in ("", "Tentative", "All Day")

    # =============================
    # TENTATIVE EVENT (DATE ONLY)
    # =============================
    if is_tentative:
        try:
            event_date = datetime.strptime(
                date_raw[:10], "%Y-%m-%d"
            ).date()
        except ValueError:
            continue

        # ✅ Only alert tentative events on TODAY (IST)
        if event_date != today_ist:
            continue

        message = (
            f"🚨 UPCOMING ECONOMIC EVENT 🚨\n\n"
            f"📊 {e['title']}\n"
            f"🕒 {event_date.strftime('%d %b %Y')} – Tentative\n"
            f"⏰ Time not updated\n"
            f"🌍 {e['country']}\n"
            f"⚠️ Impact: {e['impact']}"
        )

        send(message)
        continue

    # =============================
    # CONFIRMED EVENT (WITH TIME)
    # =============================
    try:
        event_dt_utc = datetime.strptime(
            f"{date_raw[:10]} {time_raw}",
            "%Y-%m-%d %H:%M"
        ).replace(tzinfo=UTC)
    except ValueError:
        continue

    minutes_to_event = (event_dt_utc - now_utc).total_seconds() / 60

    # 🔔 15-minute-before window
    if not (ALERT_MIN <= minutes_to_event <= ALERT_MAX):
        continue

    event_dt_ist = event_dt_utc.astimezone(IST)

    total_minutes = int(round(minutes_to_event))
    hours = total_minutes // 60
    minutes = total_minutes % 60
    countdown = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

    message = (
        f"🚨 UPCOMING ECONOMIC EVENT 🚨\n\n"
        f"📊 {e['title']}\n"
        f"🕒 {event_dt_ist.strftime('%d %b %Y, %I:%M %p')} IST\n"
        f"⏰ Releasing in {countdown}\n"
        f"🌍 {e['country']}\n"
        f"⚠️ Impact: {e['impact']}"
    )

    send(message)
