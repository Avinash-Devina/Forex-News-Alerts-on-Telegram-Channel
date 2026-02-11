import os
import json
import hashlib
import requests
from collections import defaultdict
from datetime import datetime, timedelta, timezone

# =========================
# ENV
# =========================
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
FEED_URL = os.environ["FEED_URL"]

# =========================
# TIMEZONES
# =========================
UTC = timezone.utc
IST = timezone(timedelta(hours=5, minutes=30))

# =========================
# FILTERS
# =========================
ALLOWED_IMPACT = {"High", "Medium"}
ALLOWED_COUNTRY = {"USD", "CNY"}

# =========================
# SAFE ALERT WINDOWS (30-min cron compatible)
# =========================
ALERT_WINDOWS = {
    "1H": (50, 70),     # 50–70 minutes before
    "30M": (20, 40),    # 20–40 minutes before
    "15M": (5, 25),     # 5–25 minutes before
}

# =========================
# DEDUP STORAGE
# =========================
DEDUP_FILE = "sent_events.json"

# =========================
# HELPERS
# =========================
def load_sent():
    if os.path.exists(DEDUP_FILE):
        with open(DEDUP_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_sent(sent):
    with open(DEDUP_FILE, "w") as f:
        json.dump(sorted(sent), f)

def make_id(key):
    return hashlib.sha1(key.encode()).hexdigest()

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

# =========================
# LOAD STATE
# =========================
sent_events = load_sent()
changed = False

events = requests.get(FEED_URL, timeout=20).json()
now_utc = datetime.now(UTC)

# =========================
# GROUP EVENTS BY (TIME, ALERT TYPE)
# =========================
groups = defaultdict(lambda: defaultdict(list))

for e in events:

    if e.get("impact") not in ALLOWED_IMPACT:
        continue

    if e.get("country") not in ALLOWED_COUNTRY:
        continue

    date_raw = e.get("date")
    time_raw = e.get("time")

    if not date_raw:
        continue

    event_dt_utc = None

    # 1️⃣ ISO datetime (Forex Factory grouped releases)
    try:
        event_dt_utc = datetime.fromisoformat(date_raw)
        if event_dt_utc.tzinfo is None:
            event_dt_utc = event_dt_utc.replace(tzinfo=UTC)
        else:
            event_dt_utc = event_dt_utc.astimezone(UTC)
    except ValueError:
        pass

    # 2️⃣ Fallback to date + time fields
    if event_dt_utc is None and time_raw and time_raw not in ("", "Tentative", "All Day"):
        try:
            event_dt_utc = datetime.strptime(
                f"{date_raw[:10]} {time_raw}",
                "%Y-%m-%d %H:%M"
            ).replace(tzinfo=UTC)
        except ValueError:
            pass

    if event_dt_utc is None:
        continue

    minutes_to_event = (event_dt_utc - now_utc).total_seconds() / 60

    for label, (min_m, max_m) in ALERT_WINDOWS.items():
        if min_m <= minutes_to_event <= max_m:
            groups[(event_dt_utc, label)][label].append(e)

# =========================
# SEND ALERTS (UNIFIED TEMPLATE)
# =========================
for (event_dt_utc, label), bucket in groups.items():

    dedup_key = f"{label}-{event_dt_utc.isoformat()}"
    eid = make_id(dedup_key)

    if eid in sent_events:
        continue

    events_at_time = bucket[label]
    event_dt_ist = event_dt_utc.astimezone(IST)

    minutes_left = int(round((event_dt_utc - now_utc).total_seconds() / 60))
    h, m = divmod(minutes_left, 60)
    countdown = f"{h}h {m}m" if h > 0 else f"{m}m"

    lines = []
    for e in sorted(events_at_time, key=lambda x: x["impact"], reverse=True):
        impact_icon = "🔴" if e["impact"] == "High" else "🟠"
        lines.append(f"{impact_icon} {e['title']} ({e['impact']})")

    countries = " & ".join(sorted({e["country"] for e in events_at_time}))
    event_word = "DATA RELEASE" if len(events_at_time) > 1 else "DATA EVENT"

    message = (
        f"🚨 {countries} {event_word} — {label} ALERT 🚨\n\n"
        f"🕒 {event_dt_ist.strftime('%d %b %Y, %I:%M %p')} IST\n"
        f"⏰ Releasing in {countdown}\n\n"
        f"{chr(10).join(lines)}"
    )

    send(message)
    sent_events.add(eid)
    changed = True

# =========================
# SAVE STATE
# =========================
if changed:
    save_sent(sent_events)
