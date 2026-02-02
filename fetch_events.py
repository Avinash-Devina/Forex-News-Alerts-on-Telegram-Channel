import os
import requests
from datetime import datetime, timedelta, timezone

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
FEED_URL = os.environ["FEED_URL"]

HOURS_AHEAD = 72  # 👈 change to 6, 24, etc.

def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg,
        "disable_web_page_preview": True
    }).raise_for_status()

# Fetch Forex Factory weekly feed (list)
events = requests.get(FEED_URL, timeout=20).json()

now = datetime.now(timezone.utc)
window_end = now + timedelta(hours=HOURS_AHEAD)

sent_any = False

for e in events:
    # Skip events without time (like "All Day")
    if not e.get("time") or e["time"] == "":
        continue

    try:
        event_dt = datetime.strptime(
            f"{e['date']} {e['time']}",
            "%Y-%m-%d %H:%M"
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        continue

    if not (now <= event_dt <= window_end):
        continue

    message = (
        f"📊 {e['title']}\n"
        f"🕒 {event_dt.strftime('%Y-%m-%d %H:%M')} UTC\n"
        f"🌍 {e['country']}\n"
        f"⚠️ Impact: {e['impact']}"
    )

    send(message)
    sent_any = True

if not sent_any:
    send(f"ℹ️ No economic events in the next {HOURS_AHEAD} hours.")
