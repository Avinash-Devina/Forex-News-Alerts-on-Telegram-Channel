import os
import requests
from datetime import datetime, timedelta, timezone

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
FEED_URL = os.environ["FEED_URL"]

HOURS_AHEAD = 72  # change to 2 later if you want

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
    date_str = e.get("date")
    time_str = e.get("time", "")

    if not date_str:
        continue

    # Handle "All Day" or missing time
    if time_str in ("", "All Day", None):
        event_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
        time_label = "All Day"
    else:
        try:
            event_dt = datetime.strptime(
                f"{date_str} {time_str}",
                "%Y-%m-%d %H:%M"
            ).replace(tzinfo=timezone.utc)
            time_label = event_dt.strftime("%H:%M UTC")
        except ValueError:
            continue

    if not (now <= event_dt <= window_end):
        continue

    message = (
        f"📊 {e['title']}\n"
        f"🕒 {date_str} {time_label}\n"
        f"🌍 {e['country']}\n"
        f"⚠️ Impact: {e['impact']}"
    )

    send(message)
    sent_any = True

if not sent_any:
    send(f"ℹ️ No economic events in the next {HOURS_AHEAD} hours.")
