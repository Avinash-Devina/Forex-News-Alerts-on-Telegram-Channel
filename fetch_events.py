import os
import requests
from datetime import datetime, timezone

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
FEED_URL = os.environ["FEED_URL"]

def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg,
        "disable_web_page_preview": True
    })
    r.raise_for_status()

# Fetch feed (Forex Factory returns a LIST)
events = requests.get(FEED_URL, timeout=20).json()

now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")

count = 0
for e in events:
    # Only today's events
    if e.get("date") != now_utc:
        continue

    message = (
        f"📊 {e['title']}\n"
        f"🕒 {e['date']} {e['time']} UTC\n"
        f"🌍 {e['country']}\n"
        f"⚠️ Impact: {e['impact']}"
    )

    send(message)
    count += 1

if count == 0:
    send("ℹ️ No economic events today.")
