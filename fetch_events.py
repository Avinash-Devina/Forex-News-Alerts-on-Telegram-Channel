import os
import json
import hashlib
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
ALERT_MIN = 200
ALERT_MAX = 240

# --- DEDUP FILE ---
DEDUP_FILE = "sent_events.json"

# -------------------------
# Helpers
# -------------------------
def load_sent():
    if os.path.exists(DEDUP_FILE):
        with open(DEDUP_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_sent(sent):
    with open(DEDUP_FILE, "w") as f:
        json.dump(sorted(sent), f)

def event_id(e, key):
    raw = f"{e.get('title')}|{e.get('country')}|{key}"
    return hashlib.sha1(raw.encode()).hexdigest()

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

# -------------------------
# Load state
# -------------------------
sent_events = load_sent()
changed = False

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

    # -------------------------
    # STEP 1: PARSE EVENT TIME (CRITICAL FIX)
    # -------------------------
    event_dt_utc = None

    # 1️⃣ ISO datetime inside `date`
    try:
        event_dt_utc = datetime.fromisoformat(date_raw)
        if event_dt_utc.tzinfo is None:
            event_dt_utc = event_dt_utc.replace(tzinfo=UTC)
        else:
            event_dt_utc = event_dt_utc.astimezone(UTC)
    except ValueError:
        pass

    # 2️⃣ date + time fields
    if event_dt_utc is None and time_raw and time_raw not in ("", "Tentative", "All Day"):
        try:
            event_dt_utc = datetime.strptime(
                f"{date_raw[:10]} {time_raw}",
                "%Y-%m-%d %H:%M"
            ).replace(tzinfo=UTC)
        except ValueError:
            pass

    # 3️⃣ Tentative only if BOTH failed
    is_tentative = event_dt_utc is None

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

        # Only alert tentative events on TODAY (IST)
        if event_date != today_ist:
            continue

        eid = event_id(e, f"tentative-{event_date}")
        if eid in sent_events:
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
        sent_events.add(eid)
        changed = True
        continue

    # =============================
    # CONFIRMED EVENT (15-MIN ALERT)
    # =============================
    minutes_to_event = (event_dt_utc - now_utc).total_seconds() / 60

    if not (ALERT_MIN <= minutes_to_event <= ALERT_MAX):
        continue

    eid = event_id(e, event_dt_utc.isoformat())
    if eid in sent_events:
        continue

    event_dt_ist = event_dt_utc.astimezone(IST)

    total_minutes = int(round(minutes_to_event))
    h, m = divmod(total_minutes, 60)
    countdown = f"{h}h {m}m" if h > 0 else f"{m}m"

    message = (
        f"🚨 UPCOMING ECONOMIC EVENT 🚨\n\n"
        f"📊 {e['title']}\n"
        f"🕒 {event_dt_ist.strftime('%d %b %Y, %I:%M %p')} IST\n"
        f"⏰ Releasing in {countdown}\n"
        f"🌍 {e['country']}\n"
        f"⚠️ Impact: {e['impact']}"
    )

    send(message)
    sent_events.add(eid)
    changed = True

# -------------------------
# SAVE STATE
# -------------------------
if changed:
    save_sent(sent_events)