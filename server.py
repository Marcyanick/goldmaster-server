from flask import Flask, request, jsonify
import os
import json
import requests
from datetime import datetime, timezone

try:
    # Python 3.9+
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # fallback if not available

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Choose your display timezone (Montreal/Toronto)
DISPLAY_TZ_NAME = os.getenv("DISPLAY_TZ", "America/Toronto")


def tg_send(text: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Missing TELEGRAM env vars")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=10)
        print("📨 Telegram:", r.status_code, r.text[:200])
        return r.ok
    except Exception as e:
        print("❌ Telegram send error:", str(e))
        return False


def parse_tv_payload() -> dict:
    """
    Robust parser for TradingView webhooks:
    - application/json payload
    - text/plain body containing JSON
    - {"message":"{...json...}"} wrapper
    - returns dict (never None)
    """
    payload = request.get_json(silent=True)

    if payload is None:
        raw = (request.get_data(as_text=True) or "").strip()
        if raw:
            try:
                payload = json.loads(raw)
            except Exception:
                payload = {"raw": raw}

    if isinstance(payload, dict) and isinstance(payload.get("message"), str):
        msg = payload["message"].strip()
        if msg.startswith("{") and msg.endswith("}"):
            try:
                payload = json.loads(msg)
            except Exception:
                pass

    return payload if isinstance(payload, dict) else {}


def format_tv_time(tv_time_value) -> str:
    """
    Converts TradingView 'time' into readable local time.
    TradingView often sends milliseconds since epoch.
    Accepts int/float/str. Returns "" if cannot parse.
    """
    if tv_time_value is None:
        return ""

    # Extract digits safely
    s = str(tv_time_value).strip()
    if not s:
        return ""

    try:
        # Some payloads may send float-like strings
        ts = int(float(s))
    except Exception:
        return ""

    # Detect ms vs seconds:
    # - seconds around 1_700_000_000 (10 digits)
    # - ms around 1_700_000_000_000 (13 digits)
    if ts > 10_000_000_000:  # definitely ms
        ts_seconds = ts / 1000.0
    else:
        ts_seconds = float(ts)

    # Build datetime in UTC then convert to desired tz
    dt_utc = datetime.fromtimestamp(ts_seconds, tz=timezone.utc)

    if ZoneInfo is not None:
        try:
            tz = ZoneInfo(DISPLAY_TZ_NAME)
            dt_local = dt_utc.astimezone(tz)
            return dt_local.strftime("%Y-%m-%d %H:%M:%S") + f" ({DISPLAY_TZ_NAME})"
        except Exception:
            pass

    # Fallback: show UTC if ZoneInfo not available or TZ fails
    return dt_utc.strftime("%Y-%m-%d %H:%M:%S") + " (UTC)"


@app.post("/signal")
def signal():
    payload = parse_tv_payload()
    print("📩 payload:", payload)

    # Detect GoldMasterFVG flexibly
    strategy = str(payload.get("strategy", "")).strip()
    strategy_lc = strategy.lower().replace(" ", "")
    is_fvg = "goldmasterfvg" in strategy_lc

    if not is_fvg:
        return jsonify({"ok": True, "ignored": True, "reason": "not GoldMasterFVG"}), 200

    # Extract fields sent by Pine
    event = str(payload.get("event", "TOUCH")).strip()
    symbol = str(payload.get("symbol", payload.get("ticker", ""))).strip()
    ltf = str(payload.get("tf", payload.get("interval", ""))).strip()
    price = str(payload.get("price", payload.get("close", ""))).strip()

    htf = str(payload.get("htf", "")).strip()           # "15" or "60"
    side = str(payload.get("side", "")).strip()         # "BULL" / "BEAR"
    mode = str(payload.get("mode", "")).strip()         # "WICK" / "CLOSE"
    top = str(payload.get("top", "")).strip()
    bot = str(payload.get("bot", "")).strip()

    # Convert time
    t_raw = payload.get("time")
    t_human = format_tv_time(t_raw)

    # Clean Telegram message (final)
    msg_lines = [
        "🟡 Gold Master FVG",
        f"🔔 {event}",
        f"📌 HTF: {htf}m | Side: {side} | Mode: {mode}",
        f"📊 {symbol} (LTF {ltf})",
        f"💰 Price: {price}",
    ]

    if top and bot:
        msg_lines.append(f"🧱 Zone: {bot} → {top}")

    if t_human:
        msg_lines.append(f"🕒 {t_human}")

    msg = "\n".join(msg_lines)

    sent_ok = tg_send(msg)
    return jsonify({"ok": True, "sent": sent_ok}), 200


@app.get("/")
def home():
    return "OK", 200
