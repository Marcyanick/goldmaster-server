from flask import Flask, request, jsonify
import os
import json
import requests

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def tg_send(text: str):
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

def parse_tv_payload():
    """
    Robust parser for TradingView webhooks.
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

    strategy = str(payload.get("strategy", "")).strip().lower().replace(" ", "")
    event    = str(payload.get("event", "")).strip()
    symbol   = str(payload.get("symbol", payload.get("ticker", ""))).strip()
    tf       = str(payload.get("tf", payload.get("interval", ""))).strip()
    price    = str(payload.get("price", payload.get("close", ""))).strip()
    t        = str(payload.get("time", "")).strip()

    # Flexible detection for FVG strategy
    is_fvg = "goldmasterfvg" in strategy

    if is_fvg:
        msg = (
            f"🟡 GoldMasterFVG\n"
            f"🔔 {event or 'ALERT'}\n"
            f"📊 {symbol or '-'} ({tf or '-'})\n"
            f"💰 {price or '-'}\n"
            f"🕒 {t or '-'}"
        )
        sent_ok = tg_send(msg)
        return jsonify({"ok": True, "mode": "FVG", "sent": sent_ok}), 200

    # Old GoldMaster v6.6 logic
    decision = payload.get("decision")

    if not decision:
        raw = json.dumps(payload, indent=2, ensure_ascii=False)[:3500]
        msg = "🟥 RAW DEBUG (no decision / not FVG)\n\n" + raw
        sent_ok = tg_send(msg)
        return jsonify({"ok": True, "mode": "RAW", "sent": sent_ok, "reason": "no decision"}), 200

    msg = f"🟦 GoldMaster\n✅ {decision}\n📊 {symbol} ({tf})\n💰 {price}\n🕒 {t}"
    sent_ok = tg_send(msg)
    return jsonify({"ok": True, "mode": "GM", "sent": sent_ok}), 200

@app.get("/")
def home():
    return "OK", 200
