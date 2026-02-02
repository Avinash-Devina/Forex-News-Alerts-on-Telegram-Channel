import os
import requests
from datetime import datetime, timedelta, timezone

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
FEED_URL = os.environ["FEED_URL"]

HOURS_AHEAD = 2  # change if needed

IST = timezone(timedelta(hours=5, minutes=30))

ALLOWED_IMPACT = {"High", "Medium"}
ALLOWED_COUNTRY = {"USD", "CNY"}  # China = CNY in FF feed

def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg,
        "disable_web_page_preview": True
    }).raise_for_status()

events = requests.get(FEED_URL, timeout=20).json()

now_utc = datetime.now(timezone.utc)
window_end = now_utc + timedelta(hours=HOURS_AHEAD)

sent_any = False

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

    event_dt_utc = None

    # Case 1: ISO timestamp in date
    try:
        event_dt_utc = datetime.fromisoformat(date_raw)
        if event_dt_utc.tzinfo is None:
            event_dt_utc = event_dt_utc.replace(tzinfo=timezone.utc)
        else:
            event_dt_utc = event_dt_utc.astimezone(timezone.utc)
    except ValueError:
        pass

    # Case 2: date + time
    if event_dt_utc is None and time_raw and time_raw not in ("", "All Day"):
        try:
            event_dt_utc = datetime.strptime(
                f"{date_raw} {time_raw}",
                "%Y-%m-%d %H:%M"
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    # Case 3: All Day / date-only
    if event_dt_utc is None:
        try:
            event_dt_utc = datetime.strptime(
                date_raw[:10],
                "%Y-%m-%d"
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    if not (now_utc <= event_dt_utc <= window_end):
        continue

    # Convert to IST
    event_dt_ist = event_dt_utc.astimezone(IST)

    message = (
        f"📊 {e['title']}\n"
        f"🕒 {event_dt_ist.strftime('%d %b %Y, %I:%M %p')} IST\n"
        f"🌍 {e['country']}\n"
        f"⚠️ Impact: {e['impact']}"
    )

    send(message)
    sent_any = True

if not sent_any:
    send(f"ℹ️ No High/Medium USD or China events in the next {HOURS_AHEAD} hours.")
