import os
import requests
from datetime import datetime, timedelta, timezone

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
FEED_URL = os.environ["FEED_URL"]

HOURS_AHEAD = 2  # 👈 change as needed

def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg,
        "disable_web_page_preview": True
    }).raise_for_status()

events = requests.get(FEED_URL, timeout=20).json()

now = datetime.now(timezone.utc)
window_end = now + timedelta(hours=HOURS_AHEAD)

sent_any = False

for e in events:
    date_raw = e.get("date")
    time_raw = e.get("time")

    if not date_raw:
        continue

    event_dt = None
    time_label = ""

    # Case 1: ISO timestamp in "date"
    try:
        event_dt = datetime.fromisoformat(date_raw)
        if event_dt.tzinfo is None:
            event_dt = event_dt.replace(tzinfo=timezone.utc)
        else:
            event_dt = event_dt.astimezone(timezone.utc)
        time_label = event_dt.strftime("%H:%M UTC")
    except ValueError:
        pass

    # Case 2: date + time fields
    if event_dt is None and time_raw and time_raw not in ("All Day", ""):
        try:
            event_dt = datetime.strptime(
                f"{date_raw} {time_raw}",
                "%Y-%m-%d %H:%M"
            ).replace(tzinfo=timezone.utc)
            time_label = event_dt.strftime("%H:%M UTC")
        except ValueError:
            pass

    # Case 3: All Day or date-only
    if event_dt is None:
        try:
            event_dt = datetime.strptime(
                date_raw[:10],
                "%Y-%m-%d"
            ).replace(tzinfo=timezone.utc)
            time_label = "All Day"
        except ValueError:
            continue

    if not (now <= event_dt <= window_end):
        continue

    message = (
        f"📊 {e['title']}\n"
        f"🕒 {event_dt.strftime('%Y-%m-%d')} {time_label}\n"
        f"🌍 {e['country']}\n"
        f"⚠️ Impact: {e['impact']}"
    )

    send(message)
    sent_any = True

if not sent_any:
    send(f"ℹ️ No economic events in the next {HOURS_AHEAD} hours.")
