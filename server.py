from flask import Flask, request, jsonify
import os
import json
import requests

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


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
    t = str(payload.get("time", "")).strip()

    htf = str(payload.get("htf", "")).strip()           # "15" or "60"
    side = str(payload.get("side", "")).strip()         # "BULL" / "BEAR"
    mode = str(payload.get("mode", "")).strip()         # "WICK" / "CLOSE"
    top = str(payload.get("top", "")).strip()
    bot = str(payload.get("bot", "")).strip()

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

    if t:
        msg_lines.append(f"🕒 {t}")

    msg = "\n".join(msg_lines)

    sent_ok = tg_send(msg)
    return jsonify({"ok": True, "sent": sent_ok}), 200


@app.get("/")
def home():
    return "OK", 200
